# G2 Bridge

**Live Windows desktop video in stock DJI Goggles 2, over USB.** The original moving test pattern, Windows desktop, and Uncrashed video have been confirmed in both lenses on firmware **01.11.00.00**.

The simulator and controller run normally on the PC. The bridge captures the display, encodes H.264, and sends it through the goggles' Virtual Flight mode. No firmware modification, phone relay, or simulator plugin is needed for the tested setup.

## What made it work

DJI's own Windows Virtual Flight application does not support goggles. We traced the mobile application's native video path with REA, JADX, and Ghidra: encoder configuration, frame fragmentation, checksums, and USB wrapping. Bounded ARM emulation independently checked the packet builders against the original compiled routines.

The crucial discovery was the PC transport. The mobile application's V2 video envelope produced a black screen on the PC interface. Adapting its 32-byte video metadata to **raw DUML V1**, with **978-byte video fragments**, displayed our moving test pattern. That became a live desktop bridge.

The first implementation then exposed a second problem: video could arrive while software queues added delay. Combining packets into the verified 2 KB USB transfers reduced host queue and write times. Windows Graphics Capture with GPU scaling improved the observed responsiveness further. These are measured host improvements and user observations; end-to-end lens latency and actual panel scanout rate have not been measured.

See [the protocol notes](docs/PROTOCOL.md) for the working format and the boundary between recovered facts and tested adaptations.

## Current status

Direct monitor-versus-goggles testing shows extra control delay and less smooth motion in the goggles. Reducing that delay is the current priority.

- Tested: DJI Goggles 2, firmware 01.11.00.00; USB-A on the PC to USB-C on the goggles; Windows 11 x64; NVIDIA RTX 5060 Laptop GPU.
- Working: desktop capture, aspect-preserving 1080p output, simulator handshake, batched USB video, clean shutdown, and a CLI with selectable frame rate and bitrate.
- The current preset targets **1080p100 at 20 Mbps**. The goggles accept the stream and it has been observed as smooth and responsive. A target of 100 fps does not establish 100 distinct displayed frames: the source app, capture, and receiver all matter.
- Recovery from USB/heartbeat loss is implemented and covered by simulated disconnect tests; resumption after a physical reconnect has also been observed. Uncrashed flight was confirmed responsive enough for practice; extended stability testing remains open.
- A USB fault was observed to renegotiate the link down to 12 Mbps. Reconnecting the same cable restored 480 Mbps and the waiting CLI resumed; the underlying port/cable/device cause is not yet isolated. The CLI now diagnoses this slow-link profile explicitly.
- Known issue: a slight periodic compression pulse was linked to keyframes by changing its period from one to three seconds. Further image-quality tuning remains open.

DJI specifies 1920x1080 panels and up to 100 Hz for [Goggles 2](https://www.dji.com/support/product/goggles-2). This is a different product from DJI FPV Goggles V2. Other goggles, firmware versions, GPUs, and operating systems are unverified.

## Run on Windows

Use 64-bit Python 3.10 or newer, PyUSB 1.3.1, an NVIDIA NVENC-capable GPU, and an FFmpeg build containing `gfxcapture` and `h264_nvenc`. The current GPU capture preset was tested with Gyan's `2026-11-05-git-0893feba65` build and NVIDIA driver 610.74. [FFmpeg's download page](https://ffmpeg.org/download.html) links Windows builds.

The DJI bulk driver and its matching x64 `libusb0_device.dll` must already be installed/available. Obtain them from [DJI Assistant 2 (Consumer Drones Series)](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series). This repository does not redistribute DJI binaries or install drivers. The backend accepts only the verified DJI 5.0.0.7 DLL hash documented in [the protocol notes](docs/PROTOCOL.md).

```powershell
python -m pip install -r requirements.txt
python scripts/stream_desktop.py --dll "PATH/TO/libusb0_device.dll" --ffmpeg "PATH/TO/ffmpeg.exe"
```

Power the goggles from their battery, connect the USB data cable, and open **More > DJI Virtual Flight**. Keep one bridge process running. Launch any simulator or desktop application normally. A controller is needed only if the application itself needs one.

**Ctrl+C stops capture and releases USB.** Logs go to ignored `work/logs/`. They can contain device information and local paths; review them before sharing.

Examples:

```powershell
# Output rate and bitrate
python scripts/stream_desktop.py --dll "PATH/TO/libusb0_device.dll" --ffmpeg "PATH/TO/ffmpeg.exe" --fps 60 --bitrate-mbps 16

# Another monitor, without the mouse pointer
python scripts/stream_desktop.py --dll "PATH/TO/libusb0_device.dll" --ffmpeg "PATH/TO/ffmpeg.exe" --display 1 --hide-cursor
```

Set `DJI_USB_DLL` and `GOGGLES_FFMPEG` environment variables to avoid repeating the paths. `--capture ddagrab --fps 60` selects the earlier capture path if using an FFmpeg build without `gfxcapture`. Run `--help` for bounded runs, logging, and reconnect controls. Lower rates other than the documented presets and the 24 Mbps setting have less live coverage; selectable settings are not a compatibility guarantee.

## Verify the implementation

```powershell
python -m unittest discover -s tests -v
```

The offline suite covers original native serializer/fragment fixtures, checksums, packet boundaries, counter rollover, recorded handshakes, model gating, batched video reassembly, capture failure cleanup, and simulated reconnects. It does not replace a visual hardware test.

This is an independent experimental project, not a DJI product. Source/release packaging and broader compatibility are still being prepared. Downloads, decompiled binaries, captures, and local agent notes stay outside the current tracked tree.
