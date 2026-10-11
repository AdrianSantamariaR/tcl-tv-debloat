import tempfile,unittest,time,json
from pathlib import Path
from tests.support import fake_adb,fixture_catalog,change_state
from tcl_tv_debloat.app import Application
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.rea import Rea

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        self.adb,self.path=fake_adb(root);self.app=Application(self.adb,Store(root/'data'),fixture_catalog(),Rea())
    def wait(self,ident):
        end=time.monotonic()+20
        while self.app.status(ident)['status'] in ('running','pending'):
            if time.monotonic()>end:self.fail('Job failed to finish')
            time.sleep(.05)
        return self.app.status(ident)
    def test_shared_operations_persist_and_previews_are_read_only(self):
        inv=self.app.run('scan',{'serial':'fixture-tv','deep':False})
        self.assertEqual(self.app.store.load('sessions',inv['id']),inv)
        p=self.app.run('preview',{'inventory_id':inv['id'],'selection':{'com.example.optional':'disable'}})
        self.assertNotIn('disable-user',self.path.with_name('commands.jsonl').read_text())
        j=self.app.run('apply',{'plan_id':p['id']});self.assertEqual(j['status'],'complete')
        with self.assertRaises(ValueError):self.app.run('restore',{'plan_id':p['id']})
        with self.assertRaises((ValueError,FileNotFoundError)):self.app.run('apply',{'plan_id':'fake'})
    def test_busy_cancel_progress_and_fixed_payloads(self):
        change_state(self.path,delay=.1)
        ident=self.app.start('scan',{'serial':'fixture-tv','deep':False})
        with self.assertRaises(RuntimeError):self.app.start('scan',{'serial':'fixture-tv','deep':False})
        self.app.cancel(ident);j=self.wait(ident);self.assertEqual(j['status'],'cancelled')
        self.assertIsNotNone(j['result_id']);self.assertEqual(self.app.store.load('sessions',j['result_id'])['status'],'cancelled')
        for operation,payload in [('shell',{'command':'id'}),('scan',{'serial':'fixture-tv','deep':'yes'}),('apply',{'plan_id':'x','changes':[]})]:
            with self.assertRaises(ValueError):self.app.run(operation,payload)

    def test_duplicate_failed_recovery_does_not_report_operation_complete(self):
        inv=self.app.run('scan',{'serial':'fixture-tv','deep':False})
        for status in ('recovery_failed','recovery_invalid'):
            p=self.app.run('preview',{'inventory_id':inv['id'],'selection':{'com.example.optional':'disable'}})
            p.update(status=status,recovery_status='failed');self.app.store.save('plans',p)
            job=self.wait(self.app.start('apply',{'plan_id':p['id']}))
            self.assertEqual(job['status'],'failed')
        self.assertNotIn('disable-user',self.path.with_name('commands.jsonl').read_text())
