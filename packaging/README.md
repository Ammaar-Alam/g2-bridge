# Package the desktop app

The app is a pywebview window over the stream engine. Its code is in `goggles_bridge/app/`, and its interface is plain HTML, CSS, and JavaScript in `goggles_bridge/app/ui/`.

## Build on Windows

Install the app's dependencies, PyInstaller, and [Inno Setup 6](https://jrsoftware.org/isdl.php). Then run the build script from the repository root:

```powershell
python -m pip install -r requirements-app.txt pyinstaller==6.22.3
python packaging/build_windows.py
```

The script writes the app folder to `dist/Goggles Bridge/` and the installer to `dist/GogglesBridge-VERSION-Setup.exe`. Without Inno Setup, it builds only the folder.

The build downloads a pinned FFmpeg build and checks its SHA-256. That build repeats frames when the screen is still. FFmpeg 9.0 and earlier don't.

To check that a built app starts, run it with `--self-test`. It opens a hidden window, waits for the interface to draw, and exits with code 0.

## Preview the interface

Open `goggles_bridge/app/ui/index.html` in a browser. Opened as a file, the interface runs on simulated data. Add `?state=streaming`, `waiting`, `unplugged`, `nodriver`, or `error` to hold one state.

## Release

1. Set `__version__` in `goggles_bridge/__init__.py`, and merge the change.
2. Push a tag with the same version, such as `0.1.0`.

The release workflow builds the installer and creates a draft pre-release from `.github/RELEASE_TEMPLATE.md`, with the installer's SHA-256 and the merged pull requests filled in. Write the headline and the **What's Changed** entries, and then publish the draft.

The macOS app isn't packaged yet.
