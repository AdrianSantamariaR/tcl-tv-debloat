# Optional REA deep analysis

Deep analysis uses reverse engineering to inspect readable Android app packages locally. It can add manifest permissions, services/components and selected reviewed methods. It takes longer than the ADB inventory. Static code cannot establish actual data transmission.

You can scan, preview, apply and restore without REA. No AI API key or coding agent is required. Ghidra is not needed for this APK Java workflow.

## Tools you supply

| Dependency | Purpose |
| --- | --- |
| ADB | Reads APK paths and copies readable packages from the TV |
| Node.js + installed REA | Runs the REA dispatcher |
| Full JDK 17+ with `jdk.compiler` | Loads the engine and compiles its metadata bridge |
| JADX headless provider JAR | Decodes Android packages and selected methods |

Follow [REA's official Android analysis instructions](https://github.com/morluto/rea/blob/main/docs/android-analysis.md). The locally selected provider was [jadx-headless-mcp 0.7.1](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1), using `jadx-headless-mcp-0.7.1-all.jar`. Review dependency licenses separately.

A reproducible optional REA installation is `npm install --prefix /your/tools/rea rea-agents@6.3.0`. The application does not run npm or download anything. Set the dispatcher path explicitly if it is not discoverable through a real `rea` executable:

```sh
export REA_CLI_PATH=/your/tools/rea/node_modules/rea-agents/scripts/rea.mjs
export JAVA_HOME=/absolute/path/to/existing/jdk
export REA_JADX_MCP_JAR=/absolute/path/jadx-headless-mcp-0.7.1-all.jar
tcl-tv-debloat doctor
tcl-tv-debloat
```

In PowerShell:

```powershell
$env:REA_CLI_PATH = 'C:\tools\rea\node_modules\rea-agents\scripts\rea.mjs'
$env:JAVA_HOME = 'C:\tools\jdk-21'
$env:REA_JADX_MCP_JAR = 'C:\tools\jadx-headless-mcp-0.7.1-all.jar'
tcl-tv-debloat doctor
```

The application reads the installed REA package's Node engine requirement. REA 6.3.0 declares `^22.19.0 || ^24.11.0 || >=26.0.0`; unsupported range syntax reports an unavailable check. Windows npm `.cmd` shims are not run through a shell. REA native provider support depends on its released package and host architecture.

## Configured versus verified

The wizard checks metadata, Java's compiler module and the selected JAR. **Configured** means prerequisites appear available. **Execution verified** appears only after a valid APK inspection whose artifact and engine hashes and manifest identity match the request. Configuration can succeed while the provider fails. Our live local execution failed; see [compatibility evidence](compatibility.md).

Deep scanning saves the standard inventory before inspecting APKs. Each package has complete, failed or limited coverage and diagnostics. Cancellation stops the owned REA invocation; forced interruption may leave REA temporary files. Private evidence/cache stays in your data directory and binds APK hash, REA version, provider JAR hash and request.

Only exact reviewed artifact selectors invoke class/method decompilation. Overloads are resolved against the current class inventory. Unknown code never creates disable eligibility. Split sets are not fully analyzed; inaccessible overlays are recorded without claiming decompilation. Findings do not execute the APK or change its permissions.
