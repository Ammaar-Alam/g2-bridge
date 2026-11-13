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

1. Set `__version__` in `goggles_bridge/__init__.py` in a pull request titled `chore(release): VERSION`, and merge it.
2. On GitHub, go to **Actions > Release**, and then select **Run workflow**.
3. Under **Releases**, open the draft. Write the headline and the **What's Changed** entries, and then select **Publish release**.

The app updates only to a release that isn't a pre-release. To publish an update, clear **Set as a pre-release** before you select **Publish release**.

The workflow builds the installer for the version on `main` and attaches it to a draft pre-release. It fills in the installer's SHA-256 and the pull requests merged since the last release from `.github/RELEASE_TEMPLATE.md`. Publishing the draft creates the version tag.

The macOS app isn't packaged yet.
