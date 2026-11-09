# Experiments

Hardware tests used one stock DJI Goggles 2 with ZV900 identity and owner-reported firmware 01.11.00.00. All PC tests used the same USB-A-to-USB-C cable. The original iPhone Virtual Flight app also displayed video successfully.

## Frame-rate targets

The bridge accepts 60, 75, 90, and 100 fps encoder targets. These settings do not
select a panel refresh mode. DJI lists [1920x1080 per screen and up to 100 Hz](https://www.dji.com/support/product/goggles-2)
for Goggles 2. Distinct frames displayed in Virtual Flight still need optical measurement.

On Windows, four-second synthetic encodes at each target decoded to 240, 300,
360, and 400 frames respectively. All were 1920x1080 High profile with no B
frames. Their SPS timing declared the requested rate, and the bridge's packetizer
preserved every encoded access unit.

Two live desktop-capture runs per rate used a CRC-protected timestamp strip,
300 frames per run, and excluded the first 40 frames. Results on an RTX 5060
Laptop GPU with FFmpeg `0893feba65` were:

| Target | Encoded packets/s, run 1 / run 2 | Distinct source timestamps per 260 samples |
| ---: | --- | --- |
| 60 | 60.00 / 60.00 | 260 / 260 |
| 75 | 74.98 / 74.96 | 260 / 260 |
| 90 | 89.94 / 89.89 | 259 / 260 |
| 100 | 100.09 / 100.09 | 259 / 260 |

These are idle host measurements, without USB or a game workload. They do not
establish panel cadence or optical latency. Lower rates increase the interval
between images and the bit budget per image at a fixed bitrate.

ScreenCaptureKit previously encoded every complete or idle callback despite
setting `ExpectedFrameRate`. Apple documents that this property is an
[encoder hint, not a rate control](https://developer.apple.com/documentation/videotoolbox/kvtcompressionpropertykey_expectedframerate).
The helper now accepts the first raw frame in each target-rate time slot and
skips further callbacks in that slot. It adds no waiting queue and never drops
an encoded reference picture. This limits excess submissions; it cannot create
fresh images when the display or simulator runs below the target rate.

## Transport tests

The following tests varied the source address, packet format, and USB interface:

| Test | Observation |
| --- | --- |
| Mobile-source V1 heartbeat on PC USB | No matched replies in the bounded run |
| Change sender to type 10/id 1 (`2a`) | Matched heartbeat, identity and simulator-mode success |
| Enter acknowledged simulator mode | Waiting screen changed to black |
| Native mobile V2 video on MI04 | No test pattern appeared. The first run lost USB after 16.609 s |
| V2 with native LogicLink | Black during a 45 s run with 90 matched heartbeats |
| V2 with PC source address | Black during 40 s / 2,399 frames |
| V2 with 2 KiB transfers | Black during 45 s / 2,699 frames |
| V2 with AUD removal | Still black |
| MI03 video attempt, control on MI04 | First 2,048-byte write timed out; no completed video frame |
| 1080p60 V2, PC source, 2 KiB, no AUD | Black during 180 s / 10,798 frames |
| 1080p60 native wrapped V2 | Black during 40.921 s / 2,449 frames |
| Complete 1080p60 frames adapted to V1 `0b/53` | Moving generated bars/circles visible; 120 s / 7,199 frames / 169,439,762 bytes, no USB error |
| Desktop and Uncrashed through V1 | Video confirmed in both lenses; flight usable |

MI03 was an inference from another product's Assistant `dbus_pc.json`, and had not been established for Goggles 2. MI05–MI07 were not tested for video input.

A single `0b/1b` diagnostic request and two General `00/ea` log-export candidates returned `e0`. No log configuration was obtained. A later reconnect attempt returned simulator status `d6`. The meanings of `e0` and `d6` remain unknown.

## Capture and host framing

Desktop Duplication with CPU scaling did not reliably provide distinct 100 fps output in the initial tests. Windows Graphics Capture with GPU aspect-fit bicubic scaling and D3D11-to-NVENC input improved the observed responsiveness. The source display was 2560x1600 at 240 Hz. In the pinned gfxcapture implementation, 1728x1080 fitted content is top-left aligned in the 1920x1080 canvas, leaving 192 pixels on the right. The older CPU path centered its padding.

The original Annex-B parser holds a complete picture until the next access unit delimiter (AUD) arrives. A paired test fed the same incoming encoder bytes to both the original reader and a local streaming-AVI packet reader. After 60 startup frames, the additional old-reader hold averaged about 9.33 ms on gray and 9.35 ms on motion, with p95 about 16.5 ms. AVI carries packet lengths from FFmpeg to Python and is removed before USB transmission.

Removing filler network abstraction layer (NAL) units, type 12, preserved all decoded pixels in the retained 300-frame test. A full real-encoder/simulated-USB comparison also matched every decoded frame for gray and motion. Gray wire bytes fell from 7,849,205 to 28,682. Motion wire bytes changed from 7,852,451 to 7,851,543.

CRC16 was converted from a Python reflected-byte loop to a bit-reflection transform around C-backed `binascii.crc_hqx`. Native oracles and independent bitwise tests pass. A retained 300-frame serialization benchmark fell from about 1.126 to 0.137 ms/frame with identical wire SHA-256. See the [CRC benchmark results](evidence/crc-benchmark.json).

The 16 KiB write check used the real transport chunking method with a simulated endpoint and 300 actual encoded frames. Calls fell from 3,945 to 601, and median calls per frame fell from 13 to 2. The complete wire SHA-256 remained `f47192eaf01cbefea91702f78a335238ff1fcfaa558d5caf2e06f1b15f3ebd6b`. All reassembled packets and frames matched. The [write-equivalence results](evidence/usb-write-equivalence.json) measure call counts, not USB speed.

## Encoder quality

Unless stated otherwise, tests used 1920x1080, a 100 fps target, 20 Mbps constant bitrate (CBR), preset `p4`, ultra-low-latency tuning, no B frames, zero output delay, a two-frame video buffering verifier (VBV) buffer, and a 300-frame group of pictures (GOP). Filler was removed.

Each comparison decoded 600 frames. The motion source was `testsrc2` with a gray rectangle. The desktop source was a compressed 300-frame capture repeated twice, with a scene discontinuity at frame 300. Its images are not published.

Structural similarity (SSIM) and peak signal-to-noise ratio (PSNR) measure fidelity to the reference images:

| Mode | Motion SSIM / PSNR | Desktop SSIM / PSNR | Finding |
| --- | --- | --- | --- |
| Baseline/p4 | 0.994244 / 44.047 dB | 0.999513 / 63.048 dB | Reference |
| High/p4 | 0.995240 / 44.999 dB | 0.999590 / 63.663 dB | Higher scores on both sources. Desktop size fell from 3,563,921 to 2,963,206 bytes (16.86% less) |
| Single-slice intra refresh | 0.994242 / 44.025 dB | 0.999507 / 63.165 dB | Smaller synthetic keyframe dip. Largest desktop frame grew from 49,428 to 96,612 bytes |
| One-frame VBV | 0.990258 / 41.590 dB | 0.999092 / 62.581 dB | Lower scores. Motion payload averaged about 13.4 Mbps against a 20 Mbps target |
| Refresh + one-frame VBV | 0.990365 / 41.622 dB | 0.999154 / 62.801 dB | Largest desktop frame reached 80,389 bytes |
| High/p1 | 0.995207 / 44.911 dB | 0.999386 / 63.135 dB | Desktop SSIM below Baseline/p4 |
| High/p4, 16 Mbps | 0.993124 / 43.243 dB | 0.999420 / 63.199 dB | Did not match the 20 Mbps reference's motion quality |

For the 16 Mbps run, VBV was scaled to 320,000 bits to preserve its two-frame duration. Per-frame metrics and sizes are in `evidence/quality-*.json`. These scores do not measure perceived quality.

High/p4 tests using a rendered timestamp strip delivered about 100.10 host packets/s. Median time from render submission to packet release was 9.535 and 9.213 ms in two runs, compared with 9.268 and 9.235 ms for Baseline. A separate post-capture encode/output check measured 2.541 and 2.548 ms for Baseline, and 2.581 and 2.604 ms for High. High added about 0.05 ms in that sample.

Other PC tests produced these results:

- A direct filter graph and a 1,000 fps capture ceiling gave no consistent gain. Limiting capture to 100 fps produced more repeated frames in the constant-frame-rate output on the 240 Hz display.
- Desktop Duplication with `scale_d3d11` failed texture creation with `80070057`.
- Sampling the Windows clock did not produce duplicate millisecond timestamps despite its reported coarse resolution.
- Explicit RGB color flags did not expose a color-range mismatch. NVENC produced limited-range BT.601-family samples with matching bitstream metadata.

## Capture under GPU load

All earlier PC timings ran on an idle desktop. A simulator with no frame-rate limit saturates the GPU, so the same timestamp-strip method was repeated while an offscreen OpenGL shader kept the GPU busy at about 260 frames per second. Values are medians and 95th percentiles over 210 to 260 steady frames per run, with two or more runs per condition.

| Condition | Render-submit to packet, median / p95 | Capture-timestamp to packet, median / p95 |
| --- | --- | --- |
| Idle, default | 7.3 / 9.3 ms | 2.4 / 2.7 ms |
| GPU saturated, default | 12.9–13.9 / 17.5–35.0 ms | 3.8–3.9 / 6.6–6.9 ms |
| GPU saturated, encoder GPU scheduling class HIGH | 13.0–13.1 / 17.6–18.1 ms | 3.8–4.1 / 6.6–6.8 ms |
| GPU saturated, encoder GPU scheduling class REALTIME | 10.2–10.7 / 14.4–15.5 ms | 3.1–3.2 / 3.4–3.6 ms |
| GPU saturated, encoder CPU class HIGH | not run | 3.3 / 6.4 ms |
| Idle, REALTIME | not run | 2.4 / 2.7 ms |

GPU scheduling class REALTIME is set on the FFmpeg process with `D3DKMTSetProcessSchedulingPriorityClass`. It did not require elevation on the tested Windows 11 machine. The call returns `0xC000000D` for a process that has not yet touched the graphics stack, so the bridge applies it when the first encoded frame arrives and records the result in the `streaming` log event. Setting it at that point measured the same as setting it at process start (loaded p95 3.1–3.2 ms against 5.2–5.3 ms unprioritized in a lighter-load repeat). The synthetic load keeps one frame in flight, which is lighter than a game with several queued frames, so the in-game gain may differ.

Encoder presets were also compared at idle. Medians for render-submit to packet were 7.3 ms for `p4`, 7.1–7.3 ms for `p3`, 6.3–6.7 ms for `p2`, and 6.3–6.6 ms for `p1`. The faster presets cost measured desktop fidelity in the encoder quality table above, so the default stays `p4`.

## Monitor-to-lens delay

The camera measurements used DJI Goggles 2 firmware 01.11.00.00, an RTX 5060 Laptop GPU, and a 240 Hz monitor. Streams targeted 1920x1080 at 100 fps and 20 Mbps, with High/`p4` encoding and 16 KiB USB writes.

The following results use 50% brightness crossings in the recorded monitor and lens regions:

| Recording | Capture path | GPU load | Transitions | Median delay | Range |
| --- | --- | --- | ---: | ---: | --- |
| November 7, first | Windows desktop, `6eacb9e` | No added load | 18 | 13.3 ms | 6.7-26.7 ms |
| November 7, second | Windows desktop, realtime encoder GPU scheduling | Offscreen shader near 95% utilization | 12 | 14.6 ms | 12.5-20.8 ms |
| November 7, native | D3D11 capture prototype | No added load | 20 | 12.1 ms | 2.1-16.5 ms |

The first recording used a 10%-speed export; the second used a 1/8-speed export. Their fixed 0.65-second pattern established the playback scale. The native recording used irregular flashes. Matching them to the source timestamp log gave 240.03 stored frames per second of capture time.

The native result has a mean of 10.3 ms and a 95th percentile of 16.0 ms. The analysis tracked a small patch in the lens and included all 20 transitions. Nearby regions changed some individual delays, while most retained a median near 12 ms. The capture paths, patterns, and load conditions differ across these recordings, so the table is not a matched A/B comparison.

For the counting method and cropped frames, see [Measure video delay](../LATENCY.md).

## Live A/B comparison

On November 7, the AVI reader, 16 KiB writes, and High profile each displayed video correctly. In a sequential A/B comparison, the tester preferred B for responsiveness but still noticed delay and variable quality. The runs used different live content:

- A used source `170824e`, the original CRC implementation, the Annex-B reader, filler, a three-frame queue, 2 KiB writes, and Baseline profile. It sent 3,461 frames in 35 seconds.
- B used source `d82c892`, the faster CRC implementation, and `--low-latency --usb-write-size 16384 --h264-profile high`. Resolution, frame rate, bitrate, preset, and capture settings were unchanged.

At roughly 20–21 Mbps of wire traffic, the median of the five-second intervals' 95th-percentile send times was about 5.41 ms for A and 1.75 ms for B. The corresponding queue-time medians were about 0.19 and 0.08 ms. These queue measurements exclude the Annex-B parser's frame hold.

The [host telemetry](evidence/live-host-telemetry.json) contains per-interval data and connection events.

## macOS

Tests used the same goggles and firmware build, identity `E3T ZV900 AC Dec 24 2024|12:34:04`. The Mac was an M2 Pro 14-inch MacBook Pro with a 3024x1964 display, macOS 27.0, Homebrew FFmpeg 8.1.1, libusb 1.0.30, and PyUSB 1.3.1. Stream settings were the defaults.

| Test | Observation |
| --- | --- |
| USB-C-to-USB-C cable | The goggles took the host role. The Mac port reported data role Device, and no USB device enumerated |
| USB-A-to-USB-C cable through a USB-C adapter | Enumerated as `2ca3:0020` at high speed with the same eight interfaces as the Windows fixture. macOS bound only MI02 mass storage |
| Control handshake, 15 s | Simulator mode acknowledged 43 ms after start, with no discarded bytes |
| Default stream, 120 s | Desktop displayed in the lenses. 11,947 frames at 100 fps, no reconnects, no discarded bytes, and a 95th-percentile send time of at most 0.71 ms |

FFmpeg repeated 2,532 of 11,949 output frames, so capture supplied about 79 distinct frames per second. On a mostly static desktop, requested capture rates of 100, 120, and 240 fps all produced about 77 frames per second. Requests for 30 and 60 fps held capture to those rates. The tester found motion less smooth than on Windows.

To measure capture-to-packet delay, FFmpeg carried AVFoundation presentation timestamps, which use the host clock, through an MPEG transport stream with `-copyts`. A script compared each packet's timestamp with Python's monotonic clock when the packet arrived. Each row covers 380 frames:

| Encoder setting | Median / p95 |
| --- | --- |
| VideoToolbox, default rate control | 72.1–75.0 / 83.8–91.8 ms |
| VideoToolbox, `-flags +low_delay` | 27.1 / 35.8 ms |
| libx264 `ultrafast`, `zerolatency` | 25.2 / 35.5 ms |
| MPEG-2 encode of a 320x208 frame | 30.0–33.9 / 42.7–47.4 ms |

The MPEG-2 encode costs almost nothing, so most of the remaining delay happens before encoding, in AVFoundation capture. GPU scaling with `scale_vt` used about a third of the CPU time of `swscale` bicubic scaling (1.1 s against 3.5 s over 5 s), with similar delay.

### ScreenCaptureKit

A Swift prototype captured with ScreenCaptureKit and encoded with VideoToolbox's low-latency rate control. Each frame carried the `displayTime` that ScreenCaptureKit reports, and the reader compared it with `mach_absolute_time` when the frame arrived in Python. With a 120 fps `testsrc2` window on screen, each path ran for about 8 seconds:

| Capture | Display or capture time to packet, median / p95 |
| --- | --- |
| ScreenCaptureKit prototype | 7.2 / 10.7 ms |
| AVFoundation through FFmpeg, `-flags +low_delay` | 24.7 / 32.9 ms |

The prototype delivered about 104 new pictures per second, against the 79 that AVFoundation supplied in the earlier stream.

The bridge's helper logs the same delay, measured when each encoded frame is written. Three 11-second runs with the test pattern sent 107–115 fps, 82–85 of them new pictures, with medians of 5.6–6.1 ms and 95th percentiles of 8.7–10.3 ms. `displayTime` sometimes led the encoder callback by up to 0.6 ms. In low-latency mode, VideoToolbox rejected `MaxFrameDelayCount` and `PrioritizeEncodingSpeedOverQuality` with `kVTPropertyNotSupportedErr`.

On the goggles, the helper streamed the desktop for 48.6 seconds and 4,284 frames. Its five-second medians were 2.4–5.6 ms, with 95th percentiles of 3.9–9.9 ms. The tester said it felt much better than the AVFoundation path. The session then ended with `[Errno 5] Input/Output Error`, and the goggles left the USB bus. The cause wasn't established. Screen-to-lens latency on the Mac was not measured.

## Timing metadata and USB interruptions

The stream's sequence parameter set (SPS) declares a fixed rate of 100 fps. Picture-timing supplemental enhancement information (SEI) specifies a decoded picture buffer (DPB) output delay of 2 ticks, or 10 ms. Whether the goggles honor it is unknown.

A trial removed SEI NAL units, type 6, as well as filler. The retained clip had one buffering-period message and 300 picture-timing messages. All retained NAL payloads and all 300 decoded pictures were identical after removal.

The tester reported inconsistent smoothness and quality, with no clear improvement. At 70.24 s the USB device disappeared spontaneously, then reconnected at 72.27 s. The trial was stopped and B restored. The cause of the USB fault is unknown. SEI removal is not enabled in the bridge.

Other interruptions occurred before this trial, including one high-speed-to-full-speed fallback. The slow descriptor had speed code 1 and 64-byte bulk packets. Reconnecting the same cable and port restored speed code 2 and 512-byte bulk packets. The bridge refuses the insufficient full-speed profile. Cable, controller, driver and device causes remain unresolved.

A later B run lost the device after about 116 seconds, and the client exited. No DJI device was present afterward. It is unknown whether the goggles had been powered off.

## Firmware 01.14

On November 8, 2026, a tester checked a Goggles 2 on firmware 01.14.00.00 from Windows 11, with an RTX 3080 and FFmpeg 9.0.2. The identity reply was `E3T ZV900 AC Aug 11 2026|07:21:27`. The firmware manifest named `01.14.0000`, with `ZV900_E3T` module `10.00.81.97`.

| Test | Result |
| --- | --- |
| Descriptors | MI04 `ff/43/01`, `0x04/512` and `0x85/512`, matching the tested profile |
| Heartbeat, identity, and simulator mode in Virtual Flight | Accepted. Request and reply bytes were identical to the 01.11 capture in [`pc-control-session.json`](evidence/pc-control-session.json), apart from the identity date |
| Probe test picture | 451 pictures at 30 fps over 15 seconds. The tester saw the test pattern |
| Desktop stream, default settings | Connected on the first attempt and sent 100 fps for 20 and 25 seconds, with every heartbeat answered. The tester saw the desktop |

Before Virtual Flight was opened, heartbeat and identity were answered, but simulator mode got no reply from `28/0`. A route scan then found identity answered with `00` only by `28/1`, `e0` from `28/0` and `28/2` to `28/5`, and no reply from `28/6` or `28/7`. Simulator mode got `e0` from `28/1`, `28/2`, and `28/4`. This matches the [Goggles 3 result](GOGGLES3.md#results), whose menu had no Virtual Flight entry. Opening Virtual Flight was the only change needed, so 01.14 didn't change the PC protocol. Integra on 01.14 and monitor-to-lens delay on 01.14 weren't tested.

## Frame size limit and bitrate

On November 8, 2026, the same tester streamed a full-screen zooming fractal to a Goggles 2 on firmware 01.14.00.00. This source holds the encoder at its target bitrate. Each run lasted 12 seconds and had a colored border, so that the tester's recording identified it. Keyframe sizes come from offline encodes with the same settings.

| Run | Settings | Keyframe size | Lenses |
| --- | --- | --- | --- |
| 1 | 20 Mbps, 2-frame VBV | 41 KB | Displayed |
| 2 | 20 Mbps, 8-frame VBV, AQ | 67 KB, then 53 KB | Appeared after a delay, consistent with the first keyframe dropped and the second displayed |
| 3 | 30 Mbps, 2-frame VBV | About 65 KB | Appeared, then froze |
| 4 | 40 Mbps, 2-frame VBV | 79 KB | Black |
| 5 | 40 Mbps, 8-frame VBV, AQ | 96 to 103 KB | Black |

After runs 4 and 5, the goggles stayed black and refused to leave Virtual Flight, reporting that a mobile phone was still connected. Unplugging USB didn't help, but a power cycle did. The tester had occasionally seen the same state with the unmodified bridge.

For the following runs, the bridge capped the encoder buffer at 448,000 bits (56 KB) and skipped frames over 65,536 bytes. The same four kinds of run were repeated after a power cycle:

| Run | Settings | Largest frame sent | Lenses |
| --- | --- | --- | --- |
| 1 | 20 Mbps | 42 KB | Displayed |
| 2 | 20 Mbps, 8-frame VBV, AQ | 47 KB | Displayed |
| 3 | 30 Mbps | 47 KB | Displayed |
| 4 | 40 Mbps, AQ | 49 KB | Displayed |

A 30-second 40 Mbps stream of the same source sent 2,962 frames at a steady 100 fps, with no frames skipped. The bridge logs the time from a frame leaving the encoder to its USB write returning. Over the 12-second runs, this time rose only slightly with bitrate once frames were capped. The uncapped runs were slower because of their oversize keyframes:

| Setting | USB send time per frame, p95 | Largest frame |
| --- | --- | --- |
| 20 Mbps | 1.5 ms | 42 KB |
| 30 Mbps | 1.9 ms | 47 KB |
| 40 Mbps, AQ, capped | 2.0 ms | 49 KB |
| 40 Mbps, uncapped | 5.2 to 5.9 ms | 79 to 103 KB |

The goggles' receive and decode time for a larger frame, and monitor-to-lens delay at 40 Mbps, weren't measured. The receiver's exact limit lies between 49 KB, which displayed, and about 65 KB, which froze.

On Windows, the bridge in this repository caps the encoder buffer at 56 KB, skips any frame over 56 KB, and then skips frames until the next keyframe that fits, because later frames reference the skipped one. In CBR, every frame averages the bitrate divided by the frame rate. The bridge refuses settings whose average frame is larger than 50 KB, which is the 40 Mbps at 100 fps case that displayed. It allows at most 24 Mbps at 60 fps, and 30 Mbps at 75 or 90 fps. The macOS encoders have no cap verified on the goggles, so macOS capture keeps the earlier 24 Mbps maximum, and its frames are never skipped.

In the tester's offline comparison on a zooming Mandelbrot source, adaptive quantization raised SSIM at 20 Mbps from 0.9705 to 0.9764. NVENC preset `p7` scored the same as `p4` and encoded 40% slower. These scores measure fidelity to the source, not quality or delay on the goggles. The effect of adaptive quantization on monitor-to-lens delay is untested, so `--aq` is off by default.
