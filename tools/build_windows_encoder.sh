#!/usr/bin/env bash
set -euo pipefail

if [[ ${MSYSTEM:-} != UCRT64 ]]; then
    echo "Use an MSYS2 UCRT64 shell" >&2
    exit 2
fi
task_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$task_root/vendor/ffmpeg/sources.env"
export SOURCE_DATE_EPOCH
task_cache="$task_root/work/encoder-cache"
task_output="$task_root/artifacts/windows-encoder"
task_build=$(mktemp -d /tmp/g2-encoder.XXXXXX)
mkdir -p "$task_cache" "$task_output" "$task_build/ffmpeg" "$task_build/nv-codec-headers" "$task_build/build"

fetch_source() {
    local name=$1 url=$2 digest=$3
    if [[ ! -f "$task_cache/$name" ]]; then
        curl --fail --location --connect-timeout 15 --max-time 120 "$url" -o "$task_cache/$name"
    fi
    printf '%s  %s\n' "$digest" "$task_cache/$name" | sha256sum --check --strict
}
fetch_source ffmpeg.tar.gz "https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/$FFMPEG_REV" "$FFMPEG_SHA256"
fetch_source nv-codec-headers.tar.gz "https://codeload.github.com/FFmpeg/nv-codec-headers/tar.gz/$NV_HEADERS_REV" "$NV_HEADERS_SHA256"
tar -xzf "$task_cache/ffmpeg.tar.gz" --strip-components=1 -C "$task_build/ffmpeg"
tar -xzf "$task_cache/nv-codec-headers.tar.gz" --strip-components=1 -C "$task_build/nv-codec-headers"
patch --batch --forward -d "$task_build/ffmpeg" -p1 < "$task_root/vendor/ffmpeg/startup.patch"
printf '2026-11-05-git-%s\n' "${FFMPEG_REV:0:10}" > "$task_build/ffmpeg/FF_VERSION"
make -C "$task_build/nv-codec-headers" PREFIX="$task_build/prefix" install
export PKG_CONFIG_PATH="$task_build/prefix/lib/pkgconfig"

# Keep local checkout and toolchain paths out of the executable
task_maps="-ffile-prefix-map=$(cygpath -m "$task_build")=/build -ffile-prefix-map=$(cygpath -m "$MINGW_PREFIX")=/toolchain"
export CFLAGS="$task_maps"
export CXXFLAGS="$task_maps"
cd "$task_build/build"
../ffmpeg/configure \
    --extra-version=g2-startup --disable-autodetect --disable-everything --disable-doc --disable-debug \
    --disable-ffplay --disable-ffprobe --disable-w32threads --enable-pthreads \
    --enable-ffmpeg --enable-d3d11va --enable-ffnvcodec --enable-nvenc \
    --enable-indev=lavfi \
    --enable-filter=gfxcapture,ddagrab,select,setpts,format,scale,pad,hwdownload,hwupload,showinfo,crop,color,testsrc2,split,fps \
    --enable-encoder=h264_nvenc,rawvideo,wrapped_avframe \
    --enable-decoder=h264,rawvideo,wrapped_avframe --enable-parser=h264 \
    --enable-muxer=avi,h264,null,rawvideo --enable-demuxer=h264,rawvideo \
    --enable-protocol=file,pipe --enable-bsf=filter_units,h264_metadata \
    --extra-ldflags='-static -Wl,--no-insert-timestamp'
make -j4 ffmpeg.exe
./ffmpeg.exe -hide_banner -h encoder=h264_nvenc > "$task_output/encoder-options.txt" 2>&1
grep -q startup_fullres "$task_output/encoder-options.txt"
./ffmpeg.exe -hide_banner -h filter=gfxcapture > "$task_output/capture-options.txt" 2>&1
grep -q wait_for_first_frame "$task_output/capture-options.txt"
./ffmpeg.exe -v error -f lavfi -i color=size=16x16:rate=1 -frames:v 1 \
    -c:v rawvideo -f rawvideo -y "$task_build/smoke.yuv"
[[ $(wc -c < "$task_build/smoke.yuv") -eq 384 ]]
cp ffmpeg.exe "$task_output/g2-encoder.exe"

mkdir -p "$task_output/licenses"
cp "$task_root/vendor/ffmpeg/COPYING.LGPLv2.1" "$task_root/vendor/ffmpeg/NVIDIA-NOTICES.txt" "$task_output/licenses/"
for license in libgcc 'libstdc++' libwinpthread; do
    cp -R "$MINGW_PREFIX/share/licenses/$license" "$task_output/licenses/"
done
{
    printf 'FFmpeg: %s\nNVIDIA headers: %s\nSOURCE_DATE_EPOCH: %s\n' "$FFMPEG_REV" "$NV_HEADERS_REV" "$SOURCE_DATE_EPOCH"
    (
        cd "$task_root"
        sha256sum vendor/ffmpeg/startup.patch tools/build_windows_encoder.sh
    )
    gcc --version | head -n 1
    nasm -v
    ./ffmpeg.exe -version
} > "$task_output/BUILDINFO.txt"
pacman -Q > "$task_output/toolchain-packages.txt"

task_package="$task_build/g2-encoder-source"
mkdir -p "$task_package/tools" "$task_package/vendor/ffmpeg" "$task_package/work/encoder-cache"
cp "$task_root/tools/build_windows_encoder.sh" "$task_package/tools/"
for name in sources.env startup.patch COPYING.LGPLv2.1 NVIDIA-NOTICES.txt README.md; do
    cp "$task_root/vendor/ffmpeg/$name" "$task_package/vendor/ffmpeg/"
done
cp "$task_cache/ffmpeg.tar.gz" "$task_cache/nv-codec-headers.tar.gz" "$task_package/work/encoder-cache/"
tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner \
    -cJf "$task_output/source.tar.xz" -C "$task_build" g2-encoder-source
cd "$task_output"
sha256sum g2-encoder.exe source.tar.xz > SHA256SUMS
printf 'Build output: %s\nBuild directory: %s\n' "$task_output" "$task_build"
