import json, tempfile, unittest, sys
from pathlib import Path
from tcl_tv_debloat.adb import Adb
from tests.support import fake_adb

class AdbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tv test ')
        self.addCleanup(self.tmp.cleanup)
        self.adb, self.state = fake_adb(Path(self.tmp.name))
    def test_connected_and_unauthorised_devices_are_distinct(self):
        self.assertEqual([x['state'] for x in self.adb.devices()], ['device', 'unauthorized'])
    def test_address_cannot_be_an_adb_option(self):
        for address in ['--help', 'localhost:5555', '1.2.3.4:0', '1.2.3.4:5555;id']:
            with self.assertRaises(ValueError): self.adb.connect(address)
        self.assertFalse(self.state.with_name('commands.jsonl').exists())
    def test_numeric_addresses_and_pairing_secret(self):
        self.adb.connect('[::1]:5555')
        self.adb.pair('192.168.0.2:3333', '123456')
        self.assertNotIn('123456', self.state.with_name('commands.jsonl').read_text())
    def test_unknown_serial_and_shell_metacharacters_rejected(self):
        with self.assertRaises(ValueError): self.adb.shell('--help', ['id'])
        with self.assertRaises(ValueError): self.adb.shell('fixture-tv', ['echo', 'x;id'])
    def test_missing_adb_and_timeout_are_bounded(self):
        with self.assertRaises(RuntimeError): Adb(['missing-executable-for-tv-test']).version()
        with self.assertRaises(RuntimeError): Adb([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=.1).version()
    def test_pull_path_with_spaces(self):
        dest = Path(self.tmp.name)/'app with spaces.apk'
        self.adb.pull('fixture-tv', '/system/app/example.apk', dest)
        self.assertEqual(dest.read_bytes(), b'fixture-apk')
