'use strict';

// Checks belong to an apply journal, not whichever TV is currently scanned.
class FunctionalChecks {
  constructor(panel, create) {
    this.panel = panel; this.create = create; this.records = new Map(); this.current = null;
    this.tests = [
      ['home', 'Home and settings', 'Open Home and Settings, then return to Home.'],
      ['remote', 'Remote control', 'Check navigation, OK and Back on the remote.'],
      ['audio', 'Sound and volume', 'Check sound, volume up/down and mute.'],
      ['hdmi', 'HDMI', 'Use a connected device and check picture and sound.'],
      ['tuner', 'Live channels', 'Change between two tuned channels and check picture and sound.'],
      ['streaming', 'Streaming / Netflix', 'Play a video for at least 30 seconds and check picture and sound.'],
      ['casting', 'Casting', 'Send a video from a phone on the same network and check picture and sound.'],
      ['voice', 'Voice control', 'Use the microphone button to ask the TV to open an app.'],
      ['accessibility', 'Accessibility features', 'Exercise the accessibility services you use; opening their menu alone is insufficient.'],
      ['updates', 'System update menu', 'Check that the update menu opens. This does not test downloading or installing an update.'],
      ['restart', 'After restarting', 'Restart from the TV menu, then check Home and video playback again.']
    ];
    panel.querySelector('#validation-notes').addEventListener('input', event => {
      if (this.current) this.current.notes = event.target.value.slice(0, 2000);
    });
  }

  hide() { this.panel.hidden = true; this.current = null; }

  show(journal, inventory) {
    if (journal.mode !== 'apply' || journal.status === 'preview' || !(journal.changes?.length || journal.setting_changes?.length)) { this.hide(); return; }
    const revision = JSON.stringify([journal.status, journal.finished_at, journal.changes, journal.setting_changes]);
    let record = this.records.get(journal.id);
    if (!record || record.revision !== revision) {
      const sameSnapshot = inventory && inventory.id === journal.inventory_id && ['serial', 'hardware_id', 'fingerprint'].every(key => inventory.device[key] === journal.device[key]);
      record = {
        revision, schema_version: 1, kind: 'functional_validation', created_at: new Date().toISOString(),
        source_apply_journal_id: journal.id, device: structuredClone(journal.device), journal_status: journal.status,
        recorded_changes: structuredClone({packages: journal.changes || [], settings: journal.setting_changes || []}),
        automatic_checks: [...(journal.changes || []), ...(journal.setting_changes || [])].map(change => ({
          target: change.package || change.key, expected_value: change.after, source: 'saved_apply_journal', method: 'apply_readback',
          result: change.outcome === 'successful' ? 'verified' : change.outcome === 'uncertain' ? 'uncertain' : change.outcome === 'unchanged' ? 'unchanged' : 'not_completed',
          diagnostic: change.diagnostic || '', journal_finished_at: journal.finished_at || null
        })),
        baseline_inventory: sameSnapshot ? structuredClone({
          id: inventory.id, captured_at: inventory.captured_at, device: inventory.device,
          package_versions: inventory.packages.map(p => ({package: p.package, version_code: p.version_code, version_name: p.version_name})),
          reporting_settings: (inventory.privacy_controls || []).map(c => ({key: c.key, value: c.current_value, read_status: c.read_status}))
        }) : null,
        result_source: 'owner_reported', network_verification: 'not_performed',
        checks: Object.fromEntries(this.tests.map(([id, label, scope]) => [id, {label, scope, result: 'untested', checked_at: null}])), notes: ''
      };
      this.records.set(journal.id, record);
    }
    this.current = record; this.panel.hidden = false;
    const automatic = this.panel.querySelector('#automatic-checks'); automatic.replaceChildren();
    const counts = {verified:0, uncertain:0, unchanged:0, not_completed:0};
    record.automatic_checks.forEach(check => counts[check.result]++);
    automatic.open = counts.uncertain > 0 || counts.not_completed > 0;
    const body = this.create('div',undefined,'disclosure-body');
    automatic.append(this.create('summary','Verification details'),body);
    body.append(this.create('p',counts.verified + ' verified · ' + counts.uncertain + ' uncertain · ' + counts.not_completed + ' not completed · ' + counts.unchanged + ' unchanged'));
    body.append(this.create('p','Saved checks of app states and settings. Picture, sound and network traffic are not verified.'));
    for (const check of record.automatic_checks) body.append(this.create('p',check.target + ' · ' + check.result + (check.diagnostic ? ' · ' + check.diagnostic : '')));
    this.panel.querySelector('#validation-meta').textContent = (journal.device.model || journal.device.serial) + ' · Journal ' + journal.id + ' · ' + journal.status;
    const list = this.panel.querySelector('#validation-checks'); list.replaceChildren();
    for (const [id, label, scope] of this.tests) {
      const row = this.create('div', undefined, 'functional-check'), copy = this.create('div'), input = this.create('select'), title = this.create('label', label);
      input.id = 'validation-' + id; title.htmlFor = input.id;
      for (const [value, text] of [['untested', 'Not tested'], ['working', 'Works'], ['problem', 'Problem'], ['not_applicable', 'Not used / unavailable']]) {
        const option = this.create('option', text); option.value = value; input.append(option);
      }
      input.value = record.checks[id].result;
      input.addEventListener('change', () => {
        record.checks[id].result = input.value;
        record.checks[id].checked_at = input.value === 'untested' ? null : new Date().toISOString(); this.summary();
      });
      copy.append(title, this.create('small', scope)); row.append(copy, input); list.append(row);
    }
    this.panel.querySelector('#validation-notes').value = record.notes; this.summary();
  }

  summary() {
    const counts = {working: 0, problem: 0, untested: 0, not_applicable: 0};
    Object.values(this.current.checks).forEach(check => counts[check.result]++);
    this.panel.querySelector('#validation-summary').textContent = counts.working + ' work · ' + counts.problem + ' problems · ' + counts.untested + ' not tested · ' + counts.not_applicable + ' not used';
  }

  report() {
    if (!this.current) throw new Error('Choose a saved apply journal before recording checks.');
    const {revision, ...report} = this.current;
    return {...structuredClone(report), exported_at: new Date().toISOString()};
  }
}
