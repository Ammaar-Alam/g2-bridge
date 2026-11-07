# Experiments

Hardware tests used one stock DJI Goggles 2 with ZV900 identity and owner-reported firmware 01.11.00.00. All PC tests used the same USB-A-to-USB-C cable. The original iPhone Virtual Flight app also displayed video successfully.

Timings below measure work on the PC. Screen-to-lens latency and the goggles' displayed frame rate were not measured.

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

Two phone recordings at 240 fps measured how far one goggle lens trails the 240 Hz reference monitor. Both used the test pattern from [Measure video delay](../LATENCY.md), the same goggles, cable, and PC, and the default stream settings: 1920x1080, 100 fps target, 20 Mbps, High profile, `p4`, low-latency framing, and 16 KiB USB writes. Both recordings reached the PC as 1/8-speed exports rather than original camera files. The pattern's 0.65-second cadence confirmed that playback scale in each file, so one stored frame is one 4.17 ms camera frame, but the exports leave the frame timing unverified.

| Recording | Bridge | GPU load during the take | Transitions | Median delay | Range |
| --- | --- | --- | ---: | ---: | --- |
| November 7, first | `6eacb9e`, unchanged | Idle desktop | 18 | 13.3 ms | 6.7–26.7 ms |
| November 7, second | Realtime GPU scheduling for the encoder | Offscreen shader holding the GPU near 95% | 12 | 14.6 ms | 12.5–20.8 ms |

The second take kept the lens delay within about 1 ms of the idle result while the GPU was saturated. The unchanged bridge was not filmed under that load, so the table doesn't show how much worse the first configuration gets in that condition. The PC-side timings in the preceding section are the only measurement of that difference. Threshold choice moved the medians by at most 2 ms, and three nearby lens regions agreed within 4 ms.

These values are lens delay relative to the monitor, including both displays' scanout and response. They are not controller-to-photon latency.

## Live A/B comparison

On November 7, the AVI reader, 16 KiB writes, and High profile each displayed video correctly. In a sequential A/B comparison, the tester preferred B for responsiveness but still noticed delay and variable quality. The runs used different live content:

- A used source `170824e`, the original CRC implementation, the Annex-B reader, filler, a three-frame queue, 2 KiB writes, and Baseline profile. It sent 3,461 frames in 35 seconds.
- B used source `d82c892`, the faster CRC implementation, and `--low-latency --usb-write-size 16384 --h264-profile high`. Resolution, frame rate, bitrate, preset, and capture settings were unchanged.

At roughly 20–21 Mbps of wire traffic, the median of the five-second intervals' 95th-percentile send times was about 5.41 ms for A and 1.75 ms for B. The corresponding queue-time medians were about 0.19 and 0.08 ms. These queue measurements exclude the Annex-B parser's frame hold.

The [host telemetry](evidence/live-host-telemetry.json) contains per-interval data and connection events.

## Timing metadata and USB interruptions

The stream's sequence parameter set (SPS) declares a fixed rate of 100 fps. Picture-timing supplemental enhancement information (SEI) specifies a decoded picture buffer (DPB) output delay of 2 ticks, or 10 ms. Whether the goggles honor it is unknown.

A trial removed SEI NAL units, type 6, as well as filler. The retained clip had one buffering-period message and 300 picture-timing messages. All retained NAL payloads and all 300 decoded pictures were identical after removal.

The tester reported inconsistent smoothness and quality, with no clear improvement. At 70.24 s the USB device disappeared spontaneously, then reconnected at 72.27 s. The trial was stopped and B restored. The cause of the USB fault is unknown. SEI removal is not enabled in the bridge.

Other interruptions occurred before this trial, including one high-speed-to-full-speed fallback. The slow descriptor had speed code 1 and 64-byte bulk packets. Reconnecting the same cable and port restored speed code 2 and 512-byte bulk packets. The bridge refuses the insufficient full-speed profile. Cable, controller, driver and device causes remain unresolved.

A later B run lost the device after about 116 seconds, and the client exited. No DJI device was present afterward. It is unknown whether the goggles had been powered off.
