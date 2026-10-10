import unittest,tempfile,json,io
from pathlib import Path
from unittest.mock import patch
from tests.support import fake_adb,fixture_catalog
from tcl_tv_debloat.app import Application
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.rea import Rea
from tcl_tv_debloat.cli import main

class CliTests(unittest.TestCase):
    def test_cli_confirmation_and_browser_share_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);adb,path=fake_adb(root);app=Application(adb,Store(root/'data'),fixture_catalog(),Rea())
            inv=app.run('scan',{'serial':'fixture-tv','deep':False});plan=app.run('preview',{'inventory_id':inv['id'],'selection':{'com.example.optional':'disable'}})
            file=root/'plan.json';file.write_text(json.dumps(plan))
            with patch('tcl_tv_debloat.cli.make_app',return_value=app),patch('builtins.input',return_value='no'),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(main(['apply','--plan',str(file)]),1)
                self.assertEqual(json.loads(path.read_text())['packages']['com.example.optional']['enabled'],0)
                self.assertEqual(main(['apply','--plan',str(file),'--yes']),0)
            self.assertEqual(app.store.load('plans',plan['id'])['status'],'complete')
    def test_packaged_assets_and_guidance_load_from_package(self):
        import tcl_tv_debloat
        from tcl_tv_debloat.inventory import load_catalog
        root=Path(tcl_tv_debloat.__file__).parent
        self.assertEqual(len(load_catalog()['packages']),142)
        for name in ['index.html','app.js','style.css']:self.assertTrue((root/'web'/name).is_file())
