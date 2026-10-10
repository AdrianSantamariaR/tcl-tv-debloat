import tempfile,unittest,json,subprocess,sys,os
from pathlib import Path
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.inventory import record

class StoreTests(unittest.TestCase):
    def test_atomic_records_schema_ids_and_cross_process_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp));r=record();s.save('sessions',r);self.assertEqual(s.load('sessions',r['id']),r)
            for ident in ['../../etc/passwd','no-id']:
                with self.assertRaises(ValueError):s.load('sessions',ident)
            with self.assertRaises(ValueError):s.save('plans',{**r,'schema_version':2})
            with s.mutation_lock():
                run=subprocess.run([sys.executable,'-c',"from pathlib import Path; from tcl_tv_debloat.store import Store; s=Store(Path(__import__('sys').argv[1]));\nwith s.mutation_lock(): pass",tmp],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0);self.assertIn('Another operation',run.stderr)
