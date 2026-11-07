# G2 Bridge

Stream your Windows or Mac desktop to DJI Goggles 2 or DJI Goggles Integra over USB. The goggles use Virtual Flight mode with stock firmware. The simulator and controller run on the computer.

The bridge detects the model when it connects:

| Goggles | Identity | Tested firmware |
| --- | --- | --- |
| DJI Goggles 2 | `E3T ZV900` | 01.11.00.00 |
| DJI Goggles Integra | `E3T ZV901` | 01.09.00.00 |

Measured latency on Windows is about 13-15 ms behind a 240 Hz laptop monitor at 1080p100 (RTX 5060 Laptop GPU, filmed at 240 fps with the GPU idle and with it saturated). For the method and both results, see [Measure video delay](docs/LATENCY.md) and the [experiments](docs/research/EXPERIMENTS.md#monitor-to-lens-delay).

On a Mac, screen capture delivers about 80 new frames per second, so motion is less smooth than on Windows. See the [macOS results](docs/research/EXPERIMENTS.md#macos).

## Requirements

### Windows

- 64-bit Windows and Python 3.10 or later.
- An NVIDIA GPU with NVENC support.
- FFmpeg with `gfxcapture` and `h264_nvenc`. To install it, run `winget install Gyan.FFmpeg`.
- [DJI Assistant 2 (Consumer Drones Series)](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series), which installs the DJI USB driver 5.0.0.7. See [USB and driver requirements](docs/PROTOCOL.md#usb-and-session).

Tests used FFmpeg build `2026-11-05-git-0893feba65` and NVIDIA driver 610.74.

### macOS

- macOS and Python 3.10 or later.
- [Homebrew](https://brew.sh). The stream script offers to install FFmpeg and libusb with it.
- A USB-A-to-USB-C cable. Use a USB-C-to-USB-A adapter if the Mac has only USB-C ports. Over a USB-C-to-USB-C cable, the goggles take the USB host role and the Mac can't detect them.

Tests used an M2 Pro MacBook Pro with macOS 27.0 and Homebrew FFmpeg 8.1.1.

## Start streaming

1. Power on the goggles, connect a USB data cable, and open **More > DJI Virtual Flight**. On a Mac, select **Allow** when macOS asks whether the accessory can connect.
2. From the repository root, install the Python dependencies.

   On Windows, run:

   ```powershell
   python -m pip install -r requirements.txt
   ```

   On macOS, run:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. Start the stream.

   On Windows, run:

   ```powershell
   python scripts/stream_desktop.py
   ```

   On macOS, run:

   ```bash
   .venv/bin/python scripts/stream_desktop.py
   ```

   The script finds the DJI driver and FFmpeg automatically. If either is installed somewhere else, pass `--dll` or `--ffmpeg` with the file path. On a Mac, the script offers to install FFmpeg and libusb if either is missing. If FFmpeg can't capture the screen, allow **Screen Recording** for your terminal in **System Settings > Privacy & Security**.

The default output is **1920x1080**, with a **100 fps encoder target** and a **20 Mbps** bitrate. Press **Ctrl+C** to stop. Logs are written to `work/logs/`.

Use these options to adjust the stream:

| Option | Values |
| --- | --- |
| `--fps` | `60`, `100` |
| `--bitrate-mbps` | `8`, `10`, `12`, `16`, `20`, `24` |
| `--display` | Monitor index, starting at `0` |
| `--hide-cursor` | Hide the mouse pointer |
| `--capture` | `gfxcapture` or `ddagrab` (Windows only) |

Run `python scripts/stream_desktop.py --help` for all options.

## Run tests

Run the tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

See the [video-delay measurement guide](docs/LATENCY.md), [PC protocol](docs/PROTOCOL.md), and [reverse-engineering data and tools](docs/research/README.md).

## Contributing

See the [contribution guide](CONTRIBUTING.md) to report bugs, submit changes, or share protocol research.

## License

Copyright (C) 2026 G2 Bridge contributors.

The original code and documentation are licensed under the [GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`). Third-party materials retain their own licenses.
