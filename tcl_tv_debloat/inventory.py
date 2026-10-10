"""Read-only snapshots and deliberately narrow guidance matching."""
import json, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from .adb import PACKAGE

def record(): return {'schema_version':1,'id':str(uuid.uuid4()),'captured_at':datetime.now(timezone.utc).isoformat()}

def load_catalog():
    root=Path(__file__).parent/'data'
    catalog=json.loads((root/'catalog.json').read_text())
    catalog['profiles']=[json.loads(p.read_text()) for p in sorted((root/'profiles').glob('*.json'))]
    return catalog

def identity(adb, serial):
    props={'hardware_id':'ro.serialno','manufacturer':'ro.product.manufacturer','product':'ro.product.name','model':'ro.product.model','fingerprint':'ro.build.fingerprint','android':'ro.build.version.release'}
    result={'serial':serial}
    for name,prop in props.items(): result[name]=adb.shell(serial,['getprop',prop]) or None
    result['active_user']=int(adb.shell(serial,['am','get-current-user']))
    return result

def parse_package(name, text):
    def find(pattern, convert=str):
        m=re.search(pattern,text,re.M);return convert(m[1]) if m else None
    # Updated system apps also have a factory copy under Hidden system packages.
    # Its version and enabled state do not describe the installed application.
    text=re.split(r'^Hidden system packages:\s*$',text,maxsplit=1,flags=re.M)[0]
    installed=re.search(r'^Packages:\s*$',text,re.M)
    if installed:text=text[installed.end():]
    # Per-package dumps may contain resolver entries before Packages. Use the installed block.
    blocks=list(re.finditer(r'^[ \t]*Package \['+re.escape(name)+r'\].*$',text,re.M))
    if blocks:
        text=text[blocks[-1].start():]
        next_block=re.search(r'\n[ \t]*Package \[',text)
        if next_block:text=text[:next_block.start()]
    users=re.search(r'^[ \t]*User \d+:',text,re.M)
    global_permissions=text[:users.start()] if users else text
    user_zero=re.search(r'^[ \t]*User 0:.*?(?=^[ \t]*User \d+:|\Z)',text,re.M|re.S)
    permission_text=global_permissions+(user_zero[0] if user_zero else '')
    return {'package':name,'version_code':find(r'\bversionCode=(\d+)',int),'version_name':find(r'\bversionName=([^\r\n]+)'),
            'enabled_state':find(r'User 0:[^\r\n]*\benabled=([0-4])\b',int),'uid':find(r'\buserId=(\d+)',int),
            'shared_uid':find(r'\bsharedUser=([^\r\n]+)'), 'granted_permissions':sorted(set(re.findall(r'([\w.]+): granted=true',permission_text))),
            'adb_requested_permissions':re.findall(r'^\s+([\w.]+)\s*$', (text.split('requested permissions:',1)[1].split('install permissions:',1)[0] if 'requested permissions:' in text else ''),re.M),
            'device_paths':[], 'limitations':[], 'evidence':[]}

def match_guidance(package, device, catalog):
    desc=catalog.get('packages',{}).get(package['package'],{})
    result={'label':desc.get('label',package['package']),'purpose':desc.get('purpose','No reviewed description. Leave unchanged until reviewed.'),'features':desc.get('features',[]),
            'category':'protected' if desc.get('protected') or package.get('uid') in (0,1000) or package.get('shared_uid') else ('review' if desc else 'unknown'),
            'disable_eligible':False,'guidance_level':'description' if desc else 'unknown','verification':'unreviewed'}
    for profile in catalog.get('profiles',[]):
        if not all(device.get(k) and device[k]==profile.get(k) for k in ('manufacturer','product','fingerprint')): continue
        rule=profile.get('rules',{}).get(package['package'])
        if not rule or any(package.get(k)!=rule.get(k) or package.get(k) is None for k in ('version_code','version_name')): continue
        if result['category']!='protected': result['category']=rule['category']
        result.update(guidance_level='exact_firmware',verification=rule.get('verification','observed'),features=rule.get('features',result['features']))
        result['reason']=rule.get('reason','')
        result['reviewed_selectors']=rule.get('reviewed_selectors',[])
        result['disable_eligible']=result['category']=='optional' and type(package.get('uid')) is int and package['uid']>=0 and type(package.get('enabled_state')) is int and package['enabled_state'] in range(5) and not package.get('limitations') and device.get('active_user')==0
    return result

def scan(adb, serial, catalog, *, on_progress=None, cancel=None):
    device=identity(adb,serial)
    inv={**record(),'status':'complete','device':device,'coverage':{'installed_packages':0,'scanned_packages':0,'scope':'Android user 0'},'packages':[],'errors':[]}
    names=[]
    for line in adb.shell(serial,['pm','list','packages','--user','0']).splitlines():
        name=line.removeprefix('package:').strip()
        if PACKAGE.fullmatch(name) and name not in names: names.append(name)
        else: inv['errors'].append('Unrecognized package-list entry.');inv['status']='partial'
    inv['coverage']['installed_packages']=len(names)
    for n,name in enumerate(names):
        if cancel and cancel.is_set(): inv['status']='cancelled';break
        if on_progress: on_progress({'stage':'packages','completed':n,'total':len(names),'message':'Reading '+name})
        p=parse_package(name,'')
        try:
            p=parse_package(name,adb.shell(serial,['dumpsys','package',name]))
            p['device_paths']=[s.removeprefix('package:').strip() for s in adb.shell(serial,['pm','path',name]).splitlines() if s.startswith('package:')]
            if any(p[k] is None for k in ('version_code','version_name','enabled_state','uid')): p['limitations'].append('Incomplete package metadata or user 0 state.')
        except (RuntimeError,ValueError) as e: p['limitations'].append(str(e))
        if p['limitations']: inv['status']='partial'
        p.update(match_guidance(p,device,catalog));inv['packages'].append(p)
    inv['coverage']['scanned_packages']=len(inv['packages'])
    if adb.shell(serial,['getprop','ro.build.fingerprint'])!=device['fingerprint']:
        inv['status']='partial';inv['errors'].append('Firmware changed during scan. Scan again.')
        for p in inv['packages']: p['disable_eligible']=False;p['limitations'].append('Inconsistent firmware snapshot.')
    from .privacy import snapshot
    inv['privacy_controls']=snapshot(adb,serial,device,inv['packages'],catalog)
    if inv['errors'] or inv['status']=='cancelled':
        for control in inv['privacy_controls']:control['eligible']=False
    if on_progress: on_progress({'stage':'scan_complete','completed':len(inv['packages']),'total':len(names),'message':'Inventory saved; no changes made.'})
    return inv
