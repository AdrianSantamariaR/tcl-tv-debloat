# Setup and connection

Install Python 3.11+ and [official Android Platform Tools](https://developer.android.com/tools/releases/platform-tools). Make `adb` available on PATH. Verify with `adb version`.

Follow the [README installation commands](../README.md#getting-started) to create a virtual environment, install the checkout, and launch `tcl-tv-debloat`. You can also run `.venv\Scripts\tcl-tv-debloat.exe` directly on Windows without activating the environment.

If you prefer your coding agent to handle the terminal work, [give it this prompt](agent-guide.md#copy-this-prompt). You still need to approve debugging on the TV and choose what to change.

## Authorize the TV

Keep the TV awake and put it and the computer on the same local network, using Wi-Fi or Ethernet.

1. Open **Settings → System → About**. Older Android TVs may use **Device Preferences → About**.
2. Select **Android TV OS build** and press OK seven times, until the developer message appears.
3. Return to **System → Developer options** and turn on **USB debugging**, or the ADB debugging option your firmware exposes.
4. Find the IP address in **System → About → Status** or network settings. Enter it in the app with the TV's ADB connection port.
5. Connect, then accept **Allow USB debugging?** on the TV. Refresh devices and select the authorized device.

TCL's [official settings walkthrough](https://support.tcl.com/us-googletv-common-questions/tcl-google-tv-walkthrough-settings) identifies the System, About and Status menus, with variation by model. Android's [official TV device instructions](https://developer.android.com/training/tv/get-started/create#run-on-a-real-device) describe enabling developer options and debugging. These guides are navigation references; they do not establish network ADB support on every TCL firmware.

If network ADB is available, enter a numeric IP and its connection port, such as `192.168.1.100:5555`. The application supports bracketed IPv6 as well. A TV's Ethernet or Wi-Fi connection alone does not establish that ADB is available. Do not assume every model exposes port 5555.

If the TV offers pairing, enter its pairing address/port and six-digit code, then connect to its separate connection port. Codes are sent through stdin and are not saved. USB is available only where the TV supports an ADB device connection; a normal USB host port may not. Refresh devices and select an authorized device reported by ADB.

If ADB reports unauthorized, turn on the TV and accept its prompt. If no prompt appears, check the selected debugging setting. An offline device cannot be scanned. No packages change during connection or a standard scan.

## Choose analysis

The wizard shows ADB for standard scanning, disabling and restoration. Expand **Optional tools for Deep** to see REA, Node.js, Java and JADX. Python is already running the app. Missing Deep dependencies do not block standard use. The app does not install dependencies for you.

**Needs configuration** means the app has no selected path; it does not prove the tool is absent from the computer. **Path not found** means a selected file does not exist. **Check failed** means a probe failed or the selected tool is incompatible. An agent's REA MCP configuration is separate from the application's environment. Set the paths described in [deep analysis](deep-analysis.md) in the launching terminal, then restart the app. **Recheck prerequisites** can check newly installed files but cannot import environment changes from another terminal.

Private sessions, journals and evidence are stored at `~/.tcl-tv-debloat/`. The service binds only to `127.0.0.1`, uses a different port when available, and opens a launch URL carrying a session token in its fragment. Keep that launch URL private. A new launch generates a new token; saved history remains on disk.

## TCL sources

TCL's [Spanish P6K product page](https://www.tcl.com/es/es/tvs/p6k) describes the Google TV model family. The [55P6K regional support page](https://www.tcl.com/es/es/support-tv/model-tv/55p6k) is a starting point for model-specific help; it did not expose a manual download in our check.

TCL's [settings guide](https://support.tcl.com/en_US/us-googletv-setup-configuration/tcl-google-tv-settings-and-user-manual-guide) is based on X11L and explicitly notes variation by model, region and software. Its menus are guidance, not a P6K package compatibility list. Android's [ADB documentation](https://developer.android.com/tools/adb) describes device authorization and debugging connections.
