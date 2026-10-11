import json,tempfile,threading,unittest,copy
from unittest.mock import patch
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

    def test_unreadable_or_changed_recovery_blocks_apply_and_restore(self):
        # A damaged disk record must never be followed by a TV write.
        for mode in ('apply','restore'):
            for damage in ('unreadable','changed','write_failure'):
                with self.subTest(mode=mode,damage=damage):
                    change_state(self.state,packages={'com.example.optional':{'enabled':0,'version_code':7,'version_name':'1.0'},'android':{'enabled':0,'version_code':7,'version_name':'1.0'}})
                    plan=self.save_plan(scan(self.adb,'fixture-tv',self.catalog))
                    if mode=='restore':
                        journal=execute_plan(self.adb,self.store,self.catalog,plan)
                        plan=build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),journal)
                        self.store.save('plans',plan)
                    count=len(self.mutations());before=self.state_of();save=self.store.save
                    def damaged_save(kind,value):
                        if value.get('status')!='running':return save(kind,value)
                        if damage=='write_failure':raise OSError('disk unavailable')
                        ident=save(kind,value)
                        dest=self.root/'data'/kind/(ident+'.json')
                        if damage=='unreadable':dest.write_text('{partial')
                        else:
                            broken=json.loads(dest.read_text());broken['changes'][0]['before']=42
                            dest.write_text(json.dumps(broken))
                        return ident
                    with patch.object(self.store,'save',side_effect=damaged_save):
                        with self.assertRaisesRegex(RuntimeError,'Recovery point'):
                            execute_plan(self.adb,self.store,self.catalog,plan)
                    self.assertEqual(self.state_of(),before)
                    self.assertEqual(len(self.mutations()),count)
                    failed=self.store.load('plans',plan['id'])
                    self.assertEqual(failed['status'],'recovery_failed')
                    with self.assertRaises(ValueError):
                        build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),failed)

    def test_unverified_recovery_record_cannot_be_used_to_restore(self):
        # Catches treating a record saved before its readback as a usable backup.
        pending={**self.save_plan(),'status':'running','recovery_status':'pending'}
        with self.assertRaisesRegex(ValueError,'verified recovery'):
            build_restore_plan(self.inv,pending)

    def test_restore_rechecks_recovery_source_before_mutation(self):
        journal=execute_plan(self.adb,self.store,self.catalog,self.save_plan())
        undo=build_restore_plan(scan(self.adb,'fixture-tv',self.catalog),journal)
        self.store.save('plans',undo)
        count=len(self.mutations())
        journal['recovery_status']='pending';self.store.save('plans',journal)
        with self.assertRaisesRegex(ValueError,'verified recovery'):
            execute_plan(self.adb,self.store,self.catalog,undo)
        self.assertEqual(len(self.mutations()),count)
        self.assertEqual(self.state_of(),3)

    def test_second_recovery_write_damage_and_failed_error_save_blocks_restore(self):
        # A failed error write must not make a damaged "verified" candidate usable.
        plan=self.save_plan();save=self.store.save
        def damaged_save(kind,value):
            if value.get('status')=='recovery_failed':raise OSError('disk unavailable')
            ident=save(kind,value)
            if value.get('recovery_status')=='verified':
                dest=self.root/'data'/kind/(ident+'.json')
                broken=json.loads(dest.read_text())
                broken['changes'][0].update(before=2,after=0)
                dest.write_text(json.dumps(broken))
            return ident
        with patch.object(self.store,'save',side_effect=damaged_save):
            with self.assertRaisesRegex(RuntimeError,'Recovery point'):
                execute_plan(self.adb,self.store,self.catalog,plan)
        self.assertEqual(self.mutations(),[])
        raw=json.loads((self.root/'data'/'plans'/(plan['id']+'.json')).read_text())
        with self.assertRaisesRegex(ValueError,'verified recovery'):
            build_restore_plan(self.inv,raw)
        invalid=self.store.load('plans',plan['id'])
        self.assertEqual(invalid['recovery_status'],'failed')
        with self.assertRaises(ValueError):export_recovery(raw)

    def test_recovery_checksum_required_for_new_records_but_legacy_is_compatible(self):
        journal=execute_plan(self.adb,self.store,self.catalog,self.save_plan())
        inv=scan(self.adb,'fixture-tv',self.catalog)
        for damage in ('missing_digest','missing_status','original_state','setting_entry'):
            broken=copy.deepcopy(journal)
            if damage=='missing_digest':broken.pop('recovery_digest')
            elif damage=='missing_status':broken.pop('recovery_status')
            elif damage=='original_state':broken['changes'][0]['before']=2
            else:broken['setting_changes']=[{'control_id':'added','before':'1','after':'0'}]
            with self.subTest(damage=damage):
                with self.assertRaisesRegex(ValueError,'verified recovery'):build_restore_plan(inv,broken)
                with self.assertRaises(ValueError):export_recovery(broken)
                self.store.save('plans',broken)
                self.assertEqual(self.store.load('plans',broken['id'])['status'],'recovery_invalid')
        legacy=copy.deepcopy(journal);legacy.pop('recovery_digest');legacy.pop('recovery_status')
        self.assertEqual(build_restore_plan(inv,legacy)['changes'][0]['after'],0)

    def test_progress_reports_checked_recovery_and_verified_completion(self):
        # Catches a finished counter emitted before a TV state is read back.
        plan=self.save_plan();events=[]
        def progress(event):
            events.append(dict(event))
            if event['stage']=='recovery_saved':
                saved=self.store.load('plans',plan['id'])
                self.assertEqual(saved['changes'][0]['before'],0)
                self.assertEqual(self.mutations(),[])
            if event['stage']=='change_complete':self.assertEqual(self.state_of(),3)
        journal=execute_plan(self.adb,self.store,self.catalog,plan,on_progress=progress)
        self.assertEqual(journal['status'],'complete')
        self.assertIn('recovery_saved_at',journal)
        self.assertEqual([e['stage'] for e in events],['preflight','recovery','recovery_saved','changes','verification','change_complete','complete'])
        self.assertEqual(events[-1]['completed'],1)
        self.assertEqual(events[-1]['total'],1)

    def test_cancellation_during_preflight_never_changes_tv(self):
        # Catches ignoring Stop while checking the TV before saving recovery.
        stop=threading.Event()
        def progress(event):
            if event['stage']=='preflight':stop.set()
        journal=execute_plan(self.adb,self.store,self.catalog,self.save_plan(),on_progress=progress,cancel=stop)
        self.assertEqual(journal['status'],'cancelled')
        self.assertEqual(self.mutations(),[])
