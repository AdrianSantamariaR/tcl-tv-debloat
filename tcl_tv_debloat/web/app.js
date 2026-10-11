'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('tv-session-token') || '';
if (token) sessionStorage.setItem('tv-session-token', token);
history.replaceState(null, '', location.pathname);
let inventory = null, plan = null, selection = {}, privacySelection = new Set(), currentJob = null, readiness = null, busy = false;
let quickActionRunning = false, suggestionsActive = false;
let flowStage = 'connect', goalChosen = false, resultJournal = null, pendingConnectionSerial = null;
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
  $('suggest-apps-status').textContent = Object.keys(selection).length ? Object.keys(selection).length + ' suggested apps selected. Review the list, then apply together. Protected, unknown and other unclassified functions stay unchanged.' : 'No supported package changes available for these preferences and versions. Other packages stay unchanged.';
}
function resetBasicGuidance() { $('basic-reset-ack').checked = false; $('basic-tv-steps').hidden = true; }
function setupNeedsScan(serial) { return !!serial && sessionStorage.getItem('tv-setup-rescan:' + serial) === 'pending'; }
function showStage(stage, focus=true) {
  flowStage = stage;
  for (const [name,id] of [['connect','wizard'],['choose','inventory-panel'],['review','preview-panel'],['result','result-panel']]) $(id).hidden = name !== stage;
  for (const item of document.querySelectorAll('.flow-nav li')) {
    if (item.dataset.stage === stage) item.setAttribute('aria-current','step');
    else item.removeAttribute('aria-current');
  }
  if (focus) {
    const heading = $({connect:'setup-heading',choose:'choose-heading',review:'plan-title',result:'result-heading'}[stage]);
    heading.focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'});
  }
}
function renderGuidedSummary() {
  const use = $('intended-use').value, stale = !!inventory?.coverage.stale;
  for (const button of document.querySelectorAll('[data-use]')) button.setAttribute('aria-pressed',String(goalChosen && button.dataset.use === use));
  $('package-flow').hidden = use === 'basic' && goalChosen;
  $('basic-tv-guide').hidden = use !== 'basic' || !goalChosen;
  $('keep-details').hidden = use === 'privacy';
  $('guided-privacy').disabled = busy || quickActionRunning || stale || use === 'privacy';
  $('guided-privacy').parentElement.hidden = use === 'privacy';
  $('guided-privacy-help').hidden = use === 'privacy';
  $('stale-prompt').hidden = !stale;
  $('preview').hidden = stale;
  $('scan-warning').hidden = !inventory || inventory.status === 'complete' || stale;
  $('scan-warning').textContent = 'This scan is incomplete. Unread or unsupported apps stay unchanged. See Advanced for details.';
  $('intended-use-status').textContent = !goalChosen ? 'Your TV stays unchanged until you review and apply.' : use === 'hdmi' ? 'Accessibility keeps your choice. This profile does not disconnect the TV from the Internet.' : use === 'basic' ? 'This is a manual setup guide. The app never resets your TV.' : use === 'privacy' ? 'Only supported TCL reporting settings are proposed. Other services may still collect data.' : 'Streaming, casting and voice stay by default. Customize below if needed.';
}
function syncGuidedPrivacy() {
  privacySelection.clear();
  if (inventory && $('guided-privacy').checked) for (const control of inventory.privacy_controls || []) {
    if (['tcl_bi_reporting','tcl_diagnostics'].includes(control.control_id) && privacyEligible(control)) privacySelection.add(control.control_id);
  }
  renderPrivacy();
}
function prepareSuggestions() {
  if (!inventory) return;
  if ($('intended-use').value === 'privacy') { selection = {}; suggestionsActive = false; plan = null; renderPackages(); }
  else suggestApps();
  syncGuidedPrivacy();
  $('suggest-apps-status').textContent = selectedCount() ? 'Prepared ' + Object.keys(selection).length + ' app changes and ' + privacySelection.size + ' reporting settings. Review before applying.' : 'No supported changes are available for this goal and these versions.';
  renderGuidedSummary(); setBusy(busy);
}
function chooseIntendedUse() {
  const use = $('intended-use').value;
  clearSelection(); goalChosen = true;
  $('guided-privacy').checked = use === 'privacy';
  if (use !== 'basic' && use !== 'privacy') for (const input of document.querySelectorAll('#feature-preferences input')) if (input.value !== 'accessibility') input.checked = use === 'smart';
  if (use !== 'basic') prepareSuggestions();
  renderGuidedSummary(); renderPackages(); renderPrivacy(); showStage('choose',false); setBusy(busy);
}
const stateNames = ['Default (0)', 'Enabled (1)', 'Disabled (2)', 'Disabled for user (3)', 'Disabled until used (4)'];
const categoryNames = {protected:'Protected', optional:'Optional · reviewed match', review:'Needs review', unknown:'Unknown'};
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
const functionalChecks = new FunctionalChecks($('validation-panel'), el);
function error(e) { $('error').textContent = (e.message || String(e)) + ' You can try again; saved recovery remains available.'; $('error').hidden = false; $('error').focus({preventScroll:true}); $('error').scrollIntoView({behavior:'instant',block:'center'}); }
function clearError() { $('error').hidden = true; }
function selectedCount() { return Object.keys(selection).length + privacySelection.size; }
function changeCount(value) { return (value.changes?.length || 0) + (value.setting_changes?.length || 0); }
function settingState(value) { return value === null ? 'Not set (defaults may allow reporting)' : value === '0' ? 'Off (0)' : value === '1' ? 'On (1)' : 'Value unavailable'; }
function privacyEligible(control) { return control.eligible && control.read_status === 'complete' && [null,'1'].includes(control.current_value) && !inventory?.coverage.stale; }
function clearSelection() { selection = {}; privacySelection.clear(); suggestionsActive = false; plan = null; $('preview-panel').hidden = true; functionalChecks.hide(); $('suggest-apps-status').textContent = 'Select a goal to prepare reviewed changes.'; resetBasicGuidance(); }
async function api(path, payload) {
  const response = await fetch('/api/' + path, {method:payload === undefined ? 'GET':'POST', headers:{'X-Session-Token':token, 'Content-Type':'application/json'}, ...(payload === undefined ? {} : {body:JSON.stringify(payload)})});
  const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed.'); return result;
}
function setBusy(value) {
  busy = value;
  const locked = value || quickActionRunning;
  document.body.classList.toggle('working',locked);
  $('progress-panel').hidden = !locked;
  $('cancel').hidden = !value;
  $('cancel').disabled = !currentJob;
  document.querySelectorAll('button').forEach(button => { button.disabled = locked && button.id !== 'cancel'; });
  if (!locked) { $('execute').disabled = !plan || plan.status !== 'preview' || !changeCount(plan) || setupNeedsScan(plan.device.serial) || (plan.mode === 'apply' && !!inventory?.coverage.stale); $('preview').disabled = !inventory || !!inventory.coverage.stale || !selectedCount(); }
  $('scan').disabled = locked || !readiness?.standard_ready || !$('device').value;
  $('quick-privacy').disabled = locked || !inventory || !readiness?.standard_ready;
  $('suggest-apps').disabled = locked || !inventory || !!inventory.coverage.stale;
  for (const id of ['device','address','pair-address','pair-code','source-journal','intended-use','basic-reset-ack']) $(id).disabled = locked;
  document.querySelectorAll('#feature-preferences input').forEach(input => { input.disabled = locked; });
  $('undo-latest').disabled = locked || !resultJournal || resultJournal.mode !== 'apply' || resultJournal.status === 'preview' || !changeCount(resultJournal);
  $('continue-scan').disabled = locked || !resultJournal;
  $('edit-selection').disabled = locked || !inventory;
  $('download-restore').disabled = locked || !plan || plan.mode !== 'apply' || plan.status === 'preview';
  $('guided-privacy').disabled = locked || !!inventory?.coverage.stale || $('intended-use').value === 'privacy';
  document.querySelectorAll('input[name=analysis]').forEach(input => { input.disabled = locked || (input.id === 'deep-choice' && !readiness?.deep_configured); });
  if (inventory) for (const p of inventory.packages) { const select = $('action-' + p.package); if (select) select.disabled = locked || !p.disable_eligible; }
  if (inventory) for (const control of inventory.privacy_controls || []) { const input = $('privacy-' + control.control_id); if (input) input.disabled = locked || !privacyEligible(control); }
}
async function operation(name, payload) {
  if (busy) throw new Error('Another operation is busy.');
  clearError(); setBusy(true); $('progress-message').textContent = ({scan:'Checking your TV…',preview:'Preparing your review…',apply:'Applying your changes…',restore:'Restoring your changes…',restore_preview:'Checking what can be undone…',connect:'Connecting to your TV…',pair:'Pairing with your TV…',export:'Preparing recovery files…'})[name] || 'Working…'; $('progress').removeAttribute('value'); $('progress-message').focus({preventScroll:true}); $('progress-panel').scrollIntoView({behavior:'instant',block:'start'});
  try {
    const started = await api(name, payload); currentJob = started.id; $('cancel').disabled = false;
    while (true) {
      const job = await api('jobs/' + currentJob);
      $('progress-message').textContent = job.message;
      $('progress-detail').textContent = job.total === null ? '' : job.completed + ' of ' + job.total;
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
  $('standard-status').textContent = readiness.standard_ready ? 'Connection tools ready.' : 'Install ADB on this computer to connect your TV. Open Tools below for instructions.';
  $('deep-tools-summary').textContent = 'Optional tools for Deep · ' + (readiness.deep_configured ? 'Configured' : 'Setup needed; standard scan is available with ADB');
  const statusLabels = {configured:'Available',missing:'Path not found',needs_configuration:'Needs configuration',unavailable:'Check failed'};
  for (const dependency of readiness.dependencies) {
    const box = el('div', undefined, 'dependency'); box.append(el('strong', dependency.name), el('span', statusLabels[dependency.status] || dependency.status, 'badge'), el('p', dependency.purpose), el('small', (dependency.version ? dependency.version + ' · ' : '') + dependency.detail));
    const link = el('a', 'Setup instructions ↗'); link.href = dependency.setup_url; link.target = '_blank'; link.rel = 'noreferrer'; box.append(link); $(dependency.required_for === 'standard' ? 'dependencies' : 'deep-dependencies').append(box);
  }
  $('deep-choice').disabled = !readiness.deep_configured;
  if (!readiness.deep_configured) document.querySelector('input[value=standard]').checked = true;
  $('deep-status').textContent = readiness.engine_execution_verified ? 'Engine execution verified on an artifact in this launch.' : readiness.deep_configured ? 'Dependencies configured. The engine is verified only after its first valid APK inspection.' : 'Code inspection is optional. Standard scanning needs only ADB.';
  $('tool-details').open = !readiness.standard_ready;
  updateScanButton(); setBusy(busy);
}
function updateScanButton() { $('scan').textContent = $('deep-choice').checked ? 'Scan and inspect apps':'Scan TV'; }
async function devices() {
  const old = $('device').value; const connected = await api('devices'); $('device').replaceChildren(el('option', 'Select an authorized TV')); $('device').firstChild.value = '';
  for (const d of connected) { const option = el('option', d.serial + ' · ' + d.state); option.value = d.serial; option.disabled = d.state !== 'device'; $('device').append(option); }
  if (pendingConnectionSerial && !connected.some(d => d.serial === pendingConnectionSerial && d.state === 'device')) $('device').value = '';
  else if (connected.some(d => d.serial === old && d.state === 'device')) $('device').value = old;
  else if (connected.filter(d => d.state === 'device').length === 1) $('device').value = connected.find(d => d.state === 'device').serial;
  $('connect-details').open = !connected.some(d => d.state === 'device');
  setBusy(busy); return connected;
}
function setInventory(value, fresh=false) {
  if (setupNeedsScan(value.device.serial)) {
    if (fresh && value.status === 'complete') sessionStorage.removeItem('tv-setup-rescan:' + value.device.serial);
    else { value.coverage.stale = true; for (const p of value.packages) p.disable_eligible = false; }
  }
  inventory = value; clearSelection(); showStage('choose');
  const d = value.device; $('tv-title').textContent = d.manufacturer + ' · ' + d.model;
  $('identity').textContent = 'Android ' + d.android + ' · Active user ' + d.active_user + ' · ' + d.fingerprint;
  $('coverage').textContent = value.status + ' inventory · ' + value.coverage.scanned_packages + ' / ' + value.coverage.installed_packages + ' packages · Android user 0' + (value.coverage.rea_status ? ' · REA ' + value.coverage.rea_status + ': ' + value.coverage.rea_successful + ' successful, ' + value.coverage.rea_failed + ' failed' : '') + (value.errors.length ? ' · ' + value.errors.join(' ') : '');
  if (setupNeedsScan(d.serial)) $('coverage').textContent = 'Setup changed. This saved inventory describes the previous setup. Reconnect, authorize debugging and scan before preparing any further changes.';
  $('counts').replaceChildren(); const all = {all:value.packages.length, protected:0, optional:0, review:0, unknown:0}; value.packages.forEach(p => all[p.category]++);
  for (const [key, count] of Object.entries(all)) { const box = el('div'); box.append(el('strong', count), el('span', key === 'all' ? 'Packages found' : categoryNames[key])); $('counts').append(box); }
  renderPackages(); renderPrivacy();
  if (goalChosen && fresh && $('intended-use').value !== 'basic') prepareSuggestions();
  renderGuidedSummary(); setBusy(busy);
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
    input.addEventListener('change',() => { if (input.checked) privacySelection.add(c.control_id); else privacySelection.delete(c.control_id); plan = null; $('preview-panel').hidden = true; $('guided-privacy').checked = false; updateSelection(); });
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
  if (plan?.status === 'preview') { plan = null; showStage('choose',false); }
  for (const p of inventory.packages) { p.disable_eligible = false; }
  $('coverage').textContent = 'Saved inventory snapshot · Changes were attempted after this scan. Rescan this TV before choosing further changes; use the journal for outcomes.';
  renderPackages(); renderPrivacy(); renderGuidedSummary(); setBusy(busy);
}
function updateSelection() {
  $('selected-count').textContent = selectedCount() + ' selected';
  if (goalChosen && $('intended-use').value !== 'basic') $('suggest-apps-status').textContent = selectedCount() ? Object.keys(selection).length + ' app changes and ' + privacySelection.size + ' reporting settings ready to review.' : 'No supported changes are selected for this goal.';
  $('preview').disabled = busy || quickActionRunning || !inventory || !!inventory.coverage.stale || !selectedCount();
}
function showPlan(value) {
  plan = value;
  const reviewing = value.status === 'preview', restoring = value.mode === 'restore';
  const changes = [...(value.changes || []),...(value.setting_changes || [])];
  const targetTV = [value.device.manufacturer,value.device.model].filter(Boolean).join(' · ');
  for (const id of ['review-tv','result-tv']) $(id).textContent = 'TV: ' + (targetTV ? targetTV + ' · ' : '') + value.device.serial;
  $(reviewing ? 'review-change-list':'result-change-list').append($('changes'));
  $(reviewing ? 'review-details':'result-journal-tools').append($('journal-tools'));
  $('plan-title').textContent = restoring ? 'Review what to undo':'Review your changes';
  $('review-summary').textContent = restoring ? 'Restore the recorded app states and reporting settings. Later conflicting changes are left for review.' : (value.changes?.length || 0) + ' app changes and ' + (value.setting_changes?.length || 0) + ' reporting settings. Review their effect on TV functions.';
  $('plan-meta').textContent = value.status + ' · ' + changeCount(value) + ' changes · Android user 0 · Reporting settings: device-wide · ' + value.identity_assurance + ' · Plan ' + value.id + (value.source_plan_id ? ' · Source ' + value.source_plan_id : '');
  $('changes').replaceChildren();
  for (const c of changes) {
    const row = el('div',undefined,'change');
    const p = inventory?.packages.find(p => p.package === c.package);
    const label = c.label || (inventory?.id === value.inventory_id ? p?.label : null) || c.package || c.control_id;
    row.append(el('strong',label));
    if (c.package) row.append(el('p',reviewing ? (restoring ? 'Restore this app to its recorded state.':'Disable this optional app.') : c.outcome === 'successful' ? (restoring ? 'Previous app state restored and checked.':'App disabled and state checked.') : 'Result: ' + c.outcome));
    else row.append(el('p',settingState(c.before) + ' → ' + settingState(c.after) + (reviewing ? '' : ' · ' + c.outcome)));
    row.append(el('small','Function affected: ' + (c.features?.join(', ') || 'Not established; review the evidence.')));
    if (c.diagnostic) row.append(el('p',c.diagnostic));
    const evidence = el('details'); evidence.append(el('summary','Technical details'),el('pre',JSON.stringify(c,null,2))); row.append(evidence); $('changes').append(row);
  }
  if (!changes.length) $('changes').append(el('p','No effective changes: the selected apps and reporting settings already have the requested states.'));
  $('execute').textContent = restoring ? 'Restore these changes':'Apply changes';
  functionalChecks.show(value,inventory);
  if (!reviewing) {
    resultJournal = value;
    const verified = changes.filter(c => c.outcome === 'successful').length;
    const unresolved = changes.filter(c => !['successful','unchanged'].includes(c.outcome)).length;
    $('result-heading').textContent = unresolved || value.status !== 'complete' ? 'Some changes need attention' : restoring ? 'Changes restored':'Changes saved';
    $('result-summary').textContent = verified + ' changes verified' + (unresolved || value.status !== 'complete' ? ' · ' + value.status + '. Open change details below.' : '. Recovery is available for recorded app states and settings.');
    $('undo-latest').hidden = restoring || !changes.length;
    $('undo-help').hidden = restoring || !changes.length;
  }
  showStage(reviewing ? 'review':'result'); setBusy(busy);
}
async function historyList() {
  const journals = await api('plans'); const old = $('source-journal').value; $('source-journal').replaceChildren(el('option','Choose a saved apply journal')); $('source-journal').firstChild.value = ''; $('history').replaceChildren();
  for (const j of journals) {
    if (j.mode === 'apply' && j.status !== 'preview') { const option = el('option',(j.device.model || j.device.serial) + ' · ' + new Date(j.created_at).toLocaleString() + ' · ' + changeCount(j) + ' changes'); option.value = j.id; $('source-journal').append(option); }
    const row = el('div',undefined,'history-row'), button = el('button','View'); row.append(el('span',(j.device.model || 'TV') + ' · ' + j.device.serial + ' · ' + (j.mode === 'restore' ? 'Undo':'Changes') + ' · ' + j.status + ' · ' + changeCount(j) + ' changes · ' + new Date(j.created_at).toLocaleString()),button); button.addEventListener('click',() => { $('history-details').open = false; showPlan(j); }); $('history').append(row);
  }
  if (journals.some(j => j.id === old)) $('source-journal').value = old;
  if (!journals.length) $('history').append(el('p','No saved changes yet.'));
  if (inventory) for (const journal of journals) if ((journal.finished_at || journal.started_at || journal.created_at) > inventory.captured_at) invalidateSnapshot(journal);
}
function download(name, content) { const url = URL.createObjectURL(new Blob([content], {type:'text/plain'})); const anchor = el('a'); anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url),1000); }
function bind(id,event,fn) { $(id).addEventListener(event,async e => { if (event === 'submit') e.preventDefault(); try { await fn(e); } catch (problem) { error(problem); } }); }
bind('recheck','click',dependencies); bind('refresh-devices','click',async () => { const connected = await devices(); const target = connected.find(d => d.serial === pendingConnectionSerial && d.state === 'device'); if (target) { $('device').value = target.serial; pendingConnectionSerial = null; await scanSelected(target.serial,$('deep-choice').checked); } }); bind('refresh-history','click',historyList);
bind('new-scan','click',async () => { clearSelection(); goalChosen = false; $('guided-privacy').checked = false; showStage('connect'); renderPackages(); renderPrivacy(); await dependencies(); await devices(); });
bind('device','change',() => { pendingConnectionSerial = null; inventory = null; goalChosen = false; clearSelection(); showStage('connect',false); setBusy(busy); });
bind('connect-form','submit',async () => { pendingConnectionSerial = $('address').value.trim(); const r = await operation('connect',{address:pendingConnectionSerial}); $('connection-message').textContent = r.message; const connected = await devices(); const target = connected.find(d => d.serial === pendingConnectionSerial && d.state === 'device'); if (target) { $('device').value = target.serial; pendingConnectionSerial = null; await scanSelected(target.serial,$('deep-choice').checked); } else $('connection-message').textContent = 'Accept the debugging prompt on the TV, then press Refresh. The scan will start once that TV is authorized.'; });
bind('pair-form','submit',async () => { const code = $('pair-code').value; $('pair-code').value = ''; const r = await operation('pair',{address:$('pair-address').value.trim(),code}); $('connection-message').textContent = r.message; });
async function scanSelected(serial,deep=false) { if (!serial) throw new Error('Select an authorized TV first.'); clearSelection(); renderPackages(); renderPrivacy(); const inv = await operation('scan',{serial,deep}); setInventory(inv,true); await historyList(); return inv; }
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
      setInventory(after,true); showPlan(result);
    }
    await historyList();
    const verified = (result.setting_changes || []).filter(c => c.outcome === 'successful').length;
    status.textContent = result.status === 'complete' ? verified + ' TCL controls applied and verified. Recovery saved below. Other tracking is outside these controls.' : 'Operation ' + result.status + '. Review the saved journal; incomplete changes are not verified.';
    $('validation-panel').scrollIntoView({behavior:'smooth'});
  } catch (problem) {status.textContent = 'Stopped. Review the error and any saved journal below before continuing.'; throw problem;}
  finally {quickActionRunning = false; setBusy(false);}
});
bind('suggest-apps','click',prepareSuggestions);
for (const button of document.querySelectorAll('[data-use]')) bind(button.id,'click',() => { $('intended-use').value = button.dataset.use; chooseIntendedUse(); });
bind('guided-privacy','change',() => { plan = null; syncGuidedPrivacy(); renderGuidedSummary(); });
bind('open-history','click',() => { $('history-details').open = !$('history-details').open; if ($('history-details').open) { $('history-details').scrollIntoView({behavior:'instant',block:'start'}); $('history-details').querySelector('summary').focus(); } });
bind('edit-selection','click',() => { plan = null; showStage('choose'); setBusy(busy); });
bind('refresh-stale','click',() => scanSelected(inventory.device.serial,$('deep-choice').checked));
bind('continue-scan','click',() => scanSelected(resultJournal.device.serial,$('deep-choice').checked));
bind('intended-use','change',chooseIntendedUse);
bind('basic-reset-ack','change',() => { $('basic-tv-steps').hidden = !$('basic-reset-ack').checked; });
bind('basic-setup-complete','click',async () => {
  if (!$('basic-reset-ack').checked) throw new Error('Read and acknowledge the factory-reset warning first.');
  sessionStorage.setItem('tv-setup-rescan:' + inventory.device.serial,'pending');
  inventory.coverage.stale = true;
  for (const p of inventory.packages) p.disable_eligible = false;
  clearSelection(); renderPackages(); renderPrivacy();
  $('coverage').textContent = 'Setup changed. This saved inventory describes the previous setup. Reconnect, authorize debugging and scan before preparing any further changes.';
  goalChosen = false; $('intended-use').value = 'smart'; showStage('connect'); await dependencies(); await devices(); setBusy(busy);
});
bind('scan','click',async () => { await scanSelected($('device').value,$('deep-choice').checked); });
bind('rescan','click',() => scanSelected(inventory.device.serial,$('deep-choice').checked));
document.querySelectorAll('#feature-preferences input').forEach(input => input.addEventListener('change',() => {
  if (suggestionsActive) { suggestApps(); syncGuidedPrivacy(); }
  else {for (const p of inventory?.packages || []) if (retainedFeatures(p).length) delete selection[p.package]; plan = null; $('preview-panel').hidden = true; renderPackages();}
}));
document.querySelectorAll('input[name=analysis]').forEach(radio => radio.addEventListener('change',updateScanButton));
bind('search','input',renderPackages); bind('category','change',renderPackages);
bind('preview','click',async () => { const payload = {inventory_id:inventory.id,selection}; if (privacySelection.size) payload.privacy_selection = [...privacySelection]; const p = await operation('preview',payload); showPlan(p); await historyList(); $('plan-title').focus({preventScroll:true}); });
bind('execute','click',async () => { if (setupNeedsScan(plan?.device.serial)) throw new Error('This TV needs a fresh complete scan after setup changed. Reconnect and scan before applying or restoring a saved preview.'); const result = await operation(plan.mode === 'restore' ? 'restore':'apply',{plan_id:plan.id}); selection = {}; privacySelection.clear(); invalidateSnapshot(result); showPlan(result); await historyList(); });
bind('cancel','click',async () => { if (currentJob) { await api('jobs/' + currentJob + '/cancel',{}); $('cancel').disabled = true; } });
async function prepareUndo(source) {
  if (!source) throw new Error('Choose saved changes to undo first.');
  const journal = await api('plans/' + source); const inv = await scanSelected(journal.device.serial);
  const result = await operation('restore_preview',{inventory_id:inv.id,source_plan_id:source}); $('history-details').open = false; showPlan(result);
}
bind('restore-preview','click',() => prepareUndo($('source-journal').value));
bind('undo-latest','click',() => prepareUndo(resultJournal.id));
bind('download-plan','click',() => { if (plan) download('plan.json',JSON.stringify(plan,null,2)); });
bind('download-validation','click',() => { const report = functionalChecks.report(); download('tv-checks-' + report.source_apply_journal_id + '.json',JSON.stringify(report,null,2)); });
bind('download-restore','click',async () => { if (!plan || plan.mode !== 'apply' || plan.status === 'preview') throw new Error('Choose a started apply journal for recovery export.'); const files = await operation('export',{plan_id:plan.id}); download('restore.py',files['restore.py']); });
(async () => {
  try { const status = await api('status'); $('storage').textContent = 'Private data: ' + status.data_dir + ' · Processing stays on this computer.'; await dependencies(); await devices(); const sessions = await api('sessions'); if (sessions.length) setInventory(sessions[0]); await historyList(); }
  catch (problem) { error(problem); }
})();
