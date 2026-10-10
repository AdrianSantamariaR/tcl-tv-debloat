import json,tempfile,threading,unittest,copy
from pathlib import Path
from tests.support import fake_adb,fixture_catalog,change_state
from tcl_tv_debloat.inventory import scan
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.plans import build_plan,build_restore_plan,execute_plan,export_recovery

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.adb,self.state=fake_adb(self.root)
        self.catalog=fixture_catalog();self.store=Store(self.root/'data')
        self.inv=scan(self.adb,'fixture-tv',self.catalog)
    def save_plan(self, inv=None):
        plan=build_plan(inv or self.inv,{'com.example.optional':'disable'});self.store.save('plans',plan);return plan
    def state_of(self):return json.loads(self.state.read_text())['packages']['com.example.optional']['enabled']
    def mutations(self):return [x for x in self.state.with_name('commands.jsonl').read_text().splitlines() if any('"'+a+'"' in x for a in ['disable-user','default-state','enable','disable','disable-until-used'])]
    def test_restore_exact_states_zero_through_four_and_duplicate_no_replay(self):
        for state in range(5):
            d=json.loads(self.state.read_text());d['packages']['com.example.optional']['enabled']=state;self.state.write_text(json.dumps(d))
            inv=scan(self.adb,'fixture-tv',self.catalog);p=self.save_plan(inv)
            j=execute_plan(self.adb,self.store,self.catalog,p)
            self.assertEqual(self.state_of(),3)
            count=len(self.mutations());execute_plan(self.adb,self.store,self.catalog,p);self.assertEqual(len(self.mutations()),count)
            undo=build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),j);self.store.save('plans',undo)
            execute_plan(self.adb,self.store,self.catalog,undo);self.assertEqual(self.state_of(),state)
    def test_unsaved_protected_invalid_and_forged_plans_do_not_write(self):
        for name in ['android','unknown.app','x;id']:
            with self.assertRaises(ValueError):build_plan(self.inv,{name:'disable'})
        p=build_plan(self.inv,{'com.example.optional':'disable'})
        with self.assertRaises(ValueError):execute_plan(self.adb,self.store,self.catalog,p)
        p['changes'][0]['package']='android';self.store.save('plans',p)
        with self.assertRaises(ValueError):execute_plan(self.adb,self.store,self.catalog,p)
        self.assertEqual(self.mutations(),[])
    def test_all_preflight_identity_state_version_and_user_before_writes(self):
        for mode in ['fingerprint','hardware_id','user','state','version']:
            p=self.save_plan();original=self.state.read_text();d=json.loads(original)
            if mode=='fingerprint':d['props']['ro.build.fingerprint']='changed'
            elif mode=='hardware_id':d['props']['ro.serialno']='other'
            elif mode=='user':d['user']=10
            elif mode=='state':d['packages']['com.example.optional']['enabled']=1
            else:d['packages']['com.example.optional']['version_code']=8
            self.state.write_text(json.dumps(d))
            with self.assertRaises(ValueError):execute_plan(self.adb,self.store,self.catalog,p)
            self.assertEqual(self.mutations(),[]);self.state.write_text(original)
    def test_lost_response_is_uncertain_and_recoverable_after_restart(self):
        p=self.save_plan();change_state(self.state,lose_response=True)
        j=execute_plan(self.adb,self.store,self.catalog,p);self.assertEqual(j['changes'][0]['outcome'],'uncertain');self.assertEqual(self.state_of(),3)
        change_state(self.state,lose_response=False)
        store=Store(self.root/'data');j=store.load('plans',p['id'])
        undo=build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),j);store.save('plans',undo)
        execute_plan(self.adb,store,self.catalog,undo);self.assertEqual(self.state_of(),0)
        self.assertIn('restore.py',export_recovery(j))
    def test_cancel_and_later_conflict(self):
        p=self.save_plan();stop=threading.Event();stop.set()
        j=execute_plan(self.adb,self.store,self.catalog,p,cancel=stop);self.assertEqual(j['status'],'cancelled');self.assertEqual(self.mutations(),[])
        d=json.loads(self.state.read_text());d['packages']['com.example.optional']['enabled']=2;self.state.write_text(json.dumps(d))
        with self.assertRaises(ValueError):build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),j)
    def test_cancel_after_first_change_leaves_second_pending(self):
        self.adb,self.state=fake_adb(self.root,states={'com.example.optional':0,'com.example.second':0,'android':0})
        self.catalog['profiles'][0]['rules']['com.example.second']=dict(self.catalog['profiles'][0]['rules']['com.example.optional'])
        inv=scan(self.adb,'fixture-tv',self.catalog)
        p=build_plan(inv,{'com.example.optional':'disable','com.example.second':'disable'});self.store.save('plans',p)
        stop=threading.Event()
        def progress(event):
            if event['completed']==1:stop.set()
        # Cancellation requested at the second boundary must not send the second command.
        j=execute_plan(self.adb,self.store,self.catalog,p,on_progress=progress,cancel=stop)
        self.assertEqual(j['status'],'cancelled')
        self.assertEqual([c['outcome'] for c in j['changes']],['successful','pending'])

    def test_missing_live_uid_blocks_all_writes(self):
        p=self.save_plan();d=json.loads(self.state.read_text())
        d['packages']['com.example.optional']['uid']=None;self.state.write_text(json.dumps(d))
        with self.assertRaises(ValueError):execute_plan(self.adb,self.store,self.catalog,p)
        self.assertEqual(self.mutations(),[])
    def test_effective_preview_includes_feature_consequences(self):
        p=self.inv['packages'][0];p.update(features=['casting'],purpose='Optional phone casting',reason='Removes phone casting',evidence=['owned-evidence'])
        plan=self.save_plan();change=plan['changes'][0]
        self.assertEqual(change['features'],['casting']);self.assertEqual(change['reason'],'Removes phone casting')
        self.assertEqual(change['purpose'],'Optional phone casting');self.assertEqual(change['evidence'],['owned-evidence'])
        p['enabled_state']=3;self.assertEqual(build_plan(self.inv,{'com.example.optional':'disable'})['changes'],[])
