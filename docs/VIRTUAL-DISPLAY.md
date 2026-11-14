# Virtual Display on Windows

Choose **Virtual Display** under Source to give a simulator an independent
desktop while keeping the physical screen available. Choose 1280 × 720 or
1920 × 1080 and 60, 75, 90, or 100 fps. The virtual display's requested refresh
rate matches the selected stream frame rate.

The first use offers installation of the pinned, signed Virtual Display Driver
25.7.23 from [VirtualDrivers](https://github.com/VirtualDrivers/Virtual-Display-Driver/releases/tag/25.7.23).
Windows shows its normal administrator authorization prompt. The app does not
change certificate trust, driver signature enforcement, or test-signing settings.
The driver is MIT-licensed; its license and original signed files are included.

After connecting the goggles and opening DJI Virtual Flight, start streaming.
Move the simulator window onto the new desktop using Windows display controls
or Win+Shift+Left/Right. Stop the stream, disconnect the goggles, or close the
app to release the virtual screen. Reconnect and start again to create a new
session; this feature does not add automatic USB start.

## Capture and settings

This feature is independent of any native FFmpeg performance work. It uses the
existing stock FFmpeg Windows Graphics Capture graph and NVIDIA NVENC encoder.
The leased screen is bound using its HMONITOR, not a display index that can
change when Windows extends the desktop. The selected dimensions and disabled
capture border are passed to both the preflight and stream command.

The physical-display path, CLI, protocol, macOS capture, and existing encoding
defaults are unchanged. Virtual Display fixes the capture method to WGC, so that
control is hidden for that source. Other advanced settings remain applicable
and visible: profile, keyframe interval, AQ, preset, low-latency delivery, and
USB write size. Physical preferences remain saved when switching sources.

The SDK still sends and limits frames as before. The driver refresh setting is
not a guarantee of the game's rendering cadence, decoded display cadence, or
optical latency. This branch makes no new performance or zero-jitter claim.

## Ownership and cleanup

The app uses its own registry ownership marker and installation folder. It
refuses to overwrite an existing third-party VDD configuration, including one
installed by a separate fork. Remove such a driver using its original app
before setting up this one. The runtime never uses the driver's reload pipe.

A session-local Windows mutex excludes concurrent streaming and driver
maintenance across app instances. Layout activation verifies existing active
screens and attempts rollback if they change. Cleanup checks the leased device
identity and refuses to detach a replacement, a primary screen, or the sole
active screen. A failed cleanup is reported even when the stream also failed
or was cancelled. The streaming thread completes cleanup on normal app exit.

The driver remains installed between streams; only its screen is detached.
Use **Remove driver** under the Virtual Display source before uninstalling the
app when the driver is no longer wanted. The signed package remains in the
Windows driver store because other software may use it.

Forced process termination, power loss, and operating-system failure cannot
run Python cleanup. A later session checks ownership and reconfigures an
existing owned display. The feature requires an active physical primary screen;
it does not implement a headless or primary virtual display.

## Build and verification

The existing Windows build command now also builds a dedicated display setup
helper and fetches the pinned driver archive. SHA-256 checks cover the archive
and each allowed INF/DLL/catalog file before extraction. Windows validates the
catalog's signature again before installation. The helper accepts only fixed
install/remove verbs and has a separate `_display_setup_internal` directory;
its Python archive cannot replace the GUI's runtime archive.

```powershell
python -m unittest discover -s tests -v
node --test tests/test_virtual_ui.mjs
python packaging/build_windows.py
```

Focused `test_virtual_*.py` tests cover mode requests, exact topology rollback,
ownership conflicts, named-mutex contention, cleanup failures, cancellation,
source preference preservation, shared encoder policy, helper verbs, and
package integrity. The UI tests use a local Edge/Chromium and the offline demo
backend; set `GOGGLES_UI_BROWSER` if it is not in the default Windows location.
They do not install drivers, mutate host display layouts, or send USB video.

Real driver installation and game/headset acceptance still depend on Windows,
the installed display driver, GPU topology, and headset firmware. Automated
tests and the requested 100/1 display timing cannot establish end-to-end frame
timing or replace an optical measurement.
