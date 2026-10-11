// Run with UI_PLAYWRIGHT_MODULE_PATH pointing to an installed playwright module.
// These tests use the real DOM and app.js; only the external HTTP API is simulated.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.UI_PLAYWRIGHT_MODULE_PATH || 'playwright');
const web = path.join(__dirname, '../tcl_tv_debloat/web');
let browser;
before(async () => { browser = await chromium.launch({ executablePath: process.env.UI_CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true }); });
after(async () => { await browser?.close(); });
const control = (id, value, overrides = {}) => ({ control_id:id, label:id === 'tcl_bi_reporting' ? 'TCL BI statistics' : 'TCL diagnostics', purpose:'Optional reporting', reason:'Observed on this firmware', features:['Reporting'], evidence:[], eligible:true, current_value:value, read_status:'complete', diagnostic:'', namespace:'global', key:id, target_value:'0', verification:'observed', guidance_level:'exact_firmware', ...overrides });
const packageRecord = { package:'com.example.optional', label:'Optional content app', purpose:'Entertainment', category:'optional', enabled_state:0, disable_eligible:true, features:['Content'], verification:'observed', guidance_level:'exact_firmware', evidence:[], limitations:[], granted_permissions:[], adb_requested_permissions:[], device_paths:[] };
function snapshot(controls) {
  return { id:'inventory-one', captured_at:'2026-10-10T10:00:00', status:'complete', device:{serial:'simulated-tv',manufacturer:'TCL',model:'Simulated',android:'12',active_user:'0',fingerprint:'test/build'}, coverage:{scanned_packages:1,installed_packages:1}, errors:[], packages:[{...packageRecord}], ...(controls === undefined ? {} : { privacy_controls:controls }) };
}
const settingChange = { control_id:'tcl_bi_reporting', label:'TCL BI statistics', namespace:'global', key:'tcl_bi_reporting', before:null, after:'0', purpose:'Optional reporting', reason:'Observed on firmware', features:['Reporting'], verification:'observed', guidance_level:'exact_firmware', evidence:[], action:'reduce_tracking', outcome:'pending', diagnostic:'', owner_versions:{} };
function preview(changes = [], setting_changes = []) { return {id:'plan-one',mode:'apply',status:'preview',device:{serial:'simulated-tv'},identity_assurance:'exact identity',created_at:'2026-10-10T10:01:00',changes,setting_changes}; }
function completedJob(result,status='complete') { return {status,result,error:null,message:'Done',stage:'complete',completed:0,total:null}; }
async function showHistory(page) {
  if (!await page.locator('#history-details').evaluate(node => node.open)) await page.locator('#open-history').click();
}
async function openApp(inv, result = preview(), journals = [], flow = {}) {
  const page = await browser.newPage(); const requests = []; const calls = []; const errors = [];
  page.setDefaultTimeout(3000);
  page.on('pageerror', e => errors.push(e.message));
  await page.route('http://privacy-ui.test/**', async route => {
    const request = route.request(), url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) {
      const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(web,name)),contentType:name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html'});
    }
    const name = url.pathname.slice(5); let data;
    if (Object.hasOwn(flow,name)) { calls.push({operation:name,payload:request.postDataJSON()}); data = typeof flow[name] === 'function' ? flow[name]() : flow[name]; }
    else if (name === 'status') data = {data_dir:'/simulated'};
    else if (name === 'dependencies') data = {standard_ready:true,deep_configured:false,engine_execution_verified:false,dependencies:[]};
    else if (name === 'devices') data = [{serial:'simulated-tv',state:'device'},{serial:'other-simulated-tv',state:'device'}];
    else if (name === 'sessions') data = inv ? [inv] : [];
    else if (name === 'plans') data = journals;
    else if (name === 'preview') { requests.push(request.postDataJSON()); data = {id:'job-one'}; }
    else if (name === 'jobs/job-one') data = {id:'job-one',message:'Done',stage:'preview',completed:1,total:1,status:'complete',result};
    else throw new Error('Unexpected simulated request: ' + name);
    return route.fulfill({json:data});
  });
  await page.goto('http://privacy-ui.test/#private-test-token');
  if (inv) await page.waitForFunction(() => document.getElementById('tv-title').textContent.includes('Simulated'));
  else { await showHistory(page); await page.locator('#history button').first().waitFor(); }
  await page.waitForTimeout(30);
  if (inv) {
    await page.locator('#advanced-details > summary').click();
    await page.locator('#keep-details > summary').click();
    await page.locator('#quick-details > summary').click();
  }
  await showHistory(page);
  return {page,requests,calls,errors};
}
test('privacy controls start unchecked and absent values are not represented as off', async () => {
  // Catches automatic opt-in and treating a missing global setting as zero.
  const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting',null),control('tcl_diagnostics','1')]));
  assert.equal(await page.locator('#privacy-controls input[type=checkbox]').count(),2);
  assert.equal(await page.locator('#privacy-controls input:checked').count(),0);
  assert.match(await page.locator('#privacy-controls').innerText(),/Not set.*defaults may allow reporting/);
  assert.equal(await page.locator('#preview').isDisabled(),true);
  assert.deepEqual(errors,[]); await page.close();
});
test('privacy-only selection reaches preview and counts as an executable change', async () => {
  // Catches omission of privacy IDs from the request or package-only button totals.
  const {page,requests,errors} = await openApp(snapshot([control('tcl_bi_reporting',null),control('tcl_diagnostics','1')]),preview([],[settingChange]));
  await page.locator('#privacy-tcl_bi_reporting').check(); await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.deepEqual(requests,[{inventory_id:'inventory-one',selection:{},privacy_selection:['tcl_bi_reporting']}]);
  assert.equal(await page.locator('#execute').isDisabled(),false);
  assert.match(await page.locator('#changes').innerText(),/Not set.*→.*Off/);
  assert.doesNotMatch(await page.locator('#changes').innerText(),/No effective changes/);
  assert.deepEqual(errors,[]); await page.close();
});
test('unsupported, failed reads and already-off controls cannot be selected', async () => {
  // Catches enabling a control whose value or firmware guidance is not usable.
  for (const overrides of [{eligible:false},{read_status:'failed',diagnostic:'<img src=x onerror=alert(1)>'},{current_value:'0'}]) {
    const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting','1',overrides)]));
    assert.equal(await page.locator('#privacy-tcl_bi_reporting').isDisabled(),true);
    assert.equal(await page.locator('#privacy-controls img').count(),0);
    if (overrides.current_value === '0') assert.match(await page.locator('#privacy-controls').innerText(),/Already off/);
    assert.deepEqual(errors,[]); await page.close();
  }
});
test('older inventories retain package-only preview compatibility', async () => {
  // Catches sending new API fields unconditionally to an older saved inventory.
  const {page,requests,errors} = await openApp(snapshot(),preview([{package:'com.example.optional',before:0,after:3,outcome:'pending'}]));
  assert.match(await page.locator('#privacy-controls').innerText(),/Rescan/i);
  await page.locator('#action-com\\.example\\.optional').selectOption('disable'); await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.deepEqual(requests,[{inventory_id:'inventory-one',selection:{'com.example.optional':'disable'}}]);
  assert.deepEqual(errors,[]); await page.close();
});
test('a setting-only journal invalidates both selections and contributes to history totals', async () => {
  // Catches package-only stale checks, stale preview application and wrong totals.
  const journal = {...preview([],[{...settingChange,outcome:'success'}]),status:'complete'};
  const journals = [];
  const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting','1')]),preview([],[settingChange]),journals);
  await page.locator('#privacy-tcl_bi_reporting').check(); await page.locator('#action-com\\.example\\.optional').selectOption('disable');
  await page.locator('#preview').click(); await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  journals.push(journal); await page.locator('#refresh-history').click(); await page.waitForFunction(() => document.getElementById('coverage').textContent.includes('Rescan'));
  assert.match(await page.locator('#history').innerText(),/1 changes/);
  assert.equal(await page.locator('#privacy-tcl_bi_reporting').isDisabled(),true);
  assert.equal(await page.locator('#privacy-controls input:checked').count(),0);
  assert.equal(await page.locator('#action-com\\.example\\.optional').inputValue(),'keep');
  assert.equal(await page.locator('#action-com\\.example\\.optional').isDisabled(),true);
  assert.equal(await page.locator('#preview').isDisabled(),true);
  assert.equal(await page.locator('#preview-panel').isHidden(),true);
  assert.equal(await page.locator('#execute').isDisabled(),true);
  assert.match(await page.locator('#coverage').innerText(),/Rescan/);
  assert.deepEqual(errors,[]); await page.close();
});
test('restore preview shows the original absence of a global reporting setting', async () => {
  // Catches treating a restore-to-absence as an off value or an empty plan.
  const restore = {...preview([],[{...settingChange,before:'0',after:null,action:'restore'}]),mode:'restore'};
  const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting','1')]),restore);
  await page.locator('#privacy-tcl_bi_reporting').check(); await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.match(await page.locator('#changes').innerText(),/Off.*→.*Not set/);
  assert.equal(await page.locator('#execute').isDisabled(),false);
  assert.match(await page.locator('#execute').innerText(),/Restore/);
  assert.deepEqual(errors,[]); await page.close();
});
test('new scan clears the selected package and privacy control', async () => {
  // Catches leaving optional privacy consent selected when starting over.
  const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting','1')]));
  await page.locator('#privacy-tcl_bi_reporting').check(); await page.locator('#action-com\\.example\\.optional').selectOption('disable');
  await page.locator('#new-scan').click();
  assert.equal(await page.locator('#privacy-controls input:checked').count(),0);
  assert.equal(await page.locator('#action-com\\.example\\.optional').inputValue(),'keep');
  assert.equal(await page.locator('#preview').isDisabled(),true);
  assert.deepEqual(errors,[]); await page.close();
});

test('validation is available for an apply journal, never for a preview', async () => {
  // Catches collecting results against changes that have not been attempted.
  const {page,errors} = await openApp(snapshot([control('tcl_bi_reporting','1')]),preview([],[settingChange]));
  await page.locator('#privacy-tcl_bi_reporting').check(); await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.equal(await page.locator('#validation-panel').isHidden(),true);
  assert.deepEqual(errors,[]); await page.close();
});

test('downloaded checks retain their source journal and never mark untested features as working', async () => {
  // Catches exporting another TV's context, credentials, or an invented pass.
  const inv=snapshot([control('tcl_bi_reporting','1')]);
  const journal={...preview([],[{...settingChange,outcome:'successful'}]),id:'apply-one',inventory_id:inv.id,status:'complete',device:{...inv.device},started_at:'2026-10-10T10:01:01',finished_at:'2026-10-10T10:01:02'};
  const {page,errors}=await openApp(inv,preview(),[journal]);
  await showHistory(page); await page.locator('#history button').click();
  await page.locator('#manual-checks summary').click();
  await page.locator('#validation-streaming').selectOption('working');
  await page.locator('#validation-hdmi').selectOption('problem');
  await page.locator('#report-details > summary').click();
  await page.locator('#validation-notes').fill('No sound on HDMI');
  if (!await page.locator('#report-details').evaluate(node => node.open)) await page.locator('#report-details > summary').click();
  const downloaded=page.waitForEvent('download'); await page.locator('#download-validation').click();
  const report=JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
  assert.equal(report.source_apply_journal_id,'apply-one');
  assert.equal(report.baseline_inventory.id,'inventory-one');
  assert.equal(report.baseline_inventory.device.fingerprint,'test/build');
  assert.equal(report.checks.streaming.result,'working');
  assert.equal(report.checks.hdmi.result,'problem');
  assert.equal(report.checks.casting.result,'untested');
  assert.equal(report.network_verification,'not_performed');
  assert.equal(report.notes,'No sound on HDMI');
  assert.equal(JSON.stringify(report).includes('private-test-token'),false);
  assert.deepEqual(errors,[]); await page.close();
});

test('functional results stay with their journal when reviewing another TV', async () => {
  // Catches carrying a good playback result over to another TV/journal.
  const inv=snapshot([control('tcl_bi_reporting','1')]);
  const first={...preview([],[{...settingChange,outcome:'successful'}]),id:'apply-one',inventory_id:inv.id,status:'complete',device:{...inv.device}};
  const second={...first,id:'apply-two',inventory_id:'other-inventory',device:{...inv.device,serial:'other-simulated-tv',fingerprint:'other/build'}};
  const {page,errors}=await openApp(inv,preview(),[first,second]);
  await showHistory(page); await page.locator('#history button').nth(0).click();
  await page.locator('#manual-checks summary').click();
  await page.locator('#validation-streaming').selectOption('working');
  await showHistory(page); await page.locator('#history button').nth(1).click();
  assert.equal(await page.locator('#validation-streaming').inputValue(),'untested');
  if (!await page.locator('#report-details').evaluate(node => node.open)) await page.locator('#report-details > summary').click();
  const downloaded=page.waitForEvent('download'); await page.locator('#download-validation').click();
  const report=JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
  assert.equal(report.source_apply_journal_id,'apply-two');
  assert.equal(report.device.serial,'other-simulated-tv');
  assert.equal(report.baseline_inventory,null);
  await showHistory(page); await page.locator('#history button').nth(0).click();
  assert.equal(await page.locator('#validation-streaming').inputValue(),'working');
  assert.deepEqual(errors,[]); await page.close();
});

test('a saved journal remains usable when its original inventory is unavailable', async () => {
  // Catches failing to open older saved changes, or inventing a missing baseline.
  const journal={...preview([],[{...settingChange,outcome:'successful'}]),status:'complete'};
  const {page,errors}=await openApp(null,preview(),[journal]);
  await showHistory(page); await page.locator('#history button').click();
  await page.locator('#manual-checks summary').click();
  assert.equal(await page.locator('#validation-streaming').inputValue(),'untested');
  if (!await page.locator('#report-details').evaluate(node => node.open)) await page.locator('#report-details > summary').click();
  const downloaded=page.waitForEvent('download'); await page.locator('#download-validation').click();
  const report=JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
  assert.equal(report.source_apply_journal_id,journal.id);
  assert.equal(report.baseline_inventory,null);
  assert.deepEqual(errors,[]); await page.close();
});

test('one-click privacy uses a fresh scan and applies only supported flags', async () => {
  // Catches changing apps or trusting obsolete flag values in the shortcut.
  const old=snapshot([control('tcl_bi_reporting','1'),control('tcl_diagnostics','1')]);
  const fresh={...snapshot([control('tcl_bi_reporting',null),control('tcl_diagnostics','0')]),id:'fresh-inventory'};
  const plan={...preview([],[settingChange]),inventory_id:fresh.id,device:{...fresh.device}};
  const applied={...plan,status:'complete',setting_changes:[{...settingChange,outcome:'successful'}]};
  const after={...fresh,id:'after-inventory',captured_at:'2026-10-10T10:02:00',privacy_controls:[control('tcl_bi_reporting','0'),control('tcl_diagnostics','0')]};
  let scans=0;
  const flow={scan:() => ({id:++scans===1 ? 'scan-job' : 'after-job'}),'jobs/scan-job':completedJob(fresh),'jobs/after-job':completedJob(after),preview:{id:'preview-job'},'jobs/preview-job':completedJob(plan),apply:{id:'apply-job'},'jobs/apply-job':completedJob(applied)};
  const {page,calls,errors}=await openApp(old,preview(),[],flow);
  await page.locator('#action-com\\.example\\.optional').selectOption('disable');
  await page.locator('#quick-privacy').click();
  await page.waitForFunction(() => document.getElementById('quick-privacy-status').textContent.includes('verified'));
  assert.deepEqual(calls.filter(c => ['scan','preview','apply'].includes(c.operation)),[
    {operation:'scan',payload:{serial:'simulated-tv',deep:false}},
    {operation:'preview',payload:{inventory_id:'fresh-inventory',selection:{},privacy_selection:['tcl_bi_reporting']}},
    {operation:'apply',payload:{plan_id:'plan-one'}},
    {operation:'scan',payload:{serial:'simulated-tv',deep:false}}
  ]);
  assert.equal(await page.locator('#suggest-apps').isDisabled(),false);
  assert.match(await page.locator('#automatic-checks').innerText(),/1.*verified/i);
  assert.equal(await page.locator('#validation-streaming').inputValue(),'untested');
  assert.deepEqual(errors,[]); await page.close();
});

test('one-click privacy never applies when flags are off, unavailable or identity changed', async () => {
  // Catches creating writes without supported targets or to a different TV.
  for (const kind of ['off','unsupported','different-tv','cancelled']) {
    const fresh=snapshot([control('tcl_bi_reporting','0'),control('tcl_diagnostics','0')]);
    if (kind==='unsupported') fresh.privacy_controls=[control('tcl_bi_reporting','1',{eligible:false})];
    if (kind==='different-tv') {fresh.device.serial='other-tv';fresh.privacy_controls=[control('tcl_bi_reporting','1')];}
    if (kind==='cancelled') {fresh.status='cancelled';fresh.privacy_controls=[control('tcl_bi_reporting','1')];}
    const flow={scan:{id:'scan-job'},'jobs/scan-job':completedJob(fresh,kind==='cancelled' ? 'cancelled' : 'complete')};
    const {page,calls,errors}=await openApp(snapshot([control('tcl_bi_reporting','1')]),preview(),[],flow);
    await page.locator('#quick-privacy').click();
    await page.waitForFunction(() => !document.getElementById('quick-privacy').disabled);
    assert.deepEqual(calls.filter(c => ['preview','apply'].includes(c.operation)),[]);
    assert.equal(await page.locator('#error').isHidden(),true);
    assert.deepEqual(errors,[]); await page.close();
  }
});

test('suggested apps preserve wanted functions and never select unknown or protected packages', async () => {
  // Catches indiscriminate bulk disabling and preferences that only show advice.
  const inv=snapshot([]);
  inv.packages=[
    {...packageRecord,package:'com.tcl.repairguide'},
    {...packageRecord,package:'com.netflix.ninja'},
    {...packageRecord,package:'com.tcl.smartalexa'},
    {...packageRecord,package:'com.tcl.hearaid'},
    {...packageRecord,package:'com.tcl.magiconnectfree'},
    {...packageRecord,package:'com.tcl.logkit',category:'protected',disable_eligible:false},
    {...packageRecord,package:'unknown.app',category:'unknown',disable_eligible:false},
    {...packageRecord,package:'com.tcl.usercenter'},
    {...packageRecord,package:'com.google.android.feedback',enabled_state:3}
  ];
  const {page,requests,errors}=await openApp(inv);
  await page.locator('#suggest-apps').click();
  await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.deepEqual(requests[0],{inventory_id:'inventory-one',selection:{'com.tcl.repairguide':'disable'}});
  await page.locator('#edit-selection').click();
  await page.locator('#feature-preferences input[value=streaming]').uncheck();
  await page.locator('#feature-preferences input[value=voice]').uncheck();
  await page.locator('#preview').click();
  await page.waitForFunction(() => !document.getElementById('preview-panel').hidden);
  assert.deepEqual(requests[1],{inventory_id:'inventory-one',selection:{'com.tcl.repairguide':'disable','com.netflix.ninja':'disable','com.tcl.smartalexa':'disable'}});
  assert.deepEqual(errors,[]); await page.close();
});

test('automatic state verification never treats uncertain or pending changes as a pass', async () => {
  // Catches presenting a failed apply as a successful automatic check.
  const journal={...preview([{package:'com.example.optional',before:0,after:3,outcome:'uncertain'}],[{...settingChange,outcome:'pending'}]),status:'failed'};
  const {page,errors}=await openApp(snapshot([]),preview(),[journal]);
  await showHistory(page); await page.locator('#history button').click();
  assert.match(await page.locator('#automatic-checks').innerText(),/0.*verified/i);
  assert.match(await page.locator('#automatic-checks').innerText(),/1.*uncertain/i);
  assert.match(await page.locator('#automatic-checks').innerText(),/1.*not completed/i);
  if (!await page.locator('#report-details').evaluate(node => node.open)) await page.locator('#report-details > summary').click();
  const downloaded=page.waitForEvent('download'); await page.locator('#download-validation').click();
  const report=JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
  assert.equal(report.automatic_checks[0].result,'uncertain');
  assert.equal(report.automatic_checks[1].result,'not_completed');
  assert.equal(report.checks.streaming.result,'untested');
  assert.deepEqual(errors,[]); await page.close();
});
