# G2 Bridge

Stream your Windows or Mac desktop to DJI Goggles 2 or DJI Goggles Integra over USB. The goggles use Virtual Flight mode with stock firmware. The simulator and controller run on the computer.

The bridge detects the model when it connects:

| Goggles | Identity | Tested firmware |
| --- | --- | --- |
| DJI Goggles 2 | `E3T ZV900` | 01.11.00.00, 01.14.00.00 |
| DJI Goggles Integra | `E3T ZV901` | 01.09.00.00 |

We measured **about 12 ms median monitor-to-lens delay** at 1080p100. See [how we measured it](docs/LATENCY.md).

## Requirements

On Windows, you need the following hardware and software:

- 64-bit Windows and Python 3.10 or later.
- An NVIDIA GPU with NVENC support and driver 570 or later.
- [DJI Assistant 2 (Consumer Drones Series)](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series), which installs the DJI USB driver 5.0.0.7. See [USB and driver requirements](docs/PROTOCOL.md#usb-and-session).

The Windows encoder is included. See its [source and build instructions](vendor/ffmpeg/README.md).
Tests used FFmpeg revision `0893feba65` and NVIDIA driver 610.74.
Desktop Duplication and encoding overrides require an installed FFmpeg build.
To install one, run `winget install Gyan.FFmpeg`.

On macOS, you need the following:

- macOS and Python 3.10 or later.
- Apple's command-line developer tools, which build the screen capture helper on the first run.
- [Homebrew](https://brew.sh), for libusb. Before macOS 12.3, the bridge also needs FFmpeg.
- A USB-A-to-USB-C cable. If the Mac has only USB-C ports, add a USB-C-to-USB-A adapter. Over a USB-C-to-USB-C cable, the goggles take the USB host role and the Mac can't detect them.

The stream script offers to install whatever is missing. Tests used an M2 Pro MacBook Pro with macOS 27.0, Swift 6.4.2, and Homebrew FFmpeg 8.1.1.

## Start streaming

1. Power on the goggles, connect a USB data cable, and open **More > DJI Virtual Flight**. On a Mac, when macOS asks whether the accessory can connect, select **Allow**.
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

   On Windows, the script finds the DJI driver and uses the included encoder. To specify another driver path, pass `--dll`. To use another encoder executable, pass `--ffmpeg`.

   On a Mac, the script offers to install anything that's missing, and it builds the screen capture helper on the first run. If the screen can't be captured, go to **System Settings > Privacy & Security** and allow screen recording for your terminal.

The default output is **1920x1080** at a **100 fps encoder target**. Windows uses **32 Mbps**, or automatically selects **24 Mbps at 60 fps** and **30 Mbps at 75 fps**. macOS uses **20 Mbps**. To stop streaming, press **Ctrl+C**. The bridge writes logs to `work/logs/`.

Use these options to adjust the stream:

| Option | Values |
| --- | --- |
| `--fps` | `60`, `75`, `90`, `100` |
| `--bitrate-mbps` | `8`, `10`, `12`, `16`, `20`, `24`. On Windows, also `30`, `32`, and `40` |
| `--display` | Monitor index, starting at `0` |
| `--hide-cursor` | Hide the mouse pointer |
| `--capture` | Windows: `gfxcapture` or `ddagrab`. macOS: `screencapturekit` or `avfoundation` |

Run `python scripts/stream_desktop.py --help` for all options.

For example, use `python scripts/stream_desktop.py --fps 90` to target 90 fps.
These values set the stream rate, not the goggles' panel refresh rate. Lower
rates provide more bits per frame at the same bitrate, but increase the time
between frames. The 100 fps target has the shortest frame interval.

Windows encoding uses gradual refresh to reduce periodic compression blur.
For details, see the [quality measurements and reproduction steps](docs/research/WINDOWS_QUALITY.md).

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
