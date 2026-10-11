# TCL TV Debloat

Review what's installed on your Google TV, turn off the apps you don't use, and keep a record you can undo later.

TCL TV Debloat runs on your computer. After scanning, you can reduce supported TCL tracking with one click, or select suggested optional apps based on the functions you want to keep. Package changes still have a review step. The tool saves original states and setting values for recovery.

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

1. **Connect:** authorize debugging on the TV and scan. Connecting by address starts the scan once that TV is authorized.
2. **Choose:** select **Keep my smart TV**, **Reduce TCL reporting**, **HDMI & live TV**, or the manual **Use TV without an account** guide. Reviewed suggestions are prepared automatically. Customize retained features if needed.
3. **Review:** check the changes and their function impact, then choose **Apply changes**. Nothing is applied just by choosing a goal.
4. **Result:** see verified outcomes, record optional TV checks, or choose **Undo these changes**. Undo reads the TV again and shows a review before restoration.

Individual apps, settings, evidence and optional code inspection are under **Advanced** or **Tools and advanced scanning**. Previous changes are available in **History**. Protected and unresolved packages can't be disabled. The account-free guide explains factory-reset data loss and never performs the reset itself.

The [Reduce tracking controls](docs/privacy.md) can close two reviewed TCL reporting flags without disabling core TTVS. They save and restore the exact original setting, including an originally absent key. Google and HbbTV controls have manual guidance.

The privacy panel explains each control's scope. On matching reviewed versions it also describes independent TCL BI, messaging and component-update paths. A flag at 0 is a recorded setting value, not proof that all network reporting stopped.

The optional **Reduce TCL tracking now** shortcut under **Advanced** performs a fresh scan, selects supported BI/diagnostic flags that need changing, creates a saved plan, applies it and verifies each value, then refreshes the inventory so you can continue with app suggestions. Already-off flags are skipped. It changes no packages and does not stop every reporting path. The smart-TV profile retains streaming, casting and voice by default. The HDMI/live-TV profile stops retaining those optional smart functions. Accessibility keeps your chosen preference in both profiles. Unknown, protected, already-disabled and unclassified optional functions are not suggested. Suggestions update with your preferences until you edit a package manually.

After applying changes, the **Result** screen shows automatic setting/package verification from the saved apply journal. Optional picture, sound and feature checks can be expanded to record playback, HDMI, casting and other observations. You can also open a saved apply journal with **View** to record them later. Manual results start at **Not tested** and stay with that journal within the current browser tab. **Download checks report** saves a private JSON report with the journal reference, device, recorded changes and your observations. Download before closing; the app does not reload these reports or measure network traffic. Keep the source journal separately for restoration.

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
