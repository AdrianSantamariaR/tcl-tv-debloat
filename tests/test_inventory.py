import json, tempfile, unittest, threading
from pathlib import Path
from tests.support import fake_adb, fixture_catalog, change_state
from tcl_tv_debloat.inventory import scan, match_guidance, parse_package

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.adb,self.path=fake_adb(Path(self.tmp.name));self.catalog=fixture_catalog()
    def test_read_only_scan_and_exact_firmware_rules(self):
        inv=scan(self.adb,'fixture-tv',self.catalog)
        self.assertEqual(inv['coverage']['installed_packages'],2)
        p=next(p for p in inv['packages'] if p['package']=='com.example.optional')
        self.assertTrue(p['disable_eligible'])
        for key,value in [('fingerprint','other/build'),('manufacturer','Other'),('product','other')]:
            self.assertFalse(match_guidance(p,{**inv['device'],key:value},self.catalog)['disable_eligible'])
        self.assertFalse(match_guidance({**p,'version_code':8},inv['device'],self.catalog)['disable_eligible'])
        self.assertNotIn('disable-user',self.path.with_name('commands.jsonl').read_text())
    def test_missing_state_is_partial_and_blocked(self):
        d=json.loads(self.path.read_text());d['packages']['com.example.optional']['enabled']=None;self.path.write_text(json.dumps(d))
        inv=scan(self.adb,'fixture-tv',self.catalog)
        self.assertEqual(inv['status'],'partial');self.assertFalse(inv['packages'][0]['disable_eligible'])
    def test_scope_missing_hardware_and_cancellation(self):
        d=json.loads(self.path.read_text());d['props']['ro.serialno']='';d['user']=10;self.path.write_text(json.dumps(d))
        inv=scan(self.adb,'fixture-tv',self.catalog)
        self.assertIsNone(inv['device']['hardware_id']);self.assertFalse(inv['packages'][0]['disable_eligible'])
        stop=threading.Event();stop.set()
        inv=scan(self.adb,'fixture-tv',self.catalog,cancel=stop)
        self.assertEqual(inv['status'],'cancelled');self.assertEqual(inv['packages'],[])
    def test_parser_crlf_and_user_scope(self):
        p=parse_package('com.example.optional','versionCode=7 minSdk=23\r\nversionName=1.0\r\nuserId=1000\r\nUser 10: installed=true enabled=1\r\nUser 0: installed=true enabled=0\r\n')
        self.assertEqual(p['enabled_state'],0);self.assertEqual(p['uid'],1000)
    def test_permissions_do_not_leak_from_other_users_or_packages(self):
        text='Package [com.example.optional]:\n userId=10100\n versionCode=7\n versionName=1.0\n install permissions:\n  android.permission.INTERNET: granted=true\n User 0: enabled=0\n  runtime permissions:\n   android.permission.CAMERA: granted=false\n User 10: enabled=1\n   android.permission.CAMERA: granted=true\n Package [other.app]:\n  android.permission.RECORD_AUDIO: granted=true\n'
        p=parse_package('com.example.optional',text)
        self.assertEqual(p['granted_permissions'],['android.permission.INTERNET'])
