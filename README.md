# TCL TV Debloat

Review what's installed on your Google TV, turn off the apps you don't use, and keep a record you can undo later.

TCL TV Debloat runs on your computer. It opens a local browser with a package inventory, plain-English descriptions, permissions, and a preview of your changes. Nothing is selected for removal. You choose what to disable, and the tool saves each package's original state before changing it.

Prefer to have your coding agent handle the work? [Copy the agent prompt](docs/agent-guide.md#copy-this-prompt). It covers setup, scanning, recommendations, your approval, and recovery.

## Getting started

You'll need **Python 3.11 or later** and [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools), which includes ADB. Check that both are available:

```sh
python3 --version
adb version
```

From this repository, on macOS or Linux:

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

The last command opens the browser. Installation itself doesn't connect to your TV or download the optional analysis tools. The application has no third-party Python runtime dependencies, account requirement, or hosted backend.

See [setup and connection](docs/setup.md) if ADB isn't available or your TV needs authorization.

## What you do in the browser

1. Connect to your TV and approve this computer on the TV's debugging prompt.
2. Run a standard scan. Optional deep analysis is explained in the wizard.
3. Search the inventory and read the details for apps you don't want.
4. Select individual packages and optional **Reduce tracking** controls, review the preview, and apply it.
5. To undo, choose the saved apply journal and preview its restoration.

Keep the smart features you use: streaming, casting, voice control, accessibility, or all of them. The feature checkboxes help explain consequences; they don't select packages for you. Protected and unresolved packages can't be disabled.

The [Reduce tracking controls](docs/privacy.md) can close two reviewed TCL reporting flags without disabling core TTVS. They save and restore the exact original setting, including an originally absent key. Google and HbbTV controls have manual guidance.

Package changes use Android's `disable-user` operation for user 0. They don't uninstall apps, erase their data, change permissions, root the TV, or flash firmware. [How apply and recovery work](docs/recovery.md) explains the saved states and what happens if a command is interrupted.

## Which TVs can use it?

A Google TV or Android TV with an authorized ADB connection may be scanned. Whether you can disable a package is a separate question: the tool requires a reviewed profile matching the manufacturer, product, firmware, and package version. A similar model name isn't enough.

The first profile comes from one TCL 55P6K running Android 12. Its inventory contains **142 packages**: 104 protected, 28 optional, and 10 needing review in the validation scan. This is an observed profile; it hasn't been tested through every possible removal and TV feature. Other firmware can be inventoried without inheriting these disable choices.

See [compatibility and evidence](docs/compatibility.md) for supported environments and the limits of the observed profile. The [roadmap](docs/next-steps.md) describes current capabilities and planned improvements.

Disabling unwanted apps doesn't prove all data collection has stopped. Some essential services also contain reporting code. The tool keeps those services protected and shows what the evidence can establish.

## Optional deep analysis

A standard scan uses ADB to read package names, versions, enabled states, and permissions. Deep analysis copies readable APKs to your computer and uses REA to inspect their manifests and selected code.

You need Node.js, REA, a full Java JDK, and a JADX provider JAR for that step. You don't need Ghidra, an AI API key, or a coding agent. Missing or failing REA tools leave standard scanning available. [The deep-analysis guide](docs/deep-analysis.md) explains installation and what static analysis can tell you.

## Terminal use

The command line uses the same scan, preview, and recovery engine as the browser. Replace `YOUR_ADB_SERIAL` with the authorized device shown by `adb devices -l`.

```sh
tcl-tv-debloat doctor
tcl-tv-debloat scan --serial YOUR_ADB_SERIAL --out inventory.json
```

After reviewing that inventory, write a `selection.json` mapping only your chosen, eligible packages to `disable`. For example:

```json
{"com.tcl.channelplus": "disable"}
```

Then preview and apply:

```sh
tcl-tv-debloat preview --inventory inventory.json --selection selection.json --out plan.json
tcl-tv-debloat apply --plan plan.json --out journal.json
```

Apply prints the saved preview and asks you to type `yes`. To undo that journal:

```sh
tcl-tv-debloat restore --journal journal.json
```

For an agent or script, `--yes` skips the terminal question after the owner has approved the selection. It doesn't bypass device, firmware, version, or state checks. [The agent guide](docs/agent-guide.md) includes the full handoff prompt and command sequence.

Saved inventories, journals, and evidence live in `~/.tcl-tv-debloat/`. Put `--data-dir PATH` before a subcommand to use another directory. Keep recovery files private and available after you close the browser.

## Development and contributions

Run the tests or open a browser with a simulated TV:

```sh
python3 -m unittest discover -s tests -v
python3 -m tests.serve_fake
```

The simulated device can't contact a real TV. Other acceptance scenarios are `--scenario unknown`, `failed-rea`, `partial`, and `slow`.

New firmware profiles need package versions, evidence, and an honest description of what was tested. Don't contribute a blanket removal list based on package names alone. Keep APKs, provider JARs, personal inventories, device identifiers, and journals out of commits.

Original project code is MIT licensed. External tools retain their own licenses. This project is independent of TCL, Google, and REA.
