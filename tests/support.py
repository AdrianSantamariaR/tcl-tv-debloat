import json, sys
from pathlib import Path
from tcl_tv_debloat.adb import Adb

def fake_adb(root: Path, *, states=None):
    root.mkdir(parents=True, exist_ok=True)
    path = root/'state.json'
    packages = {p: {'enabled': e, 'version_code':7, 'version_name':'1.0'} for p,e in (states or {'com.example.optional':0,'android':0}).items()}
    path.write_text(json.dumps({'props': {'ro.build.fingerprint':'fixture/build', 'ro.serialno':'fixture-tv-1','ro.product.manufacturer':'TCL','ro.product.name':'fixture-product','ro.product.model':'Fixture TV','ro.build.version.release':'12'},'user':0,'packages':packages}))
    return Adb([sys.executable, str(Path(__file__).with_name('fake_adb.py'))], env={'TV_FAKE_STATE':str(path)}), path

def fixture_catalog():
    return {'schema_version':1,'packages':{'android':{'label':'Android system','purpose':'Core framework','protected':True}},'profiles':[{'manufacturer':'TCL','product':'fixture-product','fingerprint':'fixture/build','rules':{'com.example.optional':{'version_code':7,'version_name':'1.0','category':'optional','reason':'Optional fixture app','verification':'observed','features':['optional content']}}}]}

def change_state(path, **updates):
    data = json.loads(path.read_text()); data.update(updates); path.write_text(json.dumps(data))
