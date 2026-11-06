# Continue on Windows

The owner plans to clone this repository on the Windows PC that runs Uncrashed and believes Ghidra is already installed. The available phone is an iPhone. No Pi is available yet.

## Establish the workspace

Clone and open the repository on the actual Windows execution host:

```powershell
git clone https://github.com/Ammaar-Alam/dji-goggles2-sim-bridge.git
cd dji-goggles2-sim-bridge
git status --short
```

Open this folder in Codex and read `AGENTS.md` and `.agents/README.md`. A chat viewed remotely can still execute on another computer; verify the host before expecting USB access. The repository carries the research, but not the Mac's local binaries or tool configuration.

The user can start the new chat with this request:

> Continue this private DJI Goggles 2 simulator bridge investigation. Read AGENTS.md and .agents/README.md, then follow .agents/WINDOWS.md. Use the included reverse-engineer-anything skill. I want existing Uncrashed on Windows to display in Goggles 2, preferably with software and a USB cable. I have an iPhone; a small Pi is the maximum acceptable hardware fallback. Verify tools and begin with offline app analysis and read-only goggles identification. Do not repeat the general compatibility research or modify firmware.

## Verify the analysis tools

Follow [the REA skill](skills/reverse-engineer-anything/SKILL.md) and [its recovery guide](skills/reverse-engineer-anything/references/connection-and-recovery.md). The bundled skill is instructions, not an installed MCP server or decompiler.

If REA tools already respond, inspect `binary_session` and use the current provider diagnostics. Do not reinstall a working registration. If tools are missing, use the skill's version-pinned read-only diagnosis:

```powershell
npx -y rea-agents@6.7.0 doctor --client codex --json
```

This command can download the pinned package into npm's cache. If registration needs repair, prepare the concrete plan before changing configuration:

```powershell
npx -y rea-agents@6.7.0 setup --client codex --dry-run --json
```

The skill requires review of configuration changes and any bundled-skill replacement before applying setup. Follow the owner's authorization and actual approval policy. Do not alter global Java or Node settings speculatively.

Check these task-specific prerequisites:

| Task | Tool | Verification |
| --- | --- | --- |
| Package inventory | REA archive tools | Exact APK opens and inventory completes |
| Android classes and methods | JADX provider | `inspect_android_package` succeeds on the actual APK |
| Native libraries | Ghidra or another available native provider | The selected library opens and target-specific analysis works |
| Recorded USB/network analysis, if needed | Compatible capture reader | The actual capture format and fields are supported |

The observed REA 6.7.0 integration expects Ghidra 12.1.x and an appropriate full JDK. Verify the current installed provider's requirements and the owner's Ghidra version instead of replacing an installation merely because it differs. The Android integration requires a supplied `jadx-headless-mcp` 0.7.1 JAR and Java 17 or later; Ghidra alone does not satisfy that dependency. Android and native support are separate. Check the exact host/target combination and use a supported local tool directly if REA's integration cannot handle it.

## Inventory the goggles without changing them

Have the owner power the goggles normally and connect a **USB-A-to-USB-C data cable** to the PC. This is the [documented DJI Assistant connection](https://dl.djicdn.com/downloads/DJI_Goggles_2/User_Manual/20230428/DJI_Goggles_2_User_Manual_v1.0_en.pdf), page 44. Keep the aircraft off for the simulator investigation. Preserve the current firmware and mode as the baseline.

Record the following information:

- Printed model and firmware from the goggles' About screen.
- Windows version, CPU architecture, USB port and cable arrangement.
- USB IDs, configuration, interfaces, endpoint descriptors, and attached drivers.
- Whether **More > DJI Virtual Flight** is available, and how identification changes when entering that mode.
- Any required controller state, without assuming a controller model or changing pairing.

A starting PowerShell inventory for the DJI USB vendor ID reported in upstream research is:

```powershell
Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -like 'USB\VID_2CA3*' } |
    Select-Object Status, Class, FriendlyName, InstanceId
```

This command is read-only and not a complete endpoint inspection. No matches do not establish incompatibility; check connection, power, cable, and normal device enumeration first. Instance IDs can contain serials, so keep full output under ignored `work/` and redact summaries before committing.

Do not replace drivers with Zadig, send command sweeps, or change firmware as part of inventory. Any later command must have a source-grounded purpose and bounded effect. Existing PC-side interfaces are an investigation target, not proof of video acceptance.

## Trace the mobile app's send path

Acquire the original APK using [ARTIFACTS.md](ARTIFACTS.md). Preserve the original hash and signing observations before extracting it. Do not run the APK to inspect it.

Use the smallest trace that answers these questions:

1. Which manifest entries, accessory filters, and connection classes select the goggles?
2. Which code opens the USB connection and negotiates a simulator session?
3. Where are video frames encoded, and what are the actual codec, dimensions, frame rate, keyframe, and buffering settings?
4. Which Java or native functions package frames and send bytes?
5. What initialization, acknowledgments, sequence numbers, keepalives, or authentication are required?
6. Is the same receiver reachable through the PC-facing USB personality, or only through the mobile path?

Search terms such as `UsbManager`, `openAccessory`, USB stream writes, `MediaCodec`, JNI registrations, and `logiclink` are candidates, not findings. Select actual class and function names from inventory. Follow incoming references, callers, and native boundaries instead of inferring behavior from strings alone. Do not assume H.264 until code or captured bytes establishes it.

For Android code, start with `inspect_android_package`, then focused class, method, and reference tools. For a native library, use `open_binary` and focused Ghidra analysis. Preserve Evidence IDs, artifact hashes, source offsets or addresses, and limitations. Export required evidence before closing an opened native session with `close_binary`.

Use firmware analysis only if this trace leaves a specific receiver-side question unanswered. A root exploit or custom firmware is not a prerequisite for reading an app's code.

## Use the iPhone as a reference

If the original DJI Virtual Flight app is available on the owner's iPhone, follow DJI's [mobile simulator instructions](https://repair.dji.com/help/content?customId=01700008917&lang=en&paperDocType=ARTICLE&re=US&spaceId=17). Record app/iOS/firmware versions and confirm the actual simulator image appears inside the Goggles 2. A controller or mode requirement may matter; do not invent one or require a purchase before testing the available setup.

This first phone test is a visual baseline. Connecting the phone to a PC as well does not automatically expose its separate goggles USB traffic. Do not promise that a passive hub or PC-side capture can observe that connection. If the app is unavailable or fails, record the result and continue useful APK analysis and PC inventory.

## Prove the transport before building an application

After the send path is understood, implement the minimum source-grounded transmitter. First send a moving pattern or frame counter. Verify it in both lenses and confirm normal operation returns after disconnecting.

Measure end-to-end delay using a method that observes the source and the lens display, such as high-frame-rate filming of a shared changing counter. Record the frame rate, measurement resolution, clock assumptions, sample count, typical delay, and variation. Do not equate encoder logs with display latency.

If the direct PC interface cannot reach the decoder with the recovered protocol, state the exact tested boundary. Evaluate a Pi with an appropriate USB peripheral controller as the fallback. The accepted conceptual path is Windows capture and encoding, then a wired local network to the Pi, then USB to the goggles. Power and USB wiring must be validated before connecting hardware. No Pi purchase has been made or requested.

Only after the moving-image test, capture Uncrashed with an existing capture/encoding component. Keep the controller connected to the PC. Test sustained playback, disconnect/reconnect, frame loss, and visible buffering. Agree on acceptable FPV latency from measurements rather than claiming a numeric target from unrelated products.
