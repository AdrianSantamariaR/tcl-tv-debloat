'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('tv-session-token') || '';
if (token) sessionStorage.setItem('tv-session-token', token);
history.replaceState(null, '', location.pathname);
let inventory = null, plan = null, selection = {}, currentJob = null, readiness = null, busy = false;
const stateNames = ['Default (0)', 'Enabled (1)', 'Disabled (2)', 'Disabled for user (3)', 'Disabled until used (4)'];
const categoryNames = {protected:'Protected', optional:'Optional · reviewed match', review:'Needs review', unknown:'Unknown'};
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function error(e) { $('error').textContent = e.message || String(e); $('error').hidden = false; }
function clearError() { $('error').hidden = true; }
async function api(path, payload) {
  const response = await fetch('/api/' + path, {method:payload === undefined ? 'GET':'POST', headers:{'X-Session-Token':token, 'Content-Type':'application/json'}, ...(payload === undefined ? {} : {body:JSON.stringify(payload)})});
  const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed.'); return result;
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('button').forEach(button => { button.disabled = value && button.id !== 'cancel'; });
  if (!value) { $('execute').disabled = !plan || plan.status !== 'preview' || !plan.changes.length; $('preview').disabled = !inventory || !Object.keys(selection).length; }
  $('scan').disabled = value || !readiness?.standard_ready;
  for (const id of ['device','address','pair-address','pair-code','source-journal']) $(id).disabled = value;
  document.querySelectorAll('input[name=analysis]').forEach(input => { input.disabled = value || (input.id === 'deep-choice' && !readiness?.deep_configured); });
  if (inventory) for (const p of inventory.packages) { const select = $('action-' + p.package); if (select) select.disabled = value || !p.disable_eligible; }
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
  readiness = await api('dependencies'); $('dependencies').replaceChildren();
  for (const dependency of readiness.dependencies) {
    const box = el('div', undefined, 'dependency'); box.append(el('strong', dependency.name), el('span', dependency.status, 'badge'), el('p', dependency.purpose), el('small', (dependency.version || 'Version unavailable') + ' · ' + dependency.detail));
    const link = el('a', 'Setup instructions ↗'); link.href = dependency.setup_url; link.target = '_blank'; link.rel = 'noreferrer'; box.append(link); $('dependencies').append(box);
  }
  $('deep-choice').disabled = !readiness.deep_configured;
  if (!readiness.deep_configured) document.querySelector('input[value=standard]').checked = true;
  $('deep-status').textContent = readiness.engine_execution_verified ? 'Engine execution verified on an artifact in this launch.' : readiness.deep_configured ? 'Dependencies configured. The engine is verified only after its first valid APK inspection.' : 'Deep analysis needs the tools listed above. You can continue with a standard scan.';
  updateScanButton(); setBusy(busy);
}
function updateScanButton() { $('scan').textContent = $('deep-choice').checked ? 'Scan with deep analysis':'Continue with standard scan'; }
async function devices() {
  const old = $('device').value; const connected = await api('devices'); $('device').replaceChildren(el('option', 'Select an authorized TV')); $('device').firstChild.value = '';
  for (const d of connected) { const option = el('option', d.serial + ' · ' + d.state); option.value = d.serial; option.disabled = d.state !== 'device'; $('device').append(option); }
  if (connected.some(d => d.serial === old && d.state === 'device')) $('device').value = old;
  else if (connected.filter(d => d.state === 'device').length === 1) $('device').value = connected.find(d => d.state === 'device').serial;
}
function setInventory(value) {
  inventory = value; selection = {}; plan = null; $('preview-panel').hidden = true; $('inventory-panel').hidden = false; $('wizard').hidden = true;
  const d = value.device; $('tv-title').textContent = d.manufacturer + ' · ' + d.model;
  $('identity').textContent = 'Android ' + d.android + ' · Active user ' + d.active_user + ' · ' + d.fingerprint;
  $('coverage').textContent = value.status + ' inventory · ' + value.coverage.scanned_packages + ' / ' + value.coverage.installed_packages + ' packages · Android user 0' + (value.coverage.rea_status ? ' · REA ' + value.coverage.rea_status + ': ' + value.coverage.rea_successful + ' successful, ' + value.coverage.rea_failed + ' failed' : '') + (value.errors.length ? ' · ' + value.errors.join(' ') : '');
  $('counts').replaceChildren(); const all = {all:value.packages.length, protected:0, optional:0, review:0, unknown:0}; value.packages.forEach(p => all[p.category]++);
  for (const [key, count] of Object.entries(all)) { const box = el('div'); box.append(el('strong', count), el('span', key === 'all' ? 'Packages found' : categoryNames[key])); $('counts').append(box); }
  renderPackages(); setBusy(busy);
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
    select.addEventListener('change', () => { if (select.value === 'keep') delete selection[p.package]; else selection[p.package] = select.value; updateSelection(); plan = null; $('preview-panel').hidden = true; });
    const features = {casting:/mediashell|miracast|airplay|magiconnect|tclhome/i,voice:/katniss|smartalexa|android.tts/i,accessibility:/hearaid|talkback|android.tts/i,streaming:/netflix|disney|youtube|spotify|amazonvideo|atresplayer|movistar|rtve|wbd.stream|android.videos/i};
    const retained = [...document.querySelectorAll('#feature-preferences input:checked')].map(input => input.value).filter(feature => features[feature].test(p.package));
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
  if (!inventory || journal.device.serial !== inventory.device.serial || !journal.changes.length || journal.status === 'preview') return;
  inventory.coverage.stale = true; selection = {};
  for (const p of inventory.packages) { p.disable_eligible = false; }
  $('coverage').textContent = 'Saved inventory snapshot · Changes were attempted after this scan. Rescan this TV before choosing further changes; use the journal for outcomes.';
  renderPackages();
}
function updateSelection() { $('selected-count').textContent = Object.keys(selection).length + ' selected'; $('preview').disabled = busy || !Object.keys(selection).length; }
function showPlan(value) {
  plan = value; $('preview-panel').hidden = false; $('plan-title').textContent = (value.mode === 'restore' ? 'Restoration':'Change') + ' ' + (value.status === 'preview' ? 'preview':'journal');
  $('plan-meta').textContent = value.status + ' · Android user 0 · ' + value.identity_assurance + ' · Plan ' + value.id + (value.source_plan_id ? ' · Source ' + value.source_plan_id : '');
  $('changes').replaceChildren();
  for (const c of value.changes) {
    const row = el('div',undefined,'change'); row.append(el('strong',c.package), el('p',stateNames[c.before] + ' → ' + stateNames[c.after] + ' · ' + c.outcome + (c.diagnostic ? ' · ' + c.diagnostic : '')));
    row.append(el('p',c.purpose || 'See the saved inventory for this package’s function.'), el('p','Feature impact: ' + (c.features?.join(', ') || 'Not established; review the package details.')),
      el('small',(c.reason || 'Individually selected optional package.') + ' · ' + (c.verification || 'observed') + ' guidance · ' + (c.guidance_level || 'saved inventory') + ' · ' + (c.evidence?.length || 0) + ' evidence records'));
    $('changes').append(row);
  }
  if (!value.changes.length) $('changes').append(el('p','No effective changes: the selected packages already have the requested states.'));
  $('execute').textContent = value.mode === 'restore' ? 'Restore this preview':'Apply this preview'; setBusy(busy);
}
async function historyList() {
  const journals = await api('plans'); const old = $('source-journal').value; $('source-journal').replaceChildren(el('option','Choose a saved apply journal')); $('source-journal').firstChild.value = ''; $('history').replaceChildren();
  for (const j of journals) {
    if (j.mode === 'apply' && j.status !== 'preview') { const option = el('option',j.created_at.slice(0,19) + ' · ' + j.status + ' · ' + j.id); option.value = j.id; $('source-journal').append(option); }
    const row = el('div',undefined,'history-row'), button = el('button','View'); row.append(el('span',j.mode + ' · ' + j.status + ' · ' + j.changes.length + ' changes · ' + j.created_at.slice(0,19)),button); button.addEventListener('click',() => showPlan(j)); $('history').append(row);
  }
  if (journals.some(j => j.id === old)) $('source-journal').value = old;
  if (!journals.length) $('history').append(el('p','No saved changes yet.'));
  if (inventory) for (const journal of journals) if ((journal.finished_at || journal.started_at || journal.created_at) > inventory.captured_at) invalidateSnapshot(journal);
}
function download(name, content) { const url = URL.createObjectURL(new Blob([content], {type:'text/plain'})); const anchor = el('a'); anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url),1000); }
function bind(id,event,fn) { $(id).addEventListener(event,async e => { if (event === 'submit') e.preventDefault(); try { await fn(e); } catch (problem) { error(problem); } }); }
bind('recheck','click',dependencies); bind('refresh-devices','click',devices); bind('refresh-history','click',historyList);
bind('new-scan','click',async () => { selection = {}; plan = null; $('preview-panel').hidden = true; $('wizard').hidden = false; renderPackages(); await dependencies(); await devices(); });
bind('device','change',() => { inventory = null; selection = {}; plan = null; $('inventory-panel').hidden = true; $('preview-panel').hidden = true; });
bind('connect-form','submit',async () => { const r = await operation('connect',{address:$('address').value.trim()}); $('connection-message').textContent = r.message; await devices(); });
bind('pair-form','submit',async () => { const code = $('pair-code').value; $('pair-code').value = ''; const r = await operation('pair',{address:$('pair-address').value.trim(),code}); $('connection-message').textContent = r.message; });
async function scanSelected(serial,deep=false) { if (!serial) throw new Error('Select an authorized TV first.'); const inv = await operation('scan',{serial,deep}); setInventory(inv); await historyList(); return inv; }
bind('scan','click',async () => { await scanSelected($('device').value,$('deep-choice').checked); });
bind('rescan','click',async () => { $('wizard').hidden = false; await dependencies(); await devices(); $('wizard').scrollIntoView({behavior:'smooth'}); });
document.querySelectorAll('#feature-preferences input').forEach(input => input.addEventListener('change',renderPackages));
document.querySelectorAll('input[name=analysis]').forEach(radio => radio.addEventListener('change',updateScanButton));
bind('search','input',renderPackages); bind('category','change',renderPackages);
bind('preview','click',async () => { const p = await operation('preview',{inventory_id:inventory.id,selection}); showPlan(p); await historyList(); $('preview-panel').scrollIntoView({behavior:'smooth'}); });
bind('execute','click',async () => { const result = await operation(plan.mode === 'restore' ? 'restore':'apply',{plan_id:plan.id}); selection = {}; invalidateSnapshot(result); showPlan(result); await historyList(); });
bind('cancel','click',async () => { if (currentJob) { await api('jobs/' + currentJob + '/cancel',{}); $('cancel').disabled = true; } });
bind('restore-preview','click',async () => {
  const source = $('source-journal').value; if (!source) throw new Error('Choose a source apply journal first.');
  const journal = await api('plans/' + source); const inv = await scanSelected(journal.device.serial);
  const result = await operation('restore_preview',{inventory_id:inv.id,source_plan_id:source}); showPlan(result); await historyList(); $('preview-panel').scrollIntoView({behavior:'smooth'});
});
bind('download-plan','click',() => { if (plan) download('plan.json',JSON.stringify(plan,null,2)); });
bind('download-restore','click',async () => { if (!plan || plan.mode !== 'apply' || plan.status === 'preview') throw new Error('Choose a started apply journal for recovery export.'); const files = await operation('export',{plan_id:plan.id}); download('restore.py',files['restore.py']); });
(async () => {
  try { const status = await api('status'); $('storage').textContent = 'Private data: ' + status.data_dir + ' · Processing stays on this computer.'; await dependencies(); await devices(); const sessions = await api('sessions'); if (sessions.length) setInventory(sessions[0]); await historyList(); }
  catch (problem) { error(problem); }
})();
