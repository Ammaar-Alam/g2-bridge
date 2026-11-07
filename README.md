# G2 Bridge

Stream your Windows desktop to DJI Goggles 2 over USB. The goggles use Virtual Flight mode with stock firmware. The simulator and controller run on the PC.

Measured latency is about 13-15 ms behind a 240 Hz laptop monitor at 1080p100 (RTX 5060 Laptop GPU, filmed at 240 fps with the GPU idle and with it saturated). For the method and both results, see [Measure video delay](docs/LATENCY.md) and the [experiments](docs/research/EXPERIMENTS.md#monitor-to-lens-delay).

## Requirements

You need the following hardware and software:

- 64-bit Windows and Python 3.10 or later.
- An NVIDIA GPU with NVENC support.
- FFmpeg with `gfxcapture` and `h264_nvenc`. To install it, run `winget install Gyan.FFmpeg`.
- [DJI Assistant 2 (Consumer Drones Series)](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series), which installs the DJI USB driver 5.0.0.7. See [USB and driver requirements](docs/PROTOCOL.md#usb-and-session).

Tests used Goggles 2 firmware **01.11.00.00**, FFmpeg build `2026-11-05-git-0893feba65`, and NVIDIA driver 610.74.

## Start streaming

1. Power on the goggles, connect a USB data cable, and open **More > DJI Virtual Flight**.
2. From the repository root, install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the stream:

   ```powershell
   python scripts/stream_desktop.py
   ```

   The script finds the DJI driver and FFmpeg automatically. If either is installed somewhere else, pass `--dll` or `--ffmpeg` with the file path.

The default output is **1920x1080**, with a **100 fps encoder target** and a **20 Mbps** bitrate. Press **Ctrl+C** to stop. Logs are written to `work/logs/`.

Use these options to adjust the stream:

| Option | Values |
| --- | --- |
| `--fps` | `60`, `100` |
| `--bitrate-mbps` | `8`, `10`, `12`, `16`, `20`, `24` |
| `--display` | Monitor index, starting at `0` |
| `--hide-cursor` | Hide the mouse pointer |
| `--capture` | `gfxcapture` or `ddagrab` |

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
