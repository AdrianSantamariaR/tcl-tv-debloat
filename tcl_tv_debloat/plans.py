"""Saved previews and exact-state recovery. No uninstall or permission changes."""
import copy,json
from .adb import PACKAGE
from .privacy import plan_changes, restore_changes, validate_change, read_flags, verify_live_owners
from .inventory import record, identity, parse_package, match_guidance
from .store import recovery_digest, verified_recovery

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

def build_plan(inv,selection,privacy_selection=None):
    if not isinstance(selection,dict):raise ValueError('Selection must be a package-action mapping.')
    plan=base_plan(inv,'apply');packages={p['package']:p for p in inv['packages']}
    for name,action in selection.items():
        if action=='keep':continue
        if action!='disable' or name not in packages:raise ValueError('Invalid package selection.')
        p=packages[name];valid_package(p)
        if not p.get('disable_eligible'):raise ValueError('Package is not eligible for disabling: '+name)
        if p['enabled_state']==3:continue
        plan['changes'].append({'package':name,'label':p.get('label',name),'version_code':p['version_code'],'version_name':p['version_name'],'before':p['enabled_state'],'after':3,'action':'disable','outcome':'pending','diagnostic':'','features':p.get('features',[]),'purpose':p.get('purpose',''),'reason':p.get('reason',''),'guidance_level':p.get('guidance_level','unknown'),'verification':p.get('verification','unreviewed'),'evidence':p.get('evidence',[])})
    settings=plan_changes(inv,privacy_selection)
    if settings:plan['setting_changes']=settings
    return plan

def build_restore_plan(inv,journal,packages=None):
    if journal.get('mode')!='apply' or journal.get('status')=='preview':raise ValueError('Select a saved apply journal that has started.')
    if not verified_recovery(journal):raise ValueError('Select a journal with verified recovery.')
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
    if packages is None:
        settings=restore_changes(inv,journal)
        if settings:plan['setting_changes']=settings
    return plan

def execute_plan(adb,store,catalog,plan,*,on_progress=None,cancel=None):
    try:saved=store.load('plans',plan['id'])
    except FileNotFoundError:raise ValueError('A saved preview is required.') from None
    if saved['status']=='preview' and saved!=plan:raise ValueError('The saved preview has changed.')
    with store.mutation_lock():
        plan=store.load('plans',plan['id'])
        if plan['status']!='preview':return plan
        if plan.get('schema_version')!=1 or plan.get('target_user')!=0 or plan.get('mode') not in ('apply','restore'):raise ValueError('Invalid plan.')
        if on_progress:on_progress({'stage':'preflight','completed':0,'total':None,'message':'Checking TV identity, firmware and original states…'})
        serial=plan['device']['serial'];now=identity(adb,serial);same_device(plan['device'],now)
        source=None
        if plan['mode']=='restore':
            source=store.load('plans',plan['source_plan_id'])
            if source.get('mode')!='apply' or source.get('status')=='preview':raise ValueError('Invalid source apply journal.')
            if not verified_recovery(source):raise ValueError('Select a journal with verified recovery.')
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
        settings=plan.get('setting_changes',[])
        if not isinstance(settings,list):raise ValueError('Invalid privacy changes.')
        seen_controls=set()
        flags=read_flags(adb,serial) if settings else {}
        for c in settings:
            ident=validate_change(c,plan['mode'])
            if ident in seen_controls:raise ValueError('Duplicate privacy control.')
            seen_controls.add(ident)
            verify_live_owners(adb,serial,c,now,catalog)
            if flags[c['key']]!=c['before']:raise ValueError('Stale privacy preview: '+ident+'. Scan and preview again.')
            if source is not None:
                matches=[x for x in source.get('setting_changes',[]) if x.get('control_id')==ident]
                if len(matches)!=1:raise ValueError('Restore does not match its source privacy journal.')
                original=matches[0];validate_change(original,'apply')
                if c['after']!=original['before'] or c['before'] not in (original['before'],original['after']) or c['owner_versions']!=original['owner_versions']:raise ValueError('Restore does not match its source privacy journal.')
        journal=copy.deepcopy(plan);journal['status']='running';journal['started_at']=record()['captured_at']
        journal['recovery_status']='pending'
        journal['recovery_digest']=recovery_digest(journal)
        if on_progress:on_progress({'stage':'recovery','completed':0,'total':None,'message':'Saving the original states on this computer…'})
        try:
            store.save_verified('plans',journal)
            journal['recovery_status']='verified';journal['recovery_saved_at']=record()['captured_at']
            store.save_verified('plans',journal)
        except RuntimeError as error:
            journal['status']='recovery_failed';journal['recovery_status']='failed'
            journal.pop('recovery_saved_at',None);journal['recovery_error']=str(error)
            try:store.save('plans',journal)
            except (OSError,ValueError):pass  # Loading still rejects unchecked or damaged records.
            raise
        if on_progress:on_progress({'stage':'recovery_saved','completed':0,'total':None,'message':'Recovery point saved and checked. Ready to make changes.'})
        work=[('package',c) for c in journal['changes']]+[('setting',c) for c in journal.get('setting_changes',[])]
        verb='Restoring ' if plan['mode']=='restore' else 'Applying '
        for n,(kind,c) in enumerate(work):
            if cancel and cancel.is_set():journal['status']='cancelled';break
            if c['before']==c['after']:c['outcome']='unchanged';store.save('plans',journal);continue
            label=c.get('label') or c.get('package') or c['control_id']
            if on_progress:on_progress({'stage':'changes','completed':n,'total':len(work),'message':verb+label})
            if cancel and cancel.is_set():journal['status']='cancelled';break
            try:
                # Durable pending entry already exists before sending this command.
                if kind=='package':
                    adb.shell(serial,['pm',STATES[c['after']],'--user','0',c['package']])
                    if on_progress:on_progress({'stage':'verification','completed':n,'total':len(work),'message':'Checking the resulting state of '+label})
                    live=parse_package(c['package'],adb.shell(serial,['dumpsys','package',c['package']]))
                    if live['enabled_state']!=c['after']:raise RuntimeError('State verification failed.')
                else:
                    same_device(plan['device'],identity(adb,serial))
                    verify_live_owners(adb,serial,c,now,catalog)
                    if read_flags(adb,serial)[c['key']]!=c['before']:raise ValueError('Stale privacy setting before mutation.')
                    args=['settings','--user','0','delete' if c['after'] is None else 'put','global',c['key']]
                    if c['after'] is not None:args.append(c['after'])
                    adb.shell(serial,args)
                    if on_progress:on_progress({'stage':'verification','completed':n,'total':len(work),'message':'Checking the resulting value of '+label})
                    if read_flags(adb,serial)[c['key']]!=c['after']:raise RuntimeError('Privacy setting verification failed.')
                c['outcome']='successful'
            except (ValueError,RuntimeError) as e:
                c['outcome']='uncertain';c['diagnostic']=str(e);journal['status']='failed';store.save('plans',journal);break
            store.save('plans',journal)
            if on_progress:on_progress({'stage':'change_complete','completed':n+1,'total':len(work),'message':label+' verified.'})
        else:journal['status']='complete'
        journal['finished_at']=record()['captured_at'];store.save('plans',journal)
        if on_progress:on_progress({'stage':journal['status'],'completed':sum(c['outcome'] in ('successful','unchanged') for _,c in work),'total':len(work),'message':'Changes verified and saved.' if journal['status']=='complete' else 'Stopped. Recovery is saved; review the recorded outcomes.'})
        return journal

def export_recovery(journal):
    if journal.get('mode')!='apply' or not verified_recovery(journal):raise ValueError('Choose an apply journal with verified recovery.')
    return {'plan.json':json.dumps(journal,indent=2),'restore.py':"from pathlib import Path\nfrom tcl_tv_debloat.cli import main\nraise SystemExit(main(['restore', '--journal', str(Path(__file__).with_name('plan.json'))]))\n"}
