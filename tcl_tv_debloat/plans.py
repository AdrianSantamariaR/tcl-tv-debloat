"""Saved previews and exact-state recovery. No uninstall or permission changes."""
import copy,json
from .adb import PACKAGE
from .inventory import record, identity, parse_package, match_guidance

STATES={0:'default-state',1:'enable',2:'disable',3:'disable-user',4:'disable-until-used'}

def same_device(before,now):
    keys=('manufacturer','product','fingerprint')
    if any(not before.get(k) or before[k]!=now.get(k) for k in keys):raise ValueError('TV identity or firmware changed. Scan again.')
    if before.get('hardware_id'):
        if before['hardware_id']!=now.get('hardware_id'):raise ValueError('TV hardware identity changed.')
    elif before.get('serial')!=now.get('serial'):raise ValueError('Target changed; hardware identity is unavailable.')
    if before.get('active_user')!=0 or now.get('active_user')!=0:raise ValueError('Changes require active Android user 0.')

def valid_package(p):
    if not isinstance(p.get('package'),str) or not PACKAGE.fullmatch(p['package']):raise ValueError('Invalid package name.')
    if type(p.get('enabled_state')) is not int or p['enabled_state'] not in STATES or type(p.get('version_code')) is not int or not isinstance(p.get('version_name'),str):raise ValueError('Complete package state and version required.')

def base_plan(inv,mode,source=None):
    same_device(inv['device'],inv['device'])
    if inv.get('errors'):raise ValueError('Inconsistent inventory. Scan again.')
    r=record();r['created_at']=r.pop('captured_at')
    return {**r,'inventory_id':inv['id'],'mode':mode,'source_plan_id':source,'device':copy.deepcopy(inv['device']),'target_user':0,'status':'preview','changes':[],
            'identity_assurance':'hardware ID' if inv['device'].get('hardware_id') else 'Limited: recorded target and firmware only'}

def build_plan(inv,selection):
    if not isinstance(selection,dict):raise ValueError('Selection must be a package-action mapping.')
    plan=base_plan(inv,'apply');packages={p['package']:p for p in inv['packages']}
    for name,action in selection.items():
        if action=='keep':continue
        if action!='disable' or name not in packages:raise ValueError('Invalid package selection.')
        p=packages[name];valid_package(p)
        if not p.get('disable_eligible'):raise ValueError('Package is not eligible for disabling: '+name)
        if p['enabled_state']==3:continue
        plan['changes'].append({'package':name,'version_code':p['version_code'],'version_name':p['version_name'],'before':p['enabled_state'],'after':3,'action':'disable','outcome':'pending','diagnostic':'','features':p.get('features',[]),'purpose':p.get('purpose',''),'reason':p.get('reason',''),'guidance_level':p.get('guidance_level','unknown'),'verification':p.get('verification','unreviewed'),'evidence':p.get('evidence',[])})
    return plan

def build_restore_plan(inv,journal,packages=None):
    if journal.get('mode')!='apply' or journal.get('status')=='preview':raise ValueError('Select a saved apply journal that has started.')
    same_device(journal['device'],inv['device']);plan=base_plan(inv,'restore',journal['id'])
    current={p['package']:p for p in inv['packages']};selected=set(packages) if packages is not None else {c['package'] for c in journal['changes']}
    if not selected.issubset({c['package'] for c in journal['changes']}):raise ValueError('Package is absent from the source journal.')
    for c in journal['changes']:
        if c['package'] not in selected:continue
        p=current.get(c['package'])
        if not p:raise ValueError('Package is no longer installed.')
        valid_package(p)
        if any(p[k]!=c[k] for k in ('version_code','version_name')):raise ValueError('Package version changed.')
        if p['enabled_state'] not in (c['before'],c['after']):raise ValueError('Restore conflict: '+c['package'])
        if p['enabled_state']==c['before']:continue
        plan['changes'].append({**c,'before':p['enabled_state'],'after':c['before'],'action':'restore','outcome':'pending','diagnostic':''})
    return plan

def execute_plan(adb,store,catalog,plan,*,on_progress=None,cancel=None):
    try:saved=store.load('plans',plan['id'])
    except FileNotFoundError:raise ValueError('A saved preview is required.') from None
    if saved['status']=='preview' and saved!=plan:raise ValueError('The saved preview has changed.')
    with store.mutation_lock():
        plan=store.load('plans',plan['id'])
        if plan['status']!='preview':return plan
        if plan.get('schema_version')!=1 or plan.get('target_user')!=0 or plan.get('mode') not in ('apply','restore'):raise ValueError('Invalid plan.')
        serial=plan['device']['serial'];now=identity(adb,serial);same_device(plan['device'],now)
        source=None
        if plan['mode']=='restore':
            source=store.load('plans',plan['source_plan_id'])
            if source.get('mode')!='apply' or source.get('status')=='preview':raise ValueError('Invalid source apply journal.')
            same_device(source['device'],now)
        seen=set()
        for c in plan['changes']:
            p={'package':c['package'],'enabled_state':c['before'],'version_code':c['version_code'],'version_name':c['version_name']};valid_package(p)
            if c['package'] in seen or type(c.get('after')) is not int or c['after'] not in STATES:raise ValueError('Invalid change entry.')
            seen.add(c['package'])
            live=parse_package(c['package'],adb.shell(serial,['dumpsys','package',c['package']]))
            valid_package(live)
            if any(live[k]!=p[k] for k in ('enabled_state','version_code','version_name')):raise ValueError('Stale preview: '+c['package']+'. Scan and preview again.')
            if plan['mode']=='apply':
                if c['action']!='disable' or c['after']!=3 or not match_guidance(live,now,catalog)['disable_eligible']:raise ValueError('Catalog does not allow this change.')
            else:
                matches=[x for x in source['changes'] if x['package']==c['package']]
                if len(matches)!=1 or c['action']!='restore' or c['after']!=matches[0]['before'] or c['before'] not in (matches[0]['before'],matches[0]['after']) or any(c[k]!=matches[0][k] for k in ('version_code','version_name')):raise ValueError('Restore does not match its source journal.')
        journal=copy.deepcopy(plan);journal['status']='running';journal['started_at']=record()['captured_at'];store.save('plans',journal)
        for n,c in enumerate(journal['changes']):
            if cancel and cancel.is_set():journal['status']='cancelled';break
            if c['before']==c['after']:c['outcome']='unchanged';store.save('plans',journal);continue
            if on_progress:on_progress({'stage':'changes','completed':n,'total':len(journal['changes']),'message':'Applying '+c['package']})
            if cancel and cancel.is_set():journal['status']='cancelled';break
            try:
                # Durable pending entry already exists before sending this command.
                adb.shell(serial,['pm',STATES[c['after']],'--user','0',c['package']])
                live=parse_package(c['package'],adb.shell(serial,['dumpsys','package',c['package']]))
                if live['enabled_state']!=c['after']:raise RuntimeError('State verification failed.')
                c['outcome']='successful'
            except (ValueError,RuntimeError) as e:
                c['outcome']='uncertain';c['diagnostic']=str(e);journal['status']='failed';store.save('plans',journal);break
            store.save('plans',journal)
        else:journal['status']='complete'
        journal['finished_at']=record()['captured_at'];store.save('plans',journal);return journal

def export_recovery(journal):
    return {'plan.json':json.dumps(journal,indent=2),'restore.py':"from pathlib import Path\nfrom tcl_tv_debloat.cli import main\nraise SystemExit(main(['restore', '--journal', str(Path(__file__).with_name('plan.json'))]))\n"}
