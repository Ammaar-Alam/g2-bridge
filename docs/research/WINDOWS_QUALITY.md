# Windows encoding quality

These tests compare the original Windows encoder with the quality and pacing
changes. The quality configuration improves decoded synthetic images and
reduces median host delay on the tested PC. The headset comparison did not
establish a noticeable improvement. Panel cadence and optical latency remain
unverified.

The frame-size safeguards from [PR #18](https://github.com/Ammaar-Alam/g2-bridge/pull/18)
apply to Windows encoding. Defaults adapt to the selected frame rate, and an
oversized picture triggers an encoder restart without reopening USB.

## Encoder changes

At 100 fps, the quality configuration uses NVENC High profile, the `p1` preset, 32 Mbps
constant bitrate (CBR), quarter-resolution two-pass rate
control, and single-slice gradual intra refresh. Output stays at 1920x1080 and
100 fps, with a 400,000-bit video buffering verifier (VBV) buffer, no B frames,
zero output delay, and
immediate AVI frame delivery. The default recovery interval is three seconds.
The same encoding settings apply to Desktop Duplication. Windows selects
24 Mbps at 60 fps, 30 Mbps at 75 fps, and 32 Mbps at 90 or 100 fps.
The buffer cannot exceed 448,000 bits or two frames of the previous 20 Mbps budget.
macOS encoding remains unchanged.

Gradual refresh replaces the recurring instantaneous decoder refresh (IDR)
pictures that blurred text in the decoded comparison. The first picture is
an IDR. The buffer setting is not a guaranteed maximum picture size.
Before transmission, the bridge rejects Windows pictures larger than 56,000 bytes.
It stops the encoder, discards queued dependent pictures, and starts an encoder
that supplies a fresh IDR. The USB session and packet sequence remain intact.
Three oversize events with less than five seconds between successive events
stop the stream with an error instead of restarting indefinitely.

Both inspected streams declare three reference frames, three decoded-picture
buffers, zero reordered frames, and a picture-timing output delay of two ticks.
Their sequence parameter set (SPS) timing declares 100 fps. These fields do not
measure receiver delay.

## Image quality

Tests used an RTX 5060 Laptop GPU, driver 610.74, and FFmpeg `0893feba65`.
Each configuration encoded the same deterministic reference. Peak signal-to-noise
ratio (PSNR) and structural similarity (SSIM) measure fidelity to that reference.
Whole-sequence PSNR comes from FFmpeg's final summary, which accumulates mean
squared pixel error before conversion to decibels. It is not the arithmetic
mean of per-frame PSNR.
The following table compares the original `p4` configuration at 20 Mbps with
the `p1` quality configuration at 32 Mbps:

| Source | Frames per configuration | P4 PSNR | P1 PSNR | P4 SSIM | P1 SSIM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Moving test pattern | 1,800 | 45.017 dB | 49.354 dB | 0.995329 | 0.997853 |
| Static text | 1,800 | 43.542 dB | 51.596 dB | 0.999043 | 0.999753 |
| Moving pattern with abrupt changes | 1,800 | 44.825 dB | 49.055 dB | 0.995369 | 0.997825 |
| Fine-detail fractal zoom | 600 | 35.600 dB | 38.391 dB | 0.977695 | 0.986324 |

The abrupt-change source inverts colors at frame 211 of each 347-frame cycle,
then restores them at the next cycle boundary. These transitions do not align
with the three-second recovery
interval. All output frames decoded at 1080p with no B frames.

At frame 300, text SSIM rises from 0.938979 to 0.999635. This crop compares
decoded pixels at that frame. The image labels identify each configuration:

![The original Windows stream blurs fine text at a periodic keyframe. The quality configuration retains sharp text in the same frame.](../images/windows-quality-pulse.png)

The largest pictures across these four sources were 55,649 bytes for the
original settings and 42,643 bytes for the quality configuration. Sustained
motion traffic increases. The
moving-texture capture test produced approximately 20.9 versus 32.8 Mbps,
including DUML framing. Smaller observed peak pictures do not eliminate the
extra transmission cost of larger ordinary pictures.

An additional 600-frame comparison at every supported rate improved both
sequence PSNR and mean SSIM for motion, text, and abrupt changes.
The baseline uses `p4` at 20 Mbps. The quality configuration uses the defaults
for each rate, and both encoders use the same buffer cap:

| Rate | Motion PSNR, P4 to P1 | Text PSNR, P4 to P1 | Abrupt changes PSNR, P4 to P1 |
| --- | --- | --- | --- |
| 60 fps | 47.644 to 51.726 dB | 41.678 to 48.559 dB | 47.517 to 51.449 dB |
| 75 fps | 47.523 to 51.639 dB | 41.740 to 48.553 dB | 47.320 to 51.417 dB |
| 90 fps | 46.039 to 50.296 dB | 41.285 to 48.021 dB | 45.797 to 50.112 dB |
| 100 fps | 44.988 to 49.290 dB | 41.919 to 47.138 dB | 44.801 to 49.026 dB |

These clips differ in duration across rates, so compare configurations within
each row. Individual motion pictures can be larger with the quality configuration.
The 100 fps motion and text encodes match all 600 pictures from the previously
measured candidate byte for byte.

At 60 and 75 fps, the fine-detail source also improved, from 37.932 to 39.753 dB
and from 36.961 to 39.856 dB, respectively. All 4,800 pictures from the quality
configuration across these eight comparisons fit the 56,000-byte limit.
The largest was 51,371 bytes.

These scores measure encoder output before the transmission guard. The baseline
text encodes produced pictures of 60,525 and 59,137 bytes despite the buffer cap.
The guard would reject those pictures. Neither the buffer setting nor these
finite tests guarantee that every possible source fits the limit.

## Host timing

These runs measured the encoder changes before the capture-pacing change
described in [Recovery after capture stalls](#recovery-after-capture-stalls).

Two runs per configuration captured the monitor region occupied by an owned
D3D11 test window. The window rendered a moving seeded texture and a timestamp
protected by a checksum. Each run contained 1,800
frames. The first 100 were excluded. The loaded condition added an offscreen graphics
workload. The table gives the range of the two runs' statistics, not confidence
intervals:

| Condition | P4 median | P1 median | P4 p95 | P1 p95 |
| --- | --- | --- | --- | --- |
| Moving texture | 9.119-9.186 ms | 7.968-7.988 ms | 9.782-9.937 ms | 8.694-8.724 ms |
| Moving texture with GPU contention | 11.249-11.405 ms | 10.586-10.692 ms | 17.067-18.864 ms | 18.076-18.160 ms |

Both configurations delivered approximately 100 encoded packets/s. Under contention,
the P1 median was lower, but the p95 ranges overlapped and source duplicates
remained. The synthetic graphics workload completed 237.9-239.9 frames/s with
the previous settings and 235.6-237.4 with the new settings. Source rendering was 181.7-187.5 versus
181.7-182.0 frames/s. These results do not measure simulator performance.

Timing ends when a complete encoded packet reaches the host reader. It excludes
USB transmission and receiver behavior and does not prove unchanged or reduced
optical latency.

The normal bridge and packetizer also carried 900 frames per configuration through a
simulated USB endpoint. Both streams fully decoded. Checks covered packet checksums,
frame reconstruction, encoder shutdown, and the actual logged configuration.
The quality configuration also passed 600-frame bridge and decoding checks
at each of 60, 75, 90, and 100 fps, including SPS timing and clean shutdown.
After integration with the frame-size safeguards, all 14,400 reference pictures
from the paired quality checks reproduced byte for byte. All 7,200 pictures
from the quality configuration fit the transmission limit.

Encoder recovery tests cover mid-stream and startup oversize events, repeated
failures, encoder startup failure, cancellation, forced termination, and pipe closure.
A real NVENC test injects an oversized picture at frame 50. The bridge restarts
only the encoder and sends 200 pictures through one simulated USB session.
All 200 pictures decode at 1080p and match the expected reference pictures byte for byte.
This test does not measure goggles recovery or optical delay.

## Windows capture ceiling

Windows Graphics Capture uses a 1000 fps capture ceiling. The existing frame
selector limits output to `--fps` before encoding. The encoder configuration,
resize filter, and frame-size guard remain unchanged. macOS keeps its 240 fps
capture ceiling, and an explicit `--capture-fps` value overrides the default.

The ceiling controls the capture session's minimum update interval and
FFmpeg's repeated-frame timing. For the implementation, see the
[FFmpeg Graphics Capture source](https://github.com/FFmpeg/FFmpeg/blob/0893feba65/libavfilter/vsrc_gfxcapture_winrt.cpp).
The comparison changes this ceiling from 240 to 1000 while keeping the
bounded-credit selector and 100 fps encoder target fixed.

Tests use an owned D3D11 window with a moving seeded texture and a timestamp
protected by a checksum. A separate offscreen shader completes 60 workloads/s.
Each source has two 900-picture runs per configuration in A-B-B-A order.
The first 100 pictures are excluded from timing. The GPU is an RTX 5060 Laptop
with driver 610.74 and FFmpeg `0893feba65`.

The source and background workload maintain their requested rates in every
measurement window. Recorded GPU clocks overlap within each comparison.
The following ranges describe the two runs, not confidence intervals.
Fresh-frame delay starts at source render submission and ends when the host
receives the first encoded picture with that timestamp:

| Source | Distinct fps, 240 to 1000 | Fresh median, 240 to 1000 | Fresh p95, 240 to 1000 |
| --- | --- | --- | --- |
| 1080p at 100 fps | 93.65-95.34 to 99.97-99.98 | 8.63-8.86 to 7.70-7.77 ms | 15.08-15.26 to 11.27-11.39 ms |
| 1080p at 30 fps | 29.96-30.00 to 29.97-30.00 | 6.93-7.40 to 7.03-7.10 ms | 11.72-11.89 to 7.98-8.23 ms |
| 2400x1500 at 144 fps | 91.04-93.06 to 99.91-99.92 | 8.19-8.27 to 7.89-7.91 ms | 12.30-13.00 to 11.20-11.25 ms |

The 30 fps source retains its distinct frame rate, and median-delay ranges
overlap. Time-weighted source age also improves in each group. Repeated
pictures therefore do not account for the reported improvement. All 10,800
pictures decode, all steady-state timestamp checks pass, and every picture
fits the 56,000-byte limit. The largest picture is 52,826 bytes.

Higher capture rates can consume more CPU. In the scaled-source comparison,
encoder-process CPU time rises from 1.45-1.47 to 1.67-1.84 seconds per
900-picture run. Source and background-workload throughput stay stable in
that test. This result does not establish unchanged application performance
on every PC.

The [per-run results](evidence/capture-ceiling.json) include source and
workload rates, fresh-frame delay, time-weighted age, and GPU telemetry.
These are direct-window host measurements with 1 ms source-timestamp
resolution. They exclude physical USB, goggles decoding, and panel scanout.
They do not establish headset frame rate or end-to-end latency.

## Capture timestamp jitter

Fixed time slots can discard valid frames when capture runs near the target
rate. In a 600-frame reproduction, alternating timestamp offsets of +0.5 and
-0.5 ms reduced output to 301 distinct frames. This occurred at each target
rate: 60, 75, 90, and 100 fps. The source contained 600 distinct frames and
matched the target rate on average.

The selector instead tracks the next eligible capture timestamp, allowing
one frame of timing credit. It advances that timestamp by one target interval
after each selection and resets it to the current timestamp after a gap.
Credit cannot accumulate during a stall. Faster sources can emit one extra
startup frame. Subsequent selection stays within the target rate plus one
frame of burst allowance. The filter adds no wait or frame queue.

The [frame-ID check](../../tools/research/check_frame_pacing.py) covers 252 cases:
four targets, seven source rates, three jitter phases, and gaps of 0, 20, or
200 ms. It includes sources 0.1 fps above and below each target. All source
frames survive when the source rate is at or below the target in these cases.
Faster sources remain rate-limited, IDs stay ordered and unique, and the first
frame after each gap passes immediately. These checks exercise the actual
FFmpeg filter. They do not measure headset delivery or optical latency.

Two controlled 1080p sources also pass through NVENC, the AVI reader, the
bridge engine, DUML serialization, and simulated USB. Each run supplies 600
numbered NV12 frames at 100 fps. One source contains a gradient and moving
rectangle. The other contains a seeded moving fine texture. Both carry a
frame ID protected by a checksum, which is verified after decoding.

With alternating timestamp offsets of ±0.5 ms, both sources deliver 301
pictures with the fixed-slot selector and all 600 with the corrected selector.
The corrected streams match the regular-timestamp reference byte for byte.
All 8,404 pictures across 16 runs decode, the largest picture is 45,716 bytes,
and no encoder restarts occur.

Timing starts when each input frame is submitted and ends at the simulated
USB write. The comparison uses only frame IDs delivered by both versions,
excluding the first 100 source frames. Two runs per configuration alternate
in A-B-B-A order:

| Source with timestamp jitter | Fixed-slot median | Corrected median | Fixed-slot p95 | Corrected p95 |
| --- | --- | --- | --- | --- |
| Gradient and moving rectangle | 3.602-3.648 ms | 3.465-3.486 ms | 4.062-4.063 ms | 3.930-3.942 ms |
| Moving fine texture | 4.126-4.151 ms | 3.949-3.978 ms | 4.641-4.786 ms | 4.466-4.501 ms |

Without timestamp jitter, both versions deliver all frames, timing ranges
overlap, and the encoded streams are identical. The result establishes
recovered frames in this controlled case. It does not establish a general
latency reduction: these runs exclude Windows capture, physical USB, and the
goggles. Capture can also repeat an unchanged image, so encoded packet counts
alone do not establish the rate of distinct source images.

## Recovery after capture stalls

Graphics Capture can skip timestamps while its consumer is blocked. FFmpeg's
constant-frame-rate conversion fills that gap with copies of older pictures.
The Windows Graphics Capture path limits raw frames to the target rate with
bounded timing credit and assigns consecutive encoder timestamps. It adds no
frame buffer and does not discard encoded H.264 reference pictures.

The selection allows half an input timestamp tick for rounding. The `setpts` filter
also clears the previous frame-duration metadata, which would otherwise cause
an initial duplicate for a source slower than the encoder target. For details, see the
[FFmpeg select and setpts reference](https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect).
The encoder declares the requested rate. Actual delivery can be lower
when capture is slower or interrupted.

The original stall-fix check covered 72 cases: four target rates, three source rates,
and gaps of 0, 20, or 200 ms, before and after the change. For a source matching
the target rate, a 200 ms gap previously generated 12, 15, 18, or 20 duplicate
frames at 60, 75, 90, or 100 fps. The filter generates none and preserves every
source frame at the tested regular source rates. An isolated
pacing-filter comparison preserved all 4,800 encoded motion and text pictures
byte for byte, with the encoder settings held fixed.

Direct-window Graphics Capture tests used an owned D3D11 moving texture and
timestamps protected by checksums. Each run encoded 900 frames with a 100-frame warmup
and blocked the encoded-output reader for 200 ms after picture 350. Recovery
means the first of five consecutive valid pictures under 20 ms old after the
reader resumes. Runs alternated between the original pacing and the filter
in an A-B-B-A order. The table gives the ranges for two runs per configuration:

| Target | Original pacing recovery | Filter recovery |
| --- | --- | --- |
| 60 fps | 17.3-18.4 ms | 12.6-15.1 ms |
| 75 fps | 22.7-24.6 ms | 12.3-12.7 ms |
| 90 fps | 27.5-28.1 ms | 13.1-13.7 ms |
| 100 fps | 34.2-35.4 ms | 13.5-16.4 ms |

At 100 fps, the next 100 pictures contained 92-93 distinct timestamps before
the change and 100 after it. Normal-delay ranges overlapped. This is a recovery
improvement, not a demonstrated reduction in steady latency. A separate 50 ms
stall comparison showed no consistent improvement. These are direct-window
host measurements. They exclude USB transmission and the goggles' display path.

Reproduce the frame-ID checks without screen capture, a GPU, or USB:

```powershell
python tools/research/check_frame_pacing.py --output work/frame-pacing.json
```

Use `--ffmpeg` to select the executable. The results file records the
commands, binary hash, frame counts, and duplicate counts for every case.

## Reproduce the quality comparison

The [comparison tool](../../tools/research/compare_quality.py) uses the actual
bridge encoder command for the quality configuration. Its baseline uses `p4`
at 20 Mbps with the same buffer cap, without the pacing filter, gradual refresh,
or multipass encoding.
It never opens USB or captures the desktop. FFmpeg needs NVENC support.
The text source needs Windows Consolas. To compare the synthetic sources, run:

```powershell
python tools/research/compare_quality.py --output work/quality-comparison --frames 1800 --sources motion text cuts
python tools/research/compare_quality.py --output work/detail-comparison --frames 600 --sources detail
```

Use `--ffmpeg` if the executable is not on PATH. Choose a new output directory
for each run. The tool saves its commands, FFmpeg hash, encoded clips, metrics
logs, and per-frame results. A null PSNR value denotes a lossless frame or
sequence. The `lossless_frames` field identifies those frames explicitly.

Use `--fps 60`, `--fps 75`, or `--fps 90` to compare another supported frame rate.
Hardware comparisons need the same simulator workload and the
[optical measurement method](../LATENCY.md).
