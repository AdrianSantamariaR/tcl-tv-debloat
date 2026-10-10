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
async function openApp(inv, result = preview(), journals = []) {
  const page = await browser.newPage(); const requests = []; const errors = [];
  page.setDefaultTimeout(3000);
  page.on('pageerror', e => errors.push(e.message));
  await page.route('http://privacy-ui.test/**', async route => {
    const request = route.request(), url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) {
      const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      return route.fulfill({body:fs.readFileSync(path.join(web,name)),contentType:name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html'});
    }
    const name = url.pathname.slice(5); let data;
    if (name === 'status') data = {data_dir:'/simulated'};
    else if (name === 'dependencies') data = {standard_ready:true,deep_configured:false,engine_execution_verified:false,dependencies:[]};
    else if (name === 'devices') data = [{serial:'simulated-tv',state:'device'},{serial:'other-simulated-tv',state:'device'}];
    else if (name === 'sessions') data = [inv];
    else if (name === 'plans') data = journals;
    else if (name === 'preview') { requests.push(request.postDataJSON()); data = {id:'job-one'}; }
    else if (name === 'jobs/job-one') data = {id:'job-one',message:'Done',stage:'preview',completed:1,total:1,status:'complete',result};
    else throw new Error('Unexpected simulated request: ' + name);
    return route.fulfill({json:data});
  });
  await page.goto('http://privacy-ui.test/'); await page.waitForFunction(() => document.getElementById('tv-title').textContent.includes('Simulated'));
  await page.waitForTimeout(30);
  return {page,requests,errors};
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
