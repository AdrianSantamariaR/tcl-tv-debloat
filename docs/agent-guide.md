# Let your coding agent handle the debloat

You can ask a coding agent with terminal access to handle setup, connect through ADB, scan the TV, and prepare a selection for you. It uses the same engine as the browser, so you can open the saved inventory and journals there too.

The agent should explain the proposed package changes before applying them. Your part is to approve debugging on the TV, decide which features matter to you, and approve the final selection. You don't need to write ADB commands yourself.

## Copy this prompt

Replace the bracketed lines, then paste the prompt into your agent from this repository. If you don't know the connection port, leave that line blank and let the agent help you find it.

```text
Help me debloat my Google TV using this repository. Handle the setup,
analysis, proposed changes, execution, and recovery instructions.

My TV model: [model, if known]
TV IP and ADB connection port, or connected USB serial: [if known]
Features I want to keep: [for example streaming, HDMI, live TV, casting,
voice control, and accessibility]
Apps or services I don't want: [for example TCL Channels, vendor promotions,
unused bundled apps, and optional diagnostics]
Deep analysis: [standard scan only / use REA if already configured /
help me set up REA]

Read README.md and docs/agent-guide.md first. Install the project in a
virtual environment if needed, check its dependencies, and identify the
correct authorized ADB device. Guide me through anything I must do on the
TV. Don't guess a port, select another connected device, or change packages
before the inventory is ready.

Run a fresh standard scan and keep the full inventory. Explain the device's
firmware, the package categories, missing data, and compatibility limits.
If I requested deep analysis, use this project's REA integration. If it
fails, preserve the diagnostics and continue with the standard inventory.
Keep personal reports, APKs, and journals outside Git commits.

Recommend individual packages that are eligible on this exact firmware.
For each, explain its purpose, the feature I would lose, and the evidence
or uncertainty. Preserve the features I listed. Leave protected, unknown,
and unresolved packages unchanged. Don't invent a removal rule or edit
the catalog to make a blocked package selectable. If my firmware has no
reviewed profile, give me the inventory and explain that package changes
are blocked pending review.

Create selection.json and a saved plan with the tool's preview command.
Show me the effective changes in plain English and ask me to approve that
specific list. Once I approve it, apply that saved plan through the tool,
using --yes for the terminal confirmation. If I already approved the same
explicit selection, don't ask me to approve it again. If fresh checks
invalidate the plan, rescan and explain any changed proposal before proceeding.

Stop on a failed or uncertain change. Keep the apply journal and explain
what actually changed, what remains pending, and how to restore the original
states. Don't retry a failed plan automatically or use direct package-manager
commands to work around the tool's checks.

Finish with a fresh read-only scan, a short before/after report, the paths
to my private inventory and recovery journal, and the exact restore command.
Ask me to check Home, settings, remote control, HDMI, sound, and the smart
features I use. Report those checks as unverified until I confirm them.
Don't claim all telemetry is gone based on disabled apps or static code.
```

## Commands the agent uses

Install from the checkout using the instructions in the README. For connection, use the browser wizard or `adb connect` with the address and connection port supplied by the TV. Confirm the target with `adb devices -l`; it must appear as `device`, not `unauthorized` or `offline`.

These examples use the default private store. Run exports in a private working directory outside the checkout. Replace the serial with the chosen authorized device. Use the same `--data-dir` throughout if you choose a custom store.

```sh
tcl-tv-debloat doctor
tcl-tv-debloat scan --serial YOUR_ADB_SERIAL --out inventory.json
```

`scan` is read-only. A partial result is still useful, but missing metadata must not be presented as a complete scan. To add optional REA evidence to that saved inventory:

```sh
tcl-tv-debloat analyze --inventory inventory.json --out inventory-deep.json
```

Use `inventory-deep.json` for the subsequent preview if that command returned a usable inventory. REA configuration checks don't establish that its engine can run; inspect the returned coverage and diagnostics. See [deep analysis](deep-analysis.md) for the prerequisites.

Create `selection.json` containing only approved candidates. Its format is a JSON object, for example `{"com.tcl.channelplus": "disable"}`. An example package name is not a recommendation for every TV.

```sh
tcl-tv-debloat preview --inventory inventory.json --selection selection.json --out plan.json
```

Read the saved plan and explain it to the owner. Packages already at the requested state don't produce a change entry. Only after approval:

```sh
tcl-tv-debloat apply --plan plan.json --yes --out journal.json
```

Read both the exit status and every journal entry. A failed command can have changed the TV before its response was lost. The journal is the recovery record; never replace it with a guessed baseline. Passing the same started plan again returns its journal rather than retrying the changes.

After a successful apply, capture the resulting inventory:

```sh
tcl-tv-debloat scan --serial YOUR_ADB_SERIAL --out inventory-after.json
```

Report the difference from the original scan and retain both files. That confirms package states, not playback, remote operation, or the absence of network reporting.

## Undoing changes

When the owner asks to undo the recorded selection, use its source apply journal:

```sh
tcl-tv-debloat restore --journal journal.json
```

The command scans again, prints a restoration preview, and asks for confirmation. Use `--yes` when the owner has explicitly authorized that restoration and the agent is handling the terminal interaction. Firmware, version, identity, and state checks still apply.

Restoration returns each package to its saved state, including Android's default state 0. It doesn't enable everything. A conflict with a later change needs review, not a forced overwrite. See [recovery](recovery.md) for interrupted operations and exported launchers.
