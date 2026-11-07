# G2 Bridge

Stream your Windows desktop to DJI Goggles 2 over USB. The goggles use Virtual Flight mode with stock firmware. The simulator and controller run on the PC.

## Requirements

You need the following hardware and software:

- 64-bit Windows and Python 3.10 or later.
- An NVIDIA GPU with NVENC support.
- FFmpeg with `gfxcapture` and `h264_nvenc`. See [FFmpeg builds for Windows](https://www.gyan.dev/ffmpeg/builds/).
- DJI bulk driver 5.0.0.7 and its matching x64 `libusb0_device.dll`. See [USB and driver requirements](docs/PROTOCOL.md#usb-and-session).

Tests used Goggles 2 firmware **01.11.00.00**, FFmpeg build `2026-11-05-git-0893feba65`, and NVIDIA driver 610.74.

## Start streaming

1. Power on the goggles, connect a USB data cable, and open **More > DJI Virtual Flight**.
2. From the repository root, install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the stream. Replace `DJI_USB_DLL_PATH` and `FFMPEG_PATH` with the paths to `libusb0_device.dll` and `ffmpeg.exe`:

   ```powershell
   python scripts/stream_desktop.py --dll "DJI_USB_DLL_PATH" --ffmpeg "FFMPEG_PATH"
   ```

The default output is **1920x1080**, with a **100 fps encoder target** and a **20 Mbps** bitrate. Press **Ctrl+C** to stop. Logs are written to `work/logs/`.

Use these options to adjust the stream:

| Option | Values |
| --- | --- |
| `--fps` | `60`, `100` |
| `--bitrate-mbps` | `8`, `10`, `12`, `16`, `20`, `24` |
| `--display` | Monitor index, starting at `0` |
| `--hide-cursor` | Hide the mouse pointer |
| `--capture` | `gfxcapture` or `ddagrab` |

Set `DJI_USB_DLL` and `GOGGLES_FFMPEG` to avoid repeating the file paths. Run `python scripts/stream_desktop.py --help` for all options.

## Run tests

Run the tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

See the [PC protocol](docs/PROTOCOL.md) and [reverse-engineering data and tools](docs/research/README.md) for packet layouts and reproduction steps.
