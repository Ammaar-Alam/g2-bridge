# Optional native Windows capture

The default desktop app, stock FFmpeg build, Windows Graphics Capture settings,
CLI, macOS paths and USB packet protocol are retained. This optional backend
targets Desktop Duplication on NVIDIA machines. It is not a replacement for the
upstream WGC path, and does not create or manage virtual displays.

## Opt in

For a source checkout, build/restore and verify the inputs described below, then
set `GOGGLES_NATIVE_FFMPEG` to the absolute path of that modified `ffmpeg.exe`.
Start the app and select **Desktop Duplication** under Advanced. WGC continues
to use `GOGGLES_FFMPEG`/the usual stock build. A missing configured native build
is an error; it does not silently fall back to another binary or encoder.

The default keyframe interval, profile, AQ, preset, low-latency and USB write-size
preferences remain effective. For a separate decoder-recovery experiment,
`GOGGLES_NATIVE_STARTUP_ONLY=1` replaces periodic IDRs with IDRs at 0, 1 and 2
seconds, then a long GOP. This is not a new SDK value and does not change the
default. This experiment overlaps upstream PR #14 and needs firmware-specific
evaluation; it cannot recover an undetected decoder fault through periodic IDRs.

## What changes in the optional path

- A separate worker owns preflight, capture and USB sending. WebView callbacks
  and UI Python work do not share its GIL.
- Display selection resolves the selected GDI name to a current DXGI adapter and
  output. Missing/ambiguous identities fail instead of capturing another screen.
- The modified FFmpeg uses a direct DDA graph, a single raw-frame mailbox,
  source-aware capture deadlines and asynchronous NVENC output. Only stale,
  unencoded images can be replaced; encoded reference pictures remain ordered.
- On NVIDIA outputs, SDR RGB conversion and aspect-fit scaling stay on the GPU.
  Non-NVIDIA outputs require an explicit readback/upload to NVENC. This does not
  prove that a game's rendering itself uses the same GPU as capture.
- Bounded background logging and IPC avoid disk/UI backpressure in the sender.
  Diagnostic history can be coalesced/lost when consumers stall. No additional
  high-frequency video telemetry is enabled.
- The native worker requests High GPU scheduling rather than Realtime. The CLI
  retains Realtime. These choices were workload-dependent in prior experiments;
  neither is a universal guarantee of better game frame times.

The source guard (3 ms), bounded fresh-image acquisition (2 ms) and delivery
offset (8 ms from the same scheduled capture deadline) are not optical latency
measurements. Late packets are sent immediately. Windows scheduling and a closed
receiver cannot support a zero-jitter, zero-drop or fixed end-to-end delay claim.
The SDK already provides ULL NVENC, no B-frames, CBR/VBV limits, low-latency frame
delivery and frame-size guards. This patch retains those existing mechanisms.

## Build inputs and distribution

The normal `python packaging/build_windows.py` command remains a stock build,
without native input requirements or changes to the release workflow.

For a native-enabled build:

1. Follow [the pinned native build recipe](../packaging/windows/ffmpeg/README.md).
   It includes the exact patch, toolchain/source identities and native tests.
2. Place the validated binaries and matching upstream source archive at the
   `vendor/ffmpeg` paths in the manifest. `python packaging/bootstrap_native.py
   verify` must pass. A new native build requires independent validation before
   changing the manifest's accepted executable hashes.
3. Alternatively, restore a separately supplied verified input bundle with
   `python packaging/bootstrap_native.py install --bundle path/to/native.zip`.
   No public binary URL is assumed by this repository. Inputs remain untracked.
4. Run `python packaging/build_windows.py --native`. It includes the isolated
   worker and a separate `ffmpeg-native` directory. The stock build remains
   present for WGC. The native directory contains licenses, complete upstream
   source, patch and build recipe, not only a link to source code.

An installer containing the optional native directory selects it when DDA is
chosen. A normal stock build does not add that directory.
The installer always overwrites `native-backend.json` with the selected build
mode. Installing stock over a native-enabled build disables the old native
payload even if its files remain on disk; file presence alone cannot enable it.
Native input
bundles can be produced with `python packaging/bootstrap_native.py pack --output
path/to/new-native.zip`; the helper refuses an existing destination or mismatched
manifest/source/binary contents.

## Validation boundaries

Run `python -m unittest discover -s tests -v`. The native recipe separately runs
clock, phase, bounded-wait, delivery-deadline and raw-mailbox tests. Offline tests
cover stock/native routing, advanced-option parity, failure/cancellation, bounded
logging, DXGI identity, best-effort scheduling and bundle validation. The Windows
GPU-priority smoke test uses Python's base executable so its process handle is
the graphics caller, rather than a venv forwarding launcher.

Prior integrated-fork hardware checks are background evidence, not controlled A/B
measurements against this focused branch. Record source, matched motion workload,
GPU/driver, firmware, resolution, fps, bitrate, preset and duration for new tests.
Sender/USB counters must not be presented as monitor-to-lens latency.
