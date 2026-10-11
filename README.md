# TCL TV Debloat

A local tool to review TCL Google TV apps, disable supported optional packages, and reduce reviewed TCL reporting settings. Automatic recovery points let you restore the original recorded states.

Runs on your computer through a browser or the command line, using ADB to communicate with the TV. No root, firmware flashing, account or hosted backend is required.

**Public beta:** the first reviewed profile comes from a TCL 55P6K running Android 12. Other Google TV and Android TV devices can be inventoried if they support an authorized ADB connection; changing packages or reporting settings requires matching reviewed firmware and application versions.

## What it does

- **Review installed apps:** inspect package versions, enabled states, permissions, purpose and known feature impact.
- **Disable optional apps:** use Android's `disable-user` operation for user 0, preserving installed packages and their data. Protected, unknown and unreviewed packages are blocked.
- **Reduce supported TCL reporting:** change two reviewed BI and diagnostic settings while keeping core TV services enabled. This does not establish that all tracking has stopped.
- **Save and verify recovery points:** check the saved original states before sending changes, verify each result, and retain a journal for undo or recovery after interruption.
- **Inspect APKs with optional REA analysis:** add manifest and selected code evidence to the inventory. Standard scanning works without these extra tools.

Recovery covers recorded app states and selected reporting settings. It is not a backup of accounts, app data or firmware, and cannot undo a factory reset. The project also provides manual guidance for Google privacy settings and using the TV without a Google account; it does not remove the account or reset the TV automatically.

## Getting started

Install **Python 3.11 or later** and [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools). The `adb` command must be available on your PATH.

Clone this repository and open its folder. On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
tcl-tv-debloat
```

On Windows, use PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
tcl-tv-debloat
```

The last command opens the local application in your browser. Installation does not connect to the TV or download optional analysis tools. There are no third-party Python runtime dependencies.

Enable the debugging option your TV supports, connect through ADB, and approve the authorization prompt on the TV. A scan reads the device without changing packages or settings. Select the functions you want to retain, review the proposed changes, then apply them. Saved journals provide restoration to the recorded original states.

See [setup and connection](docs/setup.md) for network connections, pairing and authorization.

## Compatibility and safeguards

A connection is enough to scan, but it is not enough to authorize changes. The tool checks the device identity, firmware, active Android user, selected application versions and current states before applying a plan. Failed recovery saving or validation blocks changes. Conflicting later states block restoration for review.

The initial profile contains 142 packages observed on one TCL 55P6K. It has not been functionally tested through every selectable change. Similar model names do not establish compatibility, and no tool can guarantee that every TV feature will work after every change.

Read [compatibility and evidence](docs/compatibility.md) before making changes, and [apply, undo and recovery](docs/recovery.md) before relying on a recovery file.

## Command line

The CLI shares the browser's scan, preview, apply and recovery engine. Replace `YOUR_ADB_SERIAL` with the authorized device shown by `adb devices -l`:

```sh
tcl-tv-debloat doctor
tcl-tv-debloat scan --serial YOUR_ADB_SERIAL --out inventory.json
```

Review a saved selection with `preview`, apply the saved plan with `apply`, or restore an apply journal:

```sh
tcl-tv-debloat restore --journal journal.json
```

Apply and restore ask for confirmation. See the [agent and CLI guide](docs/agent-guide.md) for the complete command sequence and a prompt you can give your coding agent.

## Local data and privacy

The application listens on `127.0.0.1`. Inventories, plans, recovery journals and optional evidence are stored in `~/.tcl-tv-debloat/`. Use `--data-dir PATH` before a subcommand to select another directory.

Keep the launch URL, exported inventories and recovery files private: they can contain session tokens or device identifiers. Preserve recovery journals across restarts and upgrades.

## Documentation

- [Setup and connection](docs/setup.md)
- [Compatibility and evidence](docs/compatibility.md)
- [Apply, undo and recovery](docs/recovery.md)
- [Privacy controls and their limits](docs/privacy.md)
- [Optional REA deep analysis](docs/deep-analysis.md)
- [Agent and CLI guide](docs/agent-guide.md)
- [Roadmap and contributions](docs/next-steps.md)

## Development and contributions

Run the core tests or launch the app with a simulated TV:

```sh
python3 -m unittest discover -s tests -v
python3 -m tests.serve_fake
```

The simulated device cannot contact a real TV. Other scenarios are `--scenario unknown`, `failed-rea`, `partial` and `slow`.

New firmware profiles need package versions, evidence and a clear record of what was tested. Do not infer compatibility from package names alone. Keep APKs, provider JARs, personal inventories, device identifiers, traffic captures and recovery journals out of commits.

Original project code is [MIT licensed](LICENSE). External tools retain their own licenses. This project is independent of TCL, Google and REA.
