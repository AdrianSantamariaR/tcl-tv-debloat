"""Portable simulated device, never contacts ADB or a network."""
import json, os, sys, time
from pathlib import Path
path = Path(os.environ['TV_FAKE_STATE'])
state = json.loads(path.read_text())
args = sys.argv[1:]
with path.with_name('commands.jsonl').open('a') as f: f.write(json.dumps(args)+'\n')
if state.get('delay'): time.sleep(state['delay'])
if args == ['version']: print('Android Debug Bridge version 1.0.41')
elif args[:1] == ['devices']: print('List of devices attached\nfixture-tv\tdevice model:Fixture\nlocked-tv\tunauthorized')
elif args[0] == 'connect': print('connected to '+args[1])
elif args[0] == 'pair': sys.stdin.read(); print('Successfully paired to '+args[1])
elif 'pull' in args:
    if 'overlay' in args[-2]: print('Permission denied', file=sys.stderr); sys.exit(1)
    Path(args[-1]).write_bytes(b'fixture-apk')
else:
    cmd = args[3:]
    if cmd[0] == 'getprop': print(state['props'].get(cmd[1], ''))
    elif cmd == ['am', 'get-current-user']: print(state.get('user', 0))
    elif cmd[:3] == ['pm', 'list', 'packages']: print('\n'.join('package:'+p for p in state['packages']))
    elif cmd[:2] == ['pm', 'path']: print('\n'.join('package:'+p for p in state['packages'][cmd[2]].get('paths', ['/system/app/example.apk'])))
    elif cmd[:2] == ['dumpsys', 'package']:
        p = state['packages'][cmd[2]]
        enabled = '' if p.get('enabled') is None else ' enabled='+str(p['enabled'])
        print('Package ['+cmd[2]+']:\n  userId='+str(p.get('uid', 10100))+'\n  versionCode='+str(p['version_code'])+' minSdk=23\n  versionName='+p['version_name']+'\n  User 0: installed=true hidden=false'+enabled+'\n  runtime permissions:\n    android.permission.INTERNET: granted=true')
    elif cmd[0] == 'pm' and cmd[1] in ['disable-user','default-state','enable','disable','disable-until-used']:
        name = cmd[-1]
        if state.get('fail_package') == name: print('Security exception', file=sys.stderr); sys.exit(1)
        state['packages'][name]['enabled'] = {'default-state':0,'enable':1,'disable':2,'disable-user':3,'disable-until-used':4}[cmd[1]]
        path.write_text(json.dumps(state))
        if state.get('lose_response'): print('Transport closed', file=sys.stderr); sys.exit(1)
        print('Package '+name+' new state')
    else: print('Unsupported fake command: '+str(cmd), file=sys.stderr); sys.exit(1)
