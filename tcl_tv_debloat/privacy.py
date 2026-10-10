"""Two reviewed TCL consent flags. This is not a general settings editor."""
import copy

CONTROLS={
    'tcl_bi_reporting':{
        'key':'gdpr_user_action','label':'TCL BI reporting',
        'purpose':'Close the reviewed TCL BI SDK consent gate.',
        'reason':'The reviewed SDK defaults to allowing reporting when this flag is absent. Its GDPR interceptor blocks its reporting path when the flag is 0.',
        'features':['TCL BI usage reporting; other senders and queued data are not covered'],
        'owners':['com.tcl.ttvs'],
        'evidence':['TTVS DeviceUtils.getGDPR: Global.getInt(gdpr_user_action, 1); DataReport observer; GDPRInterceptor.shouldIntercept. Static audit 2026-10-10.']},
    'tcl_diagnostics':{
        'key':'tcl_diagnostic_status','label':'TCL diagnostics',
        'purpose':'Disable the reviewed TCL diagnostic consent flag.',
        'reason':'The TCL consent API writes this flag and the reviewed TTVS diagnostic collector checks consent before starting. This does not cover every log or Google sender.',
        'features':['TCL diagnostic collection in the reviewed path'],
        'owners':['com.tcl.ttvs','com.tcl.useragreement'],
        'evidence':['UserAgreement OverseaApiImpl.setDiagnosticStatus; ConfigConst.DIAGNOSTIC_ENABLE; TTVS diagnostic collector. Static audit 2026-10-10.']}}


def read_flags(adb,serial):
    # A list preserves absence; settings get would confuse an absent key with literal "null".
    result={d['key']:None for d in CONTROLS.values()};seen=set()
    output=adb.shell(serial,['settings','--user','0','list','global'])
    if not output:raise ValueError('Global settings could not be read; absence is not established.')
    for line in output.splitlines():
        key,sep,value=line.partition('=')
        if not sep or not key:raise ValueError('Unexpected global settings response; absence is not established.')
        if key not in result:continue
        if not sep or key in seen:raise ValueError('Ambiguous TCL privacy setting.')
        seen.add(key);result[key]=value
    return result


def reviewed_owners(control_id,device,packages,catalog):
    definition=CONTROLS[control_id];current={p['package']:p for p in packages}
    if device.get('active_user')!=0:return None
    for profile in catalog.get('profiles',[]):
        if control_id not in profile.get('privacy_controls',[]):continue
        if not all(device.get(k) and device[k]==profile.get(k) for k in ('manufacturer','product','fingerprint')):continue
        versions={}
        for name in definition['owners']:
            p=current.get(name,{});rule=profile.get('rules',{}).get(name,{})
            if p.get('limitations') or any(p.get(k) is None or p[k]!=rule.get(k) for k in ('version_code','version_name')):break
            versions[name]={k:p[k] for k in ('version_code','version_name')}
        else:return versions
    return None


def snapshot(adb,serial,device,packages,catalog):
    diagnostic=''
    try:flags=read_flags(adb,serial)
    except (RuntimeError,ValueError) as e:flags={};diagnostic=str(e)
    result=[]
    for ident,definition in CONTROLS.items():
        versions=reviewed_owners(ident,device,packages,catalog)
        value=flags.get(definition['key']);valid=not diagnostic and value in (None,'0','1')
        result.append({**copy.deepcopy(definition),'control_id':ident,'namespace':'global','target_value':'0',
            'current_value':value,'read_status':'complete' if valid else 'failed',
            'diagnostic':diagnostic or ('' if valid else 'Unrecognized setting value; leave unchanged.'),
            'eligible':versions is not None and valid,'owner_versions':versions or {},
            'guidance_level':'exact_firmware' if versions is not None else 'unknown','verification':'observed' if versions is not None else 'unreviewed'})
    return result


def validate_change(c,mode):
    ident=c.get('control_id')
    if ident not in CONTROLS:raise ValueError('Unknown privacy control.')
    if c.get('namespace')!='global' or c.get('key')!=CONTROLS[ident]['key']:raise ValueError('Invalid privacy setting target.')
    if c.get('before') not in (None,'0','1') or c.get('after') not in (None,'0','1'):raise ValueError('Invalid privacy setting value.')
    if mode=='apply' and (c.get('action')!='reduce_tracking' or c.get('after')!='0'):raise ValueError('Invalid privacy reduction.')
    if mode=='restore' and c.get('action')!='restore':raise ValueError('Invalid privacy restoration.')
    if not isinstance(c.get('owner_versions'),dict) or set(c['owner_versions'])!=set(CONTROLS[ident]['owners']):raise ValueError('Invalid privacy owner versions.')
    return ident


def verify_live_owners(adb,serial,c,device,catalog):
    from .inventory import parse_package
    packages=[parse_package(name,adb.shell(serial,['dumpsys','package',name])) for name in CONTROLS[c['control_id']]['owners']]
    versions=reviewed_owners(c['control_id'],device,packages,catalog)
    if versions is None or versions!=c['owner_versions']:raise ValueError('Privacy control firmware or owner version changed. Scan again.')


def plan_changes(inv,selection):
    if selection is None:return []
    if not isinstance(selection,list) or any(not isinstance(x,str) for x in selection) or len(selection)!=len(set(selection)):raise ValueError('Invalid privacy selection.')
    current={c['control_id']:c for c in inv.get('privacy_controls',[])};changes=[]
    for ident in selection:
        if ident not in CONTROLS or ident not in current:raise ValueError('Unknown privacy control; scan again.')
        c=current[ident]
        if not c.get('eligible') or c.get('read_status')!='complete':raise ValueError('Privacy control is not eligible: '+ident)
        change={k:copy.deepcopy(c[k]) for k in ('control_id','label','namespace','key','purpose','reason','features','verification','guidance_level','evidence','owner_versions')}
        change.update(before=c['current_value'],after='0',action='reduce_tracking',outcome='pending',diagnostic='')
        validate_change(change,'apply')
        if change['before']!='0':changes.append(change)
    return changes


def restore_changes(inv,journal):
    current={c['control_id']:c for c in inv.get('privacy_controls',[])};changes=[];seen=set()
    for c in journal.get('setting_changes',[]):
        ident=validate_change(c,'apply')
        if ident in seen:raise ValueError('Duplicate source privacy control.')
        seen.add(ident);live=current.get(ident)
        if not live or not live.get('eligible') or live.get('read_status')!='complete' or live.get('owner_versions')!=c['owner_versions']:raise ValueError('Privacy control cannot be restored on this firmware or owner version.')
        if live['current_value'] not in (c['before'],c['after']):raise ValueError('Restore conflict: '+ident)
        if live['current_value']==c['before']:continue
        changes.append({**copy.deepcopy(c),'before':live['current_value'],'after':c['before'],'action':'restore','outcome':'pending','diagnostic':''})
    return changes
