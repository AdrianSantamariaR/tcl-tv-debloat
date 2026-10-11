# Apply, undo and recover

A fresh scan selects no changes until the owner chooses a goal or individual controls. Goals prepare reviewed suggestions; they do not apply them. Only eligible reviewed packages can be disabled; those changes affect Android user 0. Individually selected TCL reporting controls affect the whole device. A preview contains only effective changes and explains the selected package’s purpose, feature impact and evidence level. It is saved before execution. Apply checks the connected device, firmware, active user, every selected version and every selected state before sending the first command.

Before applying or restoring, the engine saves the original states durably and reads the file back to check its contents. A failed save or readback blocks all TV changes. Unchecked or failed recovery records cannot be used to restore. New journals include a checksum of the original states. Loading, restoration and export check it so accidental corruption cannot supply different restore values, even if recording an earlier error failed. The journal is updated after each verified change. If a response is lost, the outcome is **uncertain**; the device may already have changed. Execution stops. A duplicate started plan ID returns its journal and does not repeat commands.

The progress screen shows device checks, recovery saving, changes and verification. Its counter advances only after a change has been checked and saved. **Stop after current change** allows a command already sent to finish and be verified before stopping the next change.

After apply or restoration, the browser marks its old inventory as a snapshot and clears selections. Rescan before choosing more changes; the journal shows the actual confirmed or uncertain outcomes. Target and package-action controls are locked while an operation runs.

## Browser restoration

1. From the result, select **Undo these changes**. For an earlier operation, open **History**, choose its saved apply journal and select **Review undo**.
2. The app performs a fresh read-only scan of the journal’s TV.
3. Confirm the TV identity and recorded states, then select **Restore these changes**.

Already-original states are unchanged. A later state outside original/expected values, a different firmware, changed package version or different device blocks restoration for review. Protected status does not block legitimate journal-based recovery.

A pending change entry from an interrupted process is also recoverable once the journal's recovery record has been checked: the fresh device state determines whether it is still original or at the expected disabled state. No baseline is invented for packages without a recorded journal. Older journals without recovery-check metadata remain compatible.

## Exported recovery

The result shows **Download recovery JSON** and its storage location. The original apply journal is also available in **Recovery points & history**. Technical details offer a restore launcher for that apply journal. Keep its JSON and launcher together as `plan.json` and `restore.py`. The launcher calls the installed engine:

```sh
python restore.py
```

Or use `tcl-tv-debloat restore --journal plan.json`. This creates a fresh preview and asks for confirmation. If the app was removed, reinstall it first. The launcher is not a standalone second recovery engine.

After restoration, **Download restoration JSON** exports the result of that restoration for reference. To restore the original apply operation, select its apply journal from history; a restoration record is not an input to the restore command. Local screenshot guides show simulated connection, review and restore screens. The TV debugging illustration is a guide; menus vary by firmware.

State 0 means Android's default enabled state; restoration uses `pm default-state`, not an unconditional `pm enable`. States 1–4 also map to their exact package-manager operation. If the firmware rejects an operation, the tool reports it and stops.

Reporting settings are also journaled when selected in **Reduce tracking**. They affect the device globally. Restoration writes the recorded original value, or deletes the key if it was originally absent. Owner application versions and current settings must match the reviewed preview; later conflicting values block recovery. See [privacy controls](privacy.md).

Journals record package states and selected reporting settings, not accounts, app data or a firmware backup. They cannot undo a factory reset. The **Use TV without a Google account** guide explains that switching to Basic TV requires a manual factory reset and does not delete the Google account itself. Preserve journals across application upgrades. A failed/uncertain change journal with checked recovery remains useful after restarting the server. The browser's new launch token changes while the saved history remains in `~/.tcl-tv-debloat/`.
