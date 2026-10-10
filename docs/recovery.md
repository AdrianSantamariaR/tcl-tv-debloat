# Apply, undo and recover

Every new selection starts at **Keep as is**. Only eligible reviewed packages can be disabled, and changes affect Android user 0. A preview contains only effective changes and explains the selected package’s purpose, feature impact and evidence level. It is saved before execution. Apply checks the connected device, firmware, active user, every selected version and every selected state before sending the first command.

The journal is saved durably before the command and updated after verification. If a response is lost, the outcome is **uncertain**; the device may already have changed. Execution stops. A duplicate started plan ID returns its journal and does not repeat commands.

After apply or restoration, the browser marks its old inventory as a snapshot and clears selections. Rescan before choosing more changes; the journal shows the actual confirmed or uncertain outcomes. Target and package-action controls are locked while an operation runs.

## Browser restoration

1. Choose the **source apply journal** from saved history.
2. Select **Preview restoration**. The app performs a fresh read-only scan.
3. Review the original/expected states and select **Restore this preview**.

Already-original states are unchanged. A later state outside original/expected values, a different firmware, changed package version or different device blocks restoration for review. Protected status does not block legitimate journal-based recovery.

A pending entry from an interrupted process is also recoverable: the fresh device state determines whether it is still original or at the expected disabled state. No baseline is invented for packages without a recorded journal.

## Exported recovery

From a started apply journal, download its JSON and the restore launcher. Keep them together as `plan.json` and `restore.py`. The launcher calls the installed engine:

```sh
python restore.py
```

Or use `tcl-tv-debloat restore --journal plan.json`. This creates a fresh preview and asks for confirmation. If the app was removed, reinstall it first. The launcher is not a standalone second recovery engine.

State 0 means Android's default enabled state; restoration uses `pm default-state`, not an unconditional `pm enable`. States 1–4 also map to their exact package-manager operation. If the firmware rejects an operation, the tool reports it and stops.

Journals are package-state records, not app-data backups. Preserve them across application upgrades. A failed/uncertain journal remains useful after restarting the server. The browser's new launch token changes while the saved history remains in `~/.tcl-tv-debloat/`.
