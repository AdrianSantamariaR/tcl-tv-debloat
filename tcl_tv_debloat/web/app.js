'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('tv-session-token') || '';
if (token) sessionStorage.setItem('tv-session-token', token);
history.replaceState(null, '', location.pathname);
let inventory = null, plan = null, selection = {}, privacySelection = new Set(), currentJob = null, readiness = null, busy = false;
let quickActionRunning = false, suggestionsActive = false;
const featurePackages = {casting:/mediashell|miracast|airplay|magiconnect|tclhome/i,voice:/katniss|smartalexa|android.tts/i,accessibility:/hearaid|talkback|android.tts/i,streaming:/netflix|disney|youtube|spotify|amazonvideo|atresplayer|movistar|rtve|wbd.stream|android.videos|tcl.channelplus/i};
const optionalExtras = new Set(['com.tcl.repairguide','com.tcl.ocean.instructions','com.google.android.feedback','com.tcl.logkit','com.android.dreams.basic','com.google.android.apps.tv.dreamx','com.android.wallpaper.livepicker','com.android.printspooler','com.google.android.syncadapters.calendar','com.google.android.play.games','tv.samba.ssm.ui']);
function retainedFeatures(p) {
  return [...document.querySelectorAll('#feature-preferences input:checked')].map(input => input.value).filter(feature => featurePackages[feature].test(p.package));
}
function suggestApps() {
  selection = {}; suggestionsActive = true;
  for (const p of inventory.packages) {
    if (!inventory.coverage.stale && p.disable_eligible && p.category === 'optional' && [0,1].includes(p.enabled_state) && !retainedFeatures(p).length && (optionalExtras.has(p.package) || Object.values(featurePackages).some(pattern => pattern.test(p.package)))) selection[p.package] = 'disable';
  }
  plan = null; $('preview-panel').hidden = true; functionalChecks.hide(); renderPackages();
  $('suggest-apps-status').textContent = Object.keys(selection).length + ' suggested apps selected. Review the list, then apply together. Protected, unknown and other unclassified functions stay unchanged.';
}
const stateNames = ['Default (0)', 'Enabled (1)', 'Disabled (2)', 'Disabled for user (3)', 'Disabled until used (4)'];
const categoryNames = {protected:'Protected', optional:'Optional · reviewed match', review:'Needs review', unknown:'Unknown'};
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
const functionalChecks = new FunctionalChecks($('validation-panel'), el);
function error(e) { $('error').textContent = e.message || String(e); $('error').hidden = false; }
function clearError() { $('error').hidden = true; }
function selectedCount() { return Object.keys(selection).length + privacySelection.size; }
function changeCount(value) { return (value.changes?.length || 0) + (value.setting_changes?.length || 0); }
function settingState(value) { return value === null ? 'Not set (defaults may allow reporting)' : value === '0' ? 'Off (0)' : value === '1' ? 'On (1)' : 'Value unavailable'; }
function privacyEligible(control) { return control.eligible && control.read_status === 'complete' && [null,'1'].includes(control.current_value) && !inventory?.coverage.stale; }
function clearSelection() { selection = {}; privacySelection.clear(); suggestionsActive = false; plan = null; $('preview-panel').hidden = true; functionalChecks.hide(); $('suggest-apps-status').textContent = ''; }
async function api(path, payload) {
  const response = await fetch('/api/' + path, {method:payload === undefined ? 'GET':'POST', headers:{'X-Session-Token':token, 'Content-Type':'application/json'}, ...(payload === undefined ? {} : {body:JSON.stringify(payload)})});
  const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed.'); return result;
}
function setBusy(value) {
  busy = value;
  const locked = value || quickActionRunning;
  document.querySelectorAll('button').forEach(button => { button.disabled = locked && button.id !== 'cancel'; });
  if (!locked) { $('execute').disabled = !plan || plan.status !== 'preview' || !changeCount(plan); $('preview').disabled = !inventory || !selectedCount(); }
  $('scan').disabled = locked || !readiness?.standard_ready || !$('device').value;
  $('quick-privacy').disabled = locked || !inventory || !readiness?.standard_ready;
  $('suggest-apps').disabled = locked || !inventory || !!inventory.coverage.stale;
  for (const id of ['device','address','pair-address','pair-code','source-journal']) $(id).disabled = locked;
  document.querySelectorAll('#feature-preferences input').forEach(input => { input.disabled = locked; });
  document.querySelectorAll('input[name=analysis]').forEach(input => { input.disabled = locked || (input.id === 'deep-choice' && !readiness?.deep_configured); });
  if (inventory) for (const p of inventory.packages) { const select = $('action-' + p.package); if (select) select.disabled = locked || !p.disable_eligible; }
  if (inventory) for (const control of inventory.privacy_controls || []) { const input = $('privacy-' + control.control_id); if (input) input.disabled = locked || !privacyEligible(control); }
}
async function operation(name, payload) {
  if (busy) throw new Error('Another operation is busy.');
  clearError(); setBusy(true); $('progress-panel').hidden = false; $('progress-message').textContent = 'Starting ' + name; $('progress').removeAttribute('value');
  try {
    const started = await api(name, payload); currentJob = started.id;
    while (true) {
      const job = await api('jobs/' + currentJob);
      $('progress-message').textContent = job.message;
      $('progress-detail').textContent = job.stage + (job.total === null ? '' : ' · ' + job.completed + ' / ' + job.total);
      if (job.total !== null) { $('progress').max = Math.max(1, job.total); $('progress').value = job.completed; }
      if (!['pending','running'].includes(job.status)) {
        if (job.error) throw new Error(job.error);
        let result = job.result;
        if (job.result_id) result = await api((['scan','analyze'].includes(name) ? 'sessions/' : 'plans/') + job.result_id);
        $('progress-message').textContent = 'Operation ' + job.status + '.';
        return result;
      }
      await new Promise(resolve => setTimeout(resolve, 400));
    }
  } finally { currentJob = null; setBusy(false); }
}
async function dependencies() {
  readiness = await api('dependencies'); clearError(); $('dependencies').replaceChildren(); $('deep-dependencies').replaceChildren();
  $('standard-status').textContent = readiness.standard_ready ? 'Ready for standard scanning, disabling and restoration.' : 'ADB is unavailable to this app. Follow its setup instructions, then recheck.';
  $('deep-tools-summary').textContent = 'Optional tools for Deep · ' + (readiness.deep_configured ? 'Configured' : 'Setup needed; standard scan is available with ADB');
  const statusLabels = {configured:'Available',missing:'Path not found',needs_configuration:'Needs configuration',unavailable:'Check failed'};
  for (const dependency of readiness.dependencies) {
    const box = el('div', undefined, 'dependency'); box.append(el('strong', dependency.name), el('span', statusLabels[dependency.status] || dependency.status, 'badge'), el('p', dependency.purpose), el('small', (dependency.version ? dependency.version + ' · ' : '') + dependency.detail));
    const link = el('a', 'Setup instructions ↗'); link.href = dependency.setup_url; link.target = '_blank'; link.rel = 'noreferrer'; box.append(link); $(dependency.required_for === 'standard' ? 'dependencies' : 'deep-dependencies').append(box);
  }
  $('deep-choice').disabled = !readiness.deep_configured;
  if (!readiness.deep_configured) document.querySelector('input[value=standard]').checked = true;
  $('deep-status').textContent = readiness.engine_execution_verified ? 'Engine execution verified on an artifact in this launch.' : readiness.deep_configured ? 'Dependencies configured. The engine is verified only after its first valid APK inspection.' : 'Deep is optional. Expand “Optional tools for Deep” in step 1 for setup. Standard scanning, disabling and restoration need no REA or Java.';
  updateScanButton(); setBusy(busy);
}
function updateScanButton() { $('scan').textContent = $('deep-choice').checked ? 'Scan with deep analysis':'Continue with standard scan'; }
async function devices() {
  const old = $('device').value; const connected = await api('devices'); $('device').replaceChildren(el('option', 'Select an authorized TV')); $('device').firstChild.value = '';
  for (const d of connected) { const option = el('option', d.serial + ' · ' + d.state); option.value = d.serial; option.disabled = d.state !== 'device'; $('device').append(option); }
  if (connected.some(d => d.serial === old && d.state === 'device')) $('device').value = old;
  else if (connected.filter(d => d.state === 'device').length === 1) $('device').value = connected.find(d => d.state === 'device').serial;
  setBusy(busy);
}
function setInventory(value) {
  inventory = value; clearSelection(); $('inventory-panel').hidden = false; $('wizard').hidden = true;
  const d = value.device; $('tv-title').textContent = d.manufacturer + ' · ' + d.model;
  $('identity').textContent = 'Android ' + d.android + ' · Active user ' + d.active_user + ' · ' + d.fingerprint;
  $('coverage').textContent = value.status + ' inventory · ' + value.coverage.scanned_packages + ' / ' + value.coverage.installed_packages + ' packages · Android user 0' + (value.coverage.rea_status ? ' · REA ' + value.coverage.rea_status + ': ' + value.coverage.rea_successful + ' successful, ' + value.coverage.rea_failed + ' failed' : '') + (value.errors.length ? ' · ' + value.errors.join(' ') : '');
  $('counts').replaceChildren(); const all = {all:value.packages.length, protected:0, optional:0, review:0, unknown:0}; value.packages.forEach(p => all[p.category]++);
  for (const [key, count] of Object.entries(all)) { const box = el('div'); box.append(el('strong', count), el('span', key === 'all' ? 'Packages found' : categoryNames[key])); $('counts').append(box); }
  renderPackages(); renderPrivacy(); setBusy(busy);
}
function renderPrivacy() {
  $('privacy-controls').replaceChildren();
  $('reporting-paths').replaceChildren(); $('reporting-paths').hidden = true;
  if (!inventory) return;
  if (!Array.isArray(inventory.privacy_controls)) { $('privacy-controls').append(el('p','Rescan this TV to check TCL reporting controls. This saved inventory does not contain privacy settings.')); return; }
  const controls = inventory.privacy_controls.filter(c => ['tcl_bi_reporting','tcl_diagnostics'].includes(c.control_id));
  if (!controls.length) $('privacy-controls').append(el('p','No supported TCL reporting controls were found in this inventory. Review the manual controls below.'));
  for (const c of controls) {
    const row = el('article',undefined,'privacy-control'), input = el('input'), label = el('label'), copy = el('div');
    input.type = 'checkbox'; input.id = 'privacy-' + c.control_id; input.checked = privacySelection.has(c.control_id); input.disabled = busy || !privacyEligible(c); label.htmlFor = input.id;
    label.append(input,el('span','Turn off ' + c.label));
    const status = inventory.coverage.stale ? 'Saved value before changes: ' : '';
    copy.append(el('p',c.purpose),el('span',status + (c.read_status === 'complete' ? settingState(c.current_value) : 'Read failed · Current value unavailable'),'badge'));
    if (inventory.coverage.stale) copy.append(el('small','Rescan this TV to read the current value before selecting changes.'));
    else if (c.current_value === '0' && c.read_status === 'complete') copy.append(el('small','Already off · No effective setting change.'));
    else if (!c.eligible) copy.append(el('small','Unavailable for automatic changes on this firmware.'));
    if (c.diagnostic) copy.append(el('small',c.diagnostic));
    copy.append(el('p','Feature impact: ' + (c.features?.join(', ') || 'Not established; review the evidence.')),el('small',(c.reason || 'Review the evidence before changing.') + ' · ' + c.verification + ' guidance · ' + c.guidance_level));
    if (c.scope_note) copy.append(el('p',c.scope_note,'scope-note'));
    const details = el('details'); details.append(el('summary','Setting and evidence'),el('pre',JSON.stringify({namespace:c.namespace,key:c.key,target_value:c.target_value,evidence:c.evidence},null,2)));
    input.addEventListener('change',() => { if (input.checked) privacySelection.add(c.control_id); else privacySelection.delete(c.control_id); plan = null; $('preview-panel').hidden = true; updateSelection(); });
    row.append(label,copy,details); $('privacy-controls').append(row);
    if (c.related_paths?.length) {
      const paths = $('reporting-paths'); paths.hidden = false;
      paths.append(el('h3','Other paths reviewed for these versions'),el('small','These are code findings for this saved snapshot, not a live traffic measurement. They do not add selectable changes.'));
      for (const path of c.related_paths) {
        const entry = el('article',undefined,'reporting-path');
        entry.append(el('strong',path.label),el('p',path.summary),el('small',path.feature_impact)); paths.append(entry);
      }
    }
  }
  updateSelection();
}
function renderPackages() {
  if (!inventory) return;
  const query = $('search').value.toLowerCase(), category = $('category').value; $('packages').replaceChildren();
  for (const p of inventory.packages) {
    if ((category !== 'all' && p.category !== category) || ![p.package,p.label,p.purpose].join(' ').toLowerCase().includes(query)) continue;
    const row = el('article', undefined, 'package'), description = el('div');
    description.append(el('h3', p.label), el('code', p.package), el('p', p.purpose), el('span', categoryNames[p.category], 'badge ' + p.category), el('span', (inventory.coverage.stale ? 'Before changes: ' : '') + (stateNames[p.enabled_state] || 'State unavailable'), 'badge'), el('small', p.verification + ' guidance · ' + (p.features.join(', ') || 'Feature impact not established')));
    const choice = el('div'), label = el('label', 'Action for ' + p.package), select = el('select'); select.id = 'action-' + p.package; label.htmlFor = select.id;
    for (const [value, text] of [['keep','Keep as is'],['disable','Disable for user 0']]) { const option = el('option', text); option.value = value; option.disabled = value === 'disable' && !p.disable_eligible; select.append(option); }
    select.value = selection[p.package] || 'keep'; select.disabled = !p.disable_eligible || busy;
    select.addEventListener('change', () => { suggestionsActive = false; $('suggest-apps-status').textContent = 'Selection adjusted manually.'; if (select.value === 'keep') delete selection[p.package]; else selection[p.package] = select.value; updateSelection(); plan = null; $('preview-panel').hidden = true; });
    const retained = retainedFeatures(p);
    if (retained.length) description.append(el('small','You want to keep ' + retained.join(', ') + '. Review this package’s feature impact before disabling.'));
    choice.append(label,select); row.append(description,choice);
    const details = el('details'); details.append(el('summary','Permissions, versions and evidence'));
    const data = {version_code:p.version_code, version_name:p.version_name, uid:p.uid, shared_uid:p.shared_uid, granted_permissions:p.granted_permissions, adb_requested_permissions:p.adb_requested_permissions, device_paths:p.device_paths, guidance_level:p.guidance_level, limitations:p.limitations, evidence:p.evidence};
    for (const key of ['apk_sha256','declared_permissions','components','manifest','analysis']) if (key in p) data[key] = p[key];
    details.append(el('pre',JSON.stringify(data,null,2))); row.append(details); $('packages').append(row);
  }
  updateSelection();
}
function invalidateSnapshot(journal) {
  if (!inventory || journal.device.serial !== inventory.device.serial || !changeCount(journal) || journal.status === 'preview') return;
  inventory.coverage.stale = true; selection = {}; privacySelection.clear();
  if (plan?.status === 'preview') { plan = null; $('preview-panel').hidden = true; }
  for (const p of inventory.packages) { p.disable_eligible = false; }
  $('coverage').textContent = 'Saved inventory snapshot · Changes were attempted after this scan. Rescan this TV before choosing further changes; use the journal for outcomes.';
  renderPackages(); renderPrivacy(); setBusy(busy);
}
function updateSelection() { $('selected-count').textContent = selectedCount() + ' selected'; $('preview').disabled = busy || quickActionRunning || !inventory || !selectedCount(); }
function showPlan(value) {
  plan = value; $('preview-panel').hidden = false; $('plan-title').textContent = (value.mode === 'restore' ? 'Restoration':'Change') + ' ' + (value.status === 'preview' ? 'preview':'journal');
  $('plan-meta').textContent = value.status + ' · ' + changeCount(value) + ' changes · Packages: Android user 0 · Reporting settings: device-wide · ' + value.identity_assurance + ' · Plan ' + value.id + (value.source_plan_id ? ' · Source ' + value.source_plan_id : '');
  $('changes').replaceChildren();
  for (const c of value.changes) {
    const row = el('div',undefined,'change'); row.append(el('strong',c.package), el('p',stateNames[c.before] + ' → ' + stateNames[c.after] + ' · ' + c.outcome + (c.diagnostic ? ' · ' + c.diagnostic : '')));
    row.append(el('p',c.purpose || 'See the saved inventory for this package’s function.'), el('p','Feature impact: ' + (c.features?.join(', ') || 'Not established; review the package details.')),
      el('small',(c.reason || 'Individually selected optional package.') + ' · ' + (c.verification || 'observed') + ' guidance · ' + (c.guidance_level || 'saved inventory') + ' · ' + (c.evidence?.length || 0) + ' evidence records'));
    $('changes').append(row);
  }
  for (const c of value.setting_changes || []) {
    const row = el('div',undefined,'change'); row.append(el('strong',c.label || c.control_id),el('p',settingState(c.before) + ' → ' + settingState(c.after) + ' · ' + c.outcome + (c.diagnostic ? ' · ' + c.diagnostic : '')),
      el('p',c.purpose),el('p','Feature impact: ' + (c.features?.join(', ') || 'Not established; review the setting details.')),el('small',(c.reason || 'Individually selected reporting control.') + ' · ' + c.verification + ' guidance · ' + c.guidance_level + ' · ' + (c.evidence?.length || 0) + ' evidence records'));
    const details = el('details'); details.append(el('summary','Setting, recovery and evidence'),el('pre',JSON.stringify({action:c.action,namespace:c.namespace,key:c.key,before:c.before,after:c.after,owner_versions:c.owner_versions,evidence:c.evidence},null,2))); row.append(details); $('changes').append(row);
  }
  if (!changeCount(value)) $('changes').append(el('p','No effective changes: the selected packages and reporting settings already have the requested states.'));
  $('execute').textContent = value.mode === 'restore' ? 'Restore this preview':'Apply this preview'; functionalChecks.show(value, inventory); setBusy(busy);
}
async function historyList() {
  const journals = await api('plans'); const old = $('source-journal').value; $('source-journal').replaceChildren(el('option','Choose a saved apply journal')); $('source-journal').firstChild.value = ''; $('history').replaceChildren();
  for (const j of journals) {
    if (j.mode === 'apply' && j.status !== 'preview') { const option = el('option',j.created_at.slice(0,19) + ' · ' + j.status + ' · ' + j.id); option.value = j.id; $('source-journal').append(option); }
    const row = el('div',undefined,'history-row'), button = el('button','View'); row.append(el('span',j.mode + ' · ' + j.status + ' · ' + changeCount(j) + ' changes · ' + j.created_at.slice(0,19)),button); button.addEventListener('click',() => showPlan(j)); $('history').append(row);
  }
  if (journals.some(j => j.id === old)) $('source-journal').value = old;
  if (!journals.length) $('history').append(el('p','No saved changes yet.'));
  if (inventory) for (const journal of journals) if ((journal.finished_at || journal.started_at || journal.created_at) > inventory.captured_at) invalidateSnapshot(journal);
}
function download(name, content) { const url = URL.createObjectURL(new Blob([content], {type:'text/plain'})); const anchor = el('a'); anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url),1000); }
function bind(id,event,fn) { $(id).addEventListener(event,async e => { if (event === 'submit') e.preventDefault(); try { await fn(e); } catch (problem) { error(problem); } }); }
bind('recheck','click',dependencies); bind('refresh-devices','click',devices); bind('refresh-history','click',historyList);
bind('new-scan','click',async () => { clearSelection(); $('wizard').hidden = false; renderPackages(); renderPrivacy(); await dependencies(); await devices(); });
bind('device','change',() => { inventory = null; clearSelection(); $('inventory-panel').hidden = true; setBusy(busy); });
bind('connect-form','submit',async () => { const r = await operation('connect',{address:$('address').value.trim()}); $('connection-message').textContent = r.message; await devices(); });
bind('pair-form','submit',async () => { const code = $('pair-code').value; $('pair-code').value = ''; const r = await operation('pair',{address:$('pair-address').value.trim(),code}); $('connection-message').textContent = r.message; });
async function scanSelected(serial,deep=false) { if (!serial) throw new Error('Select an authorized TV first.'); clearSelection(); renderPackages(); renderPrivacy(); const inv = await operation('scan',{serial,deep}); setInventory(inv); await historyList(); return inv; }
bind('quick-privacy','click',async () => {
  if (quickActionRunning || busy || !inventory) throw new Error('Another operation is busy or no TV is selected.');
  const original = structuredClone(inventory.device), status = $('quick-privacy-status');
  quickActionRunning = true; setBusy(false); status.textContent = 'Reading your TV before applying supported TCL controls…';
  try {
    const fresh = await scanSelected(original.serial);
    if (fresh.status === 'cancelled' || fresh.device.serial !== original.serial || fresh.device.fingerprint !== original.fingerprint || (original.hardware_id && fresh.device.hardware_id !== original.hardware_id)) { status.textContent = 'Stopped: scan cancelled or TV identity changed. No shortcut changes applied.'; return; }
    const ids = (fresh.privacy_controls || []).filter(c => ['tcl_bi_reporting','tcl_diagnostics'].includes(c.control_id) && privacyEligible(c)).map(c => c.control_id);
    if (!ids.length) {
      const supported = (fresh.privacy_controls || []).filter(c => c.eligible && c.read_status === 'complete');
      status.textContent = supported.length && supported.every(c => c.current_value === '0') ? 'Supported TCL controls are already off. No changes needed.' : 'No supported changes available. Review the scan details.'; return;
    }
    const p = await operation('preview',{inventory_id:fresh.id,selection:{},privacy_selection:ids});
    if (!changeCount(p)) {status.textContent = 'No effective changes needed.'; return;}
    const result = await operation('apply',{plan_id:p.id});
    invalidateSnapshot(result); showPlan(result);
    if (result.status === 'complete') {
      status.textContent = 'Changes saved. Refreshing the inventory so you can continue with apps…';
      const after = await operation('scan',{serial:original.serial,deep:false});
      if (after.status === 'cancelled' || after.device.serial !== original.serial || after.device.fingerprint !== original.fingerprint || (original.hardware_id && after.device.hardware_id !== original.hardware_id)) {status.textContent = 'Changes saved, but the final scan was cancelled or TV identity changed. Review the journal below.'; return;}
      setInventory(after); showPlan(result);
    }
    await historyList();
    const verified = (result.setting_changes || []).filter(c => c.outcome === 'successful').length;
    status.textContent = result.status === 'complete' ? verified + ' TCL controls applied and verified. Recovery saved below. Other tracking is outside these controls.' : 'Operation ' + result.status + '. Review the saved journal; incomplete changes are not verified.';
    $('validation-panel').scrollIntoView({behavior:'smooth'});
  } catch (problem) {status.textContent = 'Stopped. Review the error and any saved journal below before continuing.'; throw problem;}
  finally {quickActionRunning = false; setBusy(false);}
});
bind('suggest-apps','click',suggestApps);
bind('scan','click',async () => { await scanSelected($('device').value,$('deep-choice').checked); });
bind('rescan','click',async () => { clearSelection(); renderPackages(); renderPrivacy(); $('wizard').hidden = false; await dependencies(); await devices(); $('wizard').scrollIntoView({behavior:'smooth'}); });
document.querySelectorAll('#feature-preferences input').forEach(input => input.addEventListener('change',() => {
  if (suggestionsActive) suggestApps();
  else {for (const p of inventory?.packages || []) if (retainedFeatures(p).length) delete selection[p.package]; plan = null; $('preview-panel').hidden = true; renderPackages();}
}));
document.querySelectorAll('input[name=analysis]').forEach(radio => radio.addEventListener('change',updateScanButton));
bind('search','input',renderPackages); bind('category','change',renderPackages);
bind('preview','click',async () => { const payload = {inventory_id:inventory.id,selection}; if (privacySelection.size) payload.privacy_selection = [...privacySelection]; const p = await operation('preview',payload); showPlan(p); await historyList(); $('preview-panel').scrollIntoView({behavior:'smooth'}); });
bind('execute','click',async () => { const result = await operation(plan.mode === 'restore' ? 'restore':'apply',{plan_id:plan.id}); selection = {}; privacySelection.clear(); invalidateSnapshot(result); showPlan(result); await historyList(); });
bind('cancel','click',async () => { if (currentJob) { await api('jobs/' + currentJob + '/cancel',{}); $('cancel').disabled = true; } });
bind('restore-preview','click',async () => {
  const source = $('source-journal').value; if (!source) throw new Error('Choose a source apply journal first.');
  const journal = await api('plans/' + source); const inv = await scanSelected(journal.device.serial);
  const result = await operation('restore_preview',{inventory_id:inv.id,source_plan_id:source}); showPlan(result); await historyList(); $('preview-panel').scrollIntoView({behavior:'smooth'});
});
bind('download-plan','click',() => { if (plan) download('plan.json',JSON.stringify(plan,null,2)); });
bind('download-validation','click',() => { const report = functionalChecks.report(); download('tv-checks-' + report.source_apply_journal_id + '.json',JSON.stringify(report,null,2)); });
bind('download-restore','click',async () => { if (!plan || plan.mode !== 'apply' || plan.status === 'preview') throw new Error('Choose a started apply journal for recovery export.'); const files = await operation('export',{plan_id:plan.id}); download('restore.py',files['restore.py']); });
(async () => {
  try { const status = await api('status'); $('storage').textContent = 'Private data: ' + status.data_dir + ' · Processing stays on this computer.'; await dependencies(); await devices(); const sessions = await api('sessions'); if (sessions.length) setInventory(sessions[0]); await historyList(); }
  catch (problem) { error(problem); }
})();
