import copy,json,tempfile,threading,unittest
from pathlib import Path
from tests.support import fake_adb,fixture_catalog,change_state
from tcl_tv_debloat.inventory import scan
from tcl_tv_debloat.plans import build_plan,build_restore_plan,execute_plan
from tcl_tv_debloat.store import Store

IDS=['tcl_bi_reporting','tcl_diagnostics']
KEYS=['gdpr_user_action','tcl_diagnostic_status']

def privacy_fixture(catalog,state):
    d=json.loads(state.read_text())
    for name in ['com.tcl.ttvs','com.tcl.useragreement']:
        d['packages'][name]={'enabled':0,'version_code':7,'version_name':'1.0','uid':1000}
        catalog['profiles'][0]['rules'][name]={'version_code':7,'version_name':'1.0','category':'protected'}
    catalog['profiles'][0]['privacy_controls']=IDS
    d['settings']={};state.write_text(json.dumps(d))

class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.adb,self.state=fake_adb(self.root)
        self.catalog=fixture_catalog();privacy_fixture(self.catalog,self.state)
        self.store=Store(self.root/'data')
    def scan(self):return scan(self.adb,'fixture-tv',self.catalog)
    def preview(self,ids=IDS,packages=None):
        p=build_plan(self.scan(),packages or {},privacy_selection=ids);self.store.save('plans',p);return p
    def execute(self,p):return execute_plan(self.adb,self.store,self.catalog,p)
    def settings(self):return json.loads(self.state.read_text())['settings']
    def writes(self):
        return [json.loads(x) for x in self.state.with_name('commands.jsonl').read_text().splitlines() if 'put' in json.loads(x) or 'delete' in json.loads(x) or 'disable-user' in json.loads(x)]
    def test_scan_reads_only_known_flags_and_no_default_selection(self):
        inv=self.scan();self.assertEqual(len(inv['privacy_controls']),2)
        self.assertTrue(all(c['eligible'] and c['current_value'] is None for c in inv['privacy_controls']))
        self.assertEqual(build_plan(inv,{ }).get('setting_changes',[]),[]);self.assertEqual(self.writes(),[])
    def test_restore_exact_values_and_absence_without_replay(self):
        for original in [None,'1','0']:
            change_state(self.state,settings={} if original is None else {k:original for k in KEYS})
            p=self.preview();j=self.execute(p);self.assertEqual(j['status'],'complete')
            self.assertEqual(len(j.get('setting_changes',[])),0 if original=='0' else 2)
            before=len(self.writes());self.execute(p);self.assertEqual(before,len(self.writes()))
            undo=build_restore_plan(self.scan(),j);self.store.save('plans',undo);self.execute(undo)
            self.assertEqual(self.settings(),{} if original is None else {k:original for k in KEYS})
    def test_stale_flags_block_mixed_package_changes_before_any_write(self):
        p=self.preview(packages={'com.example.optional':'disable'})
        change_state(self.state,settings={'gdpr_user_action':'1'})
        with self.assertRaisesRegex(ValueError,'Stale'):self.execute(p)
        self.assertEqual(self.writes(),[])
    def test_unsupported_firmware_owner_versions_invalid_values_and_read_failure(self):
        for case in ['firmware','owner','value','read']:
            original=self.state.read_text();d=json.loads(original)
            if case=='firmware':d['props']['ro.build.fingerprint']='different'
            elif case=='owner':d['packages']['com.tcl.ttvs']['version_code']=8
            elif case=='value':d['settings']={'gdpr_user_action':'null'}
            else:d['fail_settings_read']=True
            self.state.write_text(json.dumps(d));inv=self.scan()
            with self.assertRaises(ValueError):build_plan(inv,{},privacy_selection=['tcl_bi_reporting'])
            self.assertEqual(self.writes(),[]);self.state.write_text(original)
    def test_forged_keys_ids_values_and_duplicate_rows_block_writes(self):
        for field,value in [('key','other_setting'),('namespace','secure'),('control_id','unknown'),('after','1'),('before','null')]:
            p=self.preview();p['setting_changes'][0][field]=value;self.store.save('plans',p)
            with self.assertRaises(ValueError):self.execute(p)
        p=self.preview();p['setting_changes'].append(copy.deepcopy(p['setting_changes'][0]));self.store.save('plans',p)
        with self.assertRaises(ValueError):self.execute(p)
        for ids in [['unknown'],[IDS[0],IDS[0]],'tcl_bi_reporting']:
            with self.assertRaises(ValueError):build_plan(self.scan(),{},privacy_selection=ids)
        self.assertEqual(self.writes(),[])
    def test_loss_of_response_is_recoverable_and_later_conflicts_rejected(self):
        p=self.preview();change_state(self.state,lose_settings_response=True)
        j=self.execute(p);self.assertEqual(j['status'],'failed');self.assertEqual(j['setting_changes'][0]['outcome'],'uncertain')
        self.assertEqual(self.settings()['gdpr_user_action'],'0')
        change_state(self.state,lose_settings_response=False)
        undo=build_restore_plan(self.scan(),j);self.store.save('plans',undo);self.execute(undo);self.assertEqual(self.settings(),{})
        p=self.preview();j=self.execute(p);change_state(self.state,settings={'gdpr_user_action':'1','tcl_diagnostic_status':'0'})
        with self.assertRaises(ValueError):build_restore_plan(self.scan(),j)
    def test_cancel_second_setting_and_package_subset_does_not_restore_flags(self):
        p=self.preview();stop=threading.Event()
        def progress(e):
            if e['completed']==1:stop.set()
        j=execute_plan(self.adb,self.store,self.catalog,p,on_progress=progress,cancel=stop)
        self.assertEqual(j['status'],'cancelled');self.assertEqual([c['outcome'] for c in j['setting_changes']],['successful','pending'])
        subset=build_restore_plan(self.scan(),j,packages=[]);self.assertEqual(subset.get('setting_changes',[]),[])
    def test_live_owner_update_and_read_failure_block_before_package_mutation(self):
        for case in ['owner','read']:
            p=self.preview(packages={'com.example.optional':'disable'});original=self.state.read_text();d=json.loads(original)
            if case=='owner':d['packages']['com.tcl.ttvs']['version_name']='other'
            else:d['fail_settings_read']=True
            self.state.write_text(json.dumps(d))
            with self.assertRaises((ValueError,RuntimeError)):self.execute(p)
            self.assertEqual(self.writes(),[]);self.state.write_text(original)
    def test_write_failure_stops_and_recheck_before_second_setting(self):
        p=self.preview();change_state(self.state,fail_settings_write=True)
        j=self.execute(p);self.assertEqual(j['status'],'failed');self.assertEqual(self.settings(),{})
        self.assertEqual([c['outcome'] for c in j['setting_changes']],['uncertain','pending'])
        change_state(self.state,fail_settings_write=False)
        p=self.preview();before=len(self.writes())
        def changed_during_execution(e):
            if e['completed']==1:change_state(self.state,settings={'gdpr_user_action':'0','tcl_diagnostic_status':'1'})
        j=execute_plan(self.adb,self.store,self.catalog,p,on_progress=changed_during_execution)
        self.assertEqual(j['status'],'failed');self.assertEqual(len(self.writes()),before+1)
        self.assertEqual(self.settings()['tcl_diagnostic_status'],'1')
    def test_optional_api_and_cli_selection_share_saved_engine(self):
        import io
        from unittest.mock import patch
        from tcl_tv_debloat.app import Application
        from tcl_tv_debloat.cli import main
        from tcl_tv_debloat.rea import Rea
        app=Application(self.adb,self.store,self.catalog,Rea());inv=app.run('scan',{'serial':'fixture-tv','deep':False})
        for invalid in ['tcl_bi_reporting',[1],{'key':'gdpr_user_action'}]:
            with self.assertRaises(ValueError):app.run('preview',{'inventory_id':inv['id'],'selection':{},'privacy_selection':invalid})
        inv_file=self.root/'inventory.json';inv_file.write_text(json.dumps(inv));out=self.root/'preview.json'
        with patch('tcl_tv_debloat.cli.make_app',return_value=app),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(main(['preview','--inventory',str(inv_file),'--privacy',IDS[0],'--out',str(out)]),0)
        p=json.loads(out.read_text());self.assertEqual(p['changes'],[]);self.assertEqual(len(p['setting_changes']),1)
        self.assertEqual(self.writes(),[]);j=app.run('apply',{'plan_id':p['id']});self.assertEqual(j['status'],'complete')
        inv=app.run('scan',{'serial':'fixture-tv','deep':False});undo=app.run('restore_preview',{'inventory_id':inv['id'],'source_plan_id':j['id']})
        self.assertEqual(app.run('restore',{'plan_id':undo['id']})['status'],'complete');self.assertEqual(self.settings(),{})
    def test_settings_command_error_with_zero_exit_status_is_not_absence(self):
        for output in ['Error while accessing settings provider','']:
            change_state(self.state,settings_read_stdout=output)
            inv=self.scan()
            self.assertTrue(all(c['read_status']=='failed' and not c['eligible'] for c in inv['privacy_controls']))
            with self.assertRaises(ValueError):build_plan(inv,{},privacy_selection=IDS)
        self.assertEqual(self.writes(),[])
