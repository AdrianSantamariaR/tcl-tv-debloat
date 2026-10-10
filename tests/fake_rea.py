import hashlib,json,os,sys,time
from pathlib import Path
mode=os.environ.get('REA_FAKE_MODE','success')
if mode=='delay':time.sleep(5)
if mode=='partial_delay':
    print(json.dumps({'partial_observation':'manifest stage started'}),flush=True)
    print('provider interrupted diagnostic',file=sys.stderr,flush=True)
    if os.environ.get('REA_FAKE_SIGNAL'):Path(os.environ['REA_FAKE_SIGNAL']).write_text('ready')
    time.sleep(5)
if mode=='error_exit':print(json.dumps({'error':'provider_setup_failure','details':{'partial_observation':'cleanup diagnostic'}}));sys.exit(1)
if mode=='failure':print(json.dumps({'error':'Configured engine failed.'}));sys.exit(0)
apk=Path(sys.argv[2]);sha=hashlib.sha256(apk.read_bytes()).hexdigest()
print(json.dumps({'subject':{'digest':{'sha256':'wrong' if mode=='wrong_hash' else sha}},'provider':{'id':'fixture','version':'1'},'normalized_result':{'engine':{'artifact_sha256':'other-jar' if mode=='wrong_engine' else 'fixture-jar'},'package_name':'other.app' if mode=='wrong_package' else 'com.example.optional','version_code':'7','version_name':'1.0','permissions':['android.permission.INTERNET'],'manifest':{'status':'complete','text':'<manifest package="com.example.optional" />'}}}))
