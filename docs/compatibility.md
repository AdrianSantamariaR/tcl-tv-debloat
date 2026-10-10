# Compatibility and evidence

## Televisions

A working ADB connection allows inventory on many Google TVs. The application does not promise that every TCL exposes network or USB debugging. Android user 0 is the first-release scope; an active user other than 0 blocks package changes.

There are four categories:

| Category | Behavior |
| --- | --- |
| Protected | Core, mixed or shared system functionality; disabling blocked |
| Optional | Exact reviewed firmware/package match; individually selectable |
| Needs review | Function or dependencies insufficiently resolved; disabling blocked |
| Unknown | No applicable reviewed guidance; disabling blocked |

The observed TCL profile is constrained to manufacturer `TCL`, product `G10_4K_GB_NF_32BIT`, fingerprint `TCL/G10_4K_GB_NF_32BIT/G10:12/STT2.230203.001/AS12:user/release-keys` and each recorded package version. The profile is associated with TCL 55P6K; a generic ADB model name does not verify the retail model. Another firmware retains descriptions without inheriting disable eligibility.

This is static observation, not a guarantee of correct TV behavior after every selectable change. Other firmware profiles and functional testing of tuner, HDMI, remote, audio, casting, accessibility, streaming and updates need future contributions.

TTVS includes essential functionality and reporting-related code; it stays protected. Disabling Samba's UI does not prove reporting in other packages stops. Inspect TCL privacy controls manually where available; [TCL's general guide](https://support.tcl.com/en_US/us-googletv-setup-configuration/tcl-google-tv-settings-and-user-manual-guide) is not a universal tracking map.

## Computers

Python 3.11 or later is required. CI is configured for macOS, Windows and Linux; consult the workflow results for the current test status.

## Deep analysis

Optional deep analysis requires REA, a full Java JDK and a compatible JADX provider. See [the setup guide](deep-analysis.md) for prerequisites. Failed analysis leaves standard inventory available.

Static findings describe declarations and selected code. They do not prove that data was transmitted, that all tracking is absent, that signatures are verified, or that every dependency is understood. Split APK coverage is base-only. Inaccessible overlays remain in the ADB inventory with explicit failed deep coverage.
