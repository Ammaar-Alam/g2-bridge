# Windows encoder helper

The Windows default uses a modified FFmpeg executable to reduce oversized pictures during encoder startup. It waits for a captured image before producing output, analyzes the first two pictures at full resolution, and then restores quarter-resolution analysis. The bridge retains its bitrate and 56,000-byte transport guard.

The bridge checks the mode change before connecting to the goggles. If the NVIDIA driver rejects the change, the bridge checks the standard encoding path. It uses an installed FFmpeg executable when available, or disables startup protection in the included helper. An explicit `--ffmpeg` argument or `GOGGLES_FFMPEG` value takes precedence. Desktop Duplication, P4, and adaptive quantization use the installed encoder.

The helper is built from the following sources:

- [FFmpeg revision 0893feba652894f836cb76617936da52570d20a5](https://github.com/FFmpeg/FFmpeg/tree/0893feba652894f836cb76617936da52570d20a5).
- [NVIDIA codec headers revision e844e5b26f46bb77479f063029595293aa8f812d](https://github.com/FFmpeg/nv-codec-headers/tree/e844e5b26f46bb77479f063029595293aa8f812d), SDK 13.0.
- The changes in [startup.patch](startup.patch).

## Rebuild the helper

Use an MSYS2 UCRT64 shell with these packages installed:

```bash
pacman -S --needed curl tar xz make diffutils patch mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-nasm
```

From the repository root, build the helper:

```bash
bash tools/build_windows_encoder.sh
```

The script verifies the source archives, applies the patch, builds the executable, and checks the required encoder option and raw-frame pipeline. Output is written to `artifacts/windows-encoder/`. The build directory is retained for inspection.

`source.tar.xz` contains both complete upstream source archives, the patch, this guide, and the build script. To rebuild from that package, extract it and run the same command from its `g2-encoder-source` directory. The verified source archives are already included in its cache.

The helper contains Windows capture, NVENC, H.264 decoding, and the filters and formats used by the bridge. It is not a general replacement for an installed FFmpeg distribution. GPU encoding and goggles playback require separate validation; the build smoke test does not exercise them.

## Licenses

This modified FFmpeg helper and its patch use the GNU Lesser General Public License, version 2.1 or later. See [COPYING.LGPLv2.1](COPYING.LGPLv2.1). NVIDIA header notices are in [NVIDIA-NOTICES.txt](NVIDIA-NOTICES.txt). Runtime library notices accompany the executable in `windows-x64/licenses/`.

`windows-x64/BUILDINFO.txt` records the source revisions, patch and build-script hashes, compiler, and FFmpeg configuration. `windows-x64/SHA256SUMS` records the executable and corresponding source-package hashes.
