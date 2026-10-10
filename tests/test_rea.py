import json,sys,tempfile,threading,unittest
from pathlib import Path
from tests.support import fake_adb,fixture_catalog
from tcl_tv_debloat.inventory import scan
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.rea import Rea,check_prerequisites,analyze_inventory,node_compatible

class ConfiguredRea(Rea):
    def identity(self):return {'configured':True,'version':'fixture','jar_sha256':'fixture-jar','node':'26.0.0','java':'21','dependencies':[]}

class ReaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rea space ');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.adb,self.path=fake_adb(self.root);self.inv=scan(self.adb,'fixture-tv',fixture_catalog());self.store=Store(self.root/'data')
        self.rea=ConfiguredRea([sys.executable,str(Path(__file__).with_name('fake_rea.py'))],env={'REA_FAKE_MODE':'failure'})
    def test_configured_failure_retains_inventory(self):
        ready=check_prerequisites(self.adb,self.rea);self.assertTrue(ready['deep_configured']);self.assertFalse(ready['engine_execution_verified'])
        r=analyze_inventory(self.adb,self.rea,self.store,self.inv)
        self.assertEqual(r['coverage']['rea_successful'],0);self.assertEqual(len(r['packages']),2)
    def test_hash_binding_package_mismatch_splits_and_verified_execution(self):
        self.rea.env['REA_FAKE_MODE']='success'
        self.inv['packages']=self.inv['packages'][:1];self.inv['packages'][0]['device_paths']=['/system/base.apk','/system/split_config.en.apk']
        r=analyze_inventory(self.adb,self.rea,self.store,self.inv)
        self.assertEqual(r['coverage']['rea_successful'],1);self.assertTrue(self.rea.execution_verified)
        self.assertIn('base APK only',r['packages'][0]['analysis']['coverage'])
        for mode in ['wrong_hash','wrong_package']:
            self.rea.env['REA_FAKE_MODE']=mode;self.rea.execution_verified=False
            self.rea.identity=lambda:{'configured':True,'version':mode,'jar_sha256':'changed','dependencies':[]}
            r=analyze_inventory(self.adb,self.rea,self.store,self.inv)
            self.assertEqual(r['coverage']['rea_successful'],0);self.assertFalse(self.rea.execution_verified)
    def test_unreadable_overlay_and_cancel_timeout(self):
        self.inv['packages'][0]['device_paths']=['/product/overlay/test.apk']
        r=analyze_inventory(self.adb,self.rea,self.store,self.inv);self.assertEqual(r['packages'][0]['analysis']['status'],'failed')
        apk=self.root/'input.apk';apk.write_bytes(b'test');self.rea.env['REA_FAKE_MODE']='delay';self.rea.timeout=.1
        with self.assertRaises(RuntimeError):self.rea.inspect_package(apk)
        stop=threading.Event();stop.set()
        with self.assertRaises(RuntimeError):self.rea.inspect_package(apk,cancel=stop)
        r=analyze_inventory(self.adb,self.rea,self.store,self.inv,cancel=stop);self.assertEqual(r['coverage']['rea_status'],'cancelled')
    def test_metadata_node_range_and_missing_dependencies(self):
        for version,want in [('22.19.0',True),('22.18.0',False),('23.0.0',False),('24.11.0',True),('25.0.0',False),('26.1.0',True)]:
            self.assertEqual(node_compatible(version,'^22.19.0 || ^24.11.0 || >=26.0.0'),want)
        with self.assertRaises(ValueError):node_compatible('26.0.0','~26')
        rea=Rea(env={'PATH':'','JAVA_HOME':'/missing-jdk','REA_JADX_MCP_JAR':'/missing.jar','REA_CLI_PATH':'/missing.mjs'})
        self.assertFalse(check_prerequisites(self.adb,rea)['deep_configured'])
    def test_unconfigured_optional_tools_do_not_report_missing_or_block_standard(self):
        rea=Rea(env={'PATH':'','JAVA_HOME':'/missing-jdk','REA_CLI_PATH':'','REA_JADX_MCP_JAR':''})
        ready=check_prerequisites(self.adb,rea)
        self.assertTrue(ready['standard_ready'])
        rows={d['name']:d for d in ready['dependencies']}
        self.assertEqual(rows['Node.js + REA']['status'],'needs_configuration')
        self.assertEqual(rows['JADX provider JAR']['status'],'needs_configuration')
        self.assertEqual(rows['ADB']['required_for'],'standard')
        self.assertEqual(rows['Java JDK']['required_for'],'deep')
    def test_failed_adb_probe_does_not_claim_its_path_is_missing(self):
        from tcl_tv_debloat.adb import Adb
        adb=Adb([sys.executable,'-c','import sys; sys.exit(1)'])
        ready=check_prerequisites(adb,self.rea)
        self.assertFalse(ready['standard_ready'])
        self.assertEqual(ready['dependencies'][0]['status'],'unavailable')
    def test_full_jdk_compiler_and_jar_checks(self):
        import zipfile
        from unittest.mock import patch
        root=self.root/'rea-agents';(root/'scripts').mkdir(parents=True)
        (root/'scripts'/'rea.mjs').write_text('');(root/'package.json').write_text(json.dumps({'version':'6.3.0','engines':{'node':'>=26.0.0'}}))
        jar=self.root/'provider.jar'
        with zipfile.ZipFile(jar,'w') as z:z.writestr('jadx/api/JadxDecompiler.class',b'fixture')
        rea=Rea(env={'REA_CLI_PATH':str(root/'scripts'/'rea.mjs'),'REA_JADX_MCP_JAR':str(jar)})
        with patch('tcl_tv_debloat.rea.probe',side_effect=['v26.0.0','java.base@21\njdk.compiler@21']):self.assertTrue(rea.identity()['configured'])
        with patch('tcl_tv_debloat.rea.probe',side_effect=['v26.0.0','java.base@21']):self.assertFalse(rea.identity()['configured'])
    def test_evidence_from_another_engine_is_not_attached_or_cached(self):
        self.inv['packages']=self.inv['packages'][:1];self.rea.env['REA_FAKE_MODE']='wrong_engine'
        result=analyze_inventory(self.adb,self.rea,self.store,self.inv)
        self.assertEqual(result['coverage']['rea_successful'],0)
        self.assertFalse(self.rea.execution_verified);self.assertEqual(self.store.list('evidence'),[])
    def test_nonzero_provider_response_preserves_diagnostics(self):
        self.rea.env['REA_FAKE_MODE']='error_exit';apk=self.root/'error.apk';apk.write_bytes(b'fixture')
        with self.assertRaisesRegex(RuntimeError,'provider_setup_failure'):self.rea.inspect_package(apk)

    def test_timeout_and_last_package_cancellation_preserve_partial_diagnostics(self):
        import time
        self.inv['packages']=self.inv['packages'][:1]
        self.rea.env['REA_FAKE_MODE']='partial_delay';self.rea.timeout=.3
        result=analyze_inventory(self.adb,self.rea,self.store,self.inv)
        analysis=result['packages'][0]['analysis']
        evidence=self.store.load('evidence',analysis['partial_evidence_id'])
        self.assertIn('manifest stage started',json.dumps(evidence['observation']))
        self.assertIn('provider interrupted diagnostic',json.dumps(evidence['observation']))
        ready=self.root/'ready';self.rea.env['REA_FAKE_SIGNAL']=str(ready);self.rea.timeout=5
        stop=threading.Event()
        def cancel_after_output():
            deadline=time.monotonic()+4
            while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
            stop.set()
        worker=threading.Thread(target=cancel_after_output);worker.start()
        result=analyze_inventory(self.adb,self.rea,self.store,self.inv,cancel=stop);worker.join()
        self.assertEqual(result['coverage']['rea_status'],'cancelled')
        self.assertIn('partial_evidence_id',result['packages'][0]['analysis'])
