# G2 Bridge

Stream your Windows desktop to DJI Goggles 2 over USB. The goggles use Virtual Flight mode with stock firmware; the simulator and controller run on the PC.

## Requirements

- 64-bit Windows and Python 3.10 or newer.
- An NVIDIA GPU with NVENC support.
- FFmpeg with `gfxcapture` and `h264_nvenc`. [Windows builds](https://www.gyan.dev/ffmpeg/builds/).
- DJI bulk driver 5.0.0.7 and its matching x64 `libusb0_device.dll`. [Driver details](docs/PROTOCOL.md#usb-and-session).

Tested with Goggles 2 firmware **01.11.00.00**. The tested FFmpeg build is `2026-11-05-git-0893feba65`, with NVIDIA driver 610.74.

## Run

Power the goggles, connect a USB data cable, and open **More > DJI Virtual Flight**.

```powershell
python -m pip install -r requirements.txt
python scripts/stream_desktop.py --dll "PATH/TO/libusb0_device.dll" --ffmpeg "PATH/TO/ffmpeg.exe"
```

The default output is **1920x1080**, with a **100 fps encoder target** and **20 Mbps** bitrate. Press **Ctrl+C** to stop. Logs are written to `work/logs/`.

| Option | Values |
| --- | --- |
| `--fps` | `60`, `100` |
| `--bitrate-mbps` | `8`, `10`, `12`, `16`, `20`, `24` |
| `--display` | Monitor index, starting at `0` |
| `--hide-cursor` | Hide the mouse pointer |
| `--capture` | `gfxcapture` or `ddagrab` |

Set `DJI_USB_DLL` and `GOGGLES_FFMPEG` to avoid repeating the file paths. Run `--help` for all options.

## Tests

```powershell
python -m unittest discover -s tests -v
```

[Protocol details](docs/PROTOCOL.md)
