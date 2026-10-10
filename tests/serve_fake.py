"""Interactive acceptance harness. This process never connects to a real TV."""
import argparse,sys,tempfile,json
from pathlib import Path
from tests.support import fake_adb,fixture_catalog,change_state
from tests.test_rea import ConfiguredRea
from tcl_tv_debloat.adb import Adb
from tcl_tv_debloat.app import Application
from tcl_tv_debloat.store import Store
from tcl_tv_debloat.rea import Rea
from tcl_tv_debloat.server import serve

p=argparse.ArgumentParser();p.add_argument('--scenario',choices=['normal','missing-rea','failed-rea','unknown','partial','slow'],default='missing-rea');p.add_argument('--root');p.add_argument('--port',type=int,default=0);a=p.parse_args()
root=Path(a.root or tempfile.mkdtemp(prefix='tcl-tv-demo-'));state=root/'state.json'
if not state.exists():adb,state=fake_adb(root,states={'com.example.optional':0,'com.example.second':0,'android':0,'unknown.app':0})
else:adb=Adb([sys.executable,str(Path(__file__).with_name('fake_adb.py'))],env={'TV_FAKE_STATE':str(state)})
catalog=fixture_catalog();catalog['packages']['com.example.optional']={'label':'Optional content app','purpose':'Simulated optional entertainment service.'};catalog['profiles'][0]['rules']['com.example.second']=dict(catalog['profiles'][0]['rules']['com.example.optional'])
if a.scenario=='unknown':
 d=json.loads(state.read_text());d['props']['ro.build.fingerprint']='unknown/build';state.write_text(json.dumps(d))
if a.scenario=='partial':change_state(state,fail_package='com.example.second')
if a.scenario=='slow':change_state(state,delay=.2)
rea=Rea(env={'REA_CLI_PATH':'/missing/rea.mjs','REA_JADX_MCP_JAR':'/missing/provider.jar'})
if a.scenario in ('normal','failed-rea'):
 rea=ConfiguredRea([sys.executable,str(Path(__file__).with_name('fake_rea.py'))],env={'REA_FAKE_MODE':'failure' if a.scenario=='failed-rea' else 'success'})
print('SIMULATED TV ONLY; private test data: '+str(root),flush=True)
serve(Application(adb,Store(root/'data'),catalog,rea),open_browser=False,port=a.port)
