# Reduce tracking

Choose **Reduce TCL reporting** for a reporting-only review. The optional shortcut under **Advanced**, **Reduce TCL tracking now**, reads a fresh inventory and applies the supported TCL BI and diagnostic flags that need changing, then verifies their values. It creates and saves the recovery plan automatically and changes no packages. Individually selected controls remain available alongside package choices; those selections use the existing preview and apply flow. It does not claim to remove all tracking, logs, cookies or queued reports.

Automatic changes are available only for the reviewed TCL Android 12 firmware and exact versions of the relevant TCL applications. Other TVs can be scanned, but these switches remain unavailable until their behavior is reviewed. Core TTVS remains enabled because it also provides device services, updates and casting.

| Control | Device-wide setting | Reviewed behavior |
| --- | --- | --- |
| TCL BI reporting | Global `gdpr_user_action` → `0` | Sets the supported TCL BI consent flag to off. An absent key is not treated as off. |
| TCL diagnostics | Global `tcl_diagnostic_status` → `0` | Sets the supported TCL diagnostic consent flag to off. |

Changing these flags is not proof that every service stops sending data. Other reporting paths, Firebase, cached data and firmware variations are outside that conclusion.

A value of `0` is shown as already off; an absent key is shown as not set, rather than off. Unexpected values and read failures block automatic changes.

The scan retains only these two settings, not a dump of all device settings. Execution verifies the hardware, firmware, active user, owner application versions and current settings before any change. It rechecks each setting immediately before writing and verifies the result. Failed or interrupted commands retain a recovery journal.

Restoration records the original value exactly. If a key originally did not exist, restoration deletes it. It does not invent an original value of `1`. A later value outside the original and applied values blocks restoration. This cannot detect another writer setting the same value after application. Reporting settings are device-wide, even though the connection must have active user 0. Package changes still affect user 0.

## Terminal selection

Select only the controls you want. `--selection` remains available for package choices and can be omitted for a privacy-only preview:

```sh
tcl-tv-debloat preview --inventory inventory.json --privacy tcl_bi_reporting tcl_diagnostics --out plan.json
tcl-tv-debloat apply --plan plan.json --out journal.json
tcl-tv-debloat restore --journal journal.json
```

Inspect the preview before confirming. Old package-only inventories and journals remain usable for package changes; rescan to include reporting settings. An explicitly restricted package restoration through the API restores only those packages and does not change reporting settings.

## Independent controls on the TV

The browser links to manual controls that are not automated:

- Google's [usage and diagnostics](https://support.google.com/android/answer/6078260?hl=es) setting applies to Google's diagnostic reporting and does not govern other apps.
- Review or delete the [Google TV advertising ID](https://support.google.com/googletv/answer/13392198?hl=es). Resetting an ID and deleting it are different operations.
- Review account activity and ad preferences separately. Apps-only mode changes the home experience and does not establish that telemetry stops.
- Where available, review HbbTV, cookies and third-party cookies in the TV's privacy menus. Availability varies by country and configuration. This app does not change HbbTV cookie settings.
- Existing package choices for Samba, TCL Channels, LogKit and Google Feedback remain separate. Disabling an application preserves its data and does not erase cookies, past reports or cloud records.

TCL describes connected TV data and reporting services in its [TV data information](https://www.tcl.com/eu/en/legal/data-act/user-information-on-tv). That document covers multiple configurations and is not evidence that this particular TV sent a specific report.

## Network verification

A passive capture on a computer sharing the LAN may see TV broadcasts and packets addressed to that computer while missing the TV's Internet connections. A capture with that visibility cannot establish that telemetry stopped. A fuller comparison requires an observation point on the TV's route to the Internet, such as the router's capture facility or a mirrored switch port. Encrypted connections can reveal destinations without revealing log contents.

Do not distribute captures or personal recovery journals with contributions. They can contain local identifiers and traffic data.
