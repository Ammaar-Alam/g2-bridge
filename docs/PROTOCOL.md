# Stock Goggles 2 PC video route

This describes the route visibly verified on one DJI Goggles 2 with owner-reported firmware 01.11.00.00. Static recovery, offline verification, and observed hardware behavior are distinguished below.

## Evidence and method

The Android Virtual Flight APK was inspected without installing it. REA provided package inventory/evidence capture, JADX exposed the accessory and native entry points, and focused Ghidra analysis recovered the H.264 send chain. Memory-only ARM emulation checked serializer and video-fragment outputs; concise oracle fixtures are in `tests/fixtures/`.

| Artifact | SHA-256 |
| --- | --- |
| Original APK | `e6181ea1f5e1dab39f67713c647d1c175de614019b90252a082fd8f2bd122fc2` |
| ARM32 `libUE4.so` | `c75d099fa9b7a4962909171808857a51c4ef88a02f21e9ae40c1e05924c66df7` |
| Verified x64 DJI `libusb0_device.dll` | `d2c16bd7c7fb2344408259fd083c8fdbeda3b096b8c9d07e48848e99fc2c3743` |

Relevant original ELF virtual addresses include `VideoSend` at `049f0128`, V1 serialization at `049f5c74`, and V2 serialization at `049f6448`. `UDjiDFSMGameInstance::OnBackBufferReady_RenderThread` at `04f64a9c` selects 1920x1080 for ZV900; its actual compression callback is `OnFinishCompress` at `04f663a0`. The Android encoder configures H.264, 60 fps, 10,485,760 bits/s, and a three-second I-frame interval. Those are sender settings, not proof of a receiver display-rate limit.

The original mobile video format is V2, with up to 65,404 encoded bytes per fragment and optional LogicLink wrapping. It was reproduced offline but remained black through the PC USB interface in bounded live tests. The smaller V1 adaptation below is original bridge behavior, not a claim that the Android app emits it.

## USB and session

The device enumerates as VID `2ca3`, PID `0020`. The verified video/control interface is **MI04**, class/subclass/protocol `ff/43/01`, bulk OUT `04`, bulk IN `85`, with 512-byte endpoint max packets. The backend checks that exact descriptor and refuses ambiguous devices. It does not reset the device or change its USB configuration.

DJI's x64 libusb0 ABI extends the device structure with an additional 512-byte location field. Using the unmodified upstream PyUSB structure was incompatible. The backend is therefore bound to the exact verified DLL above and PyUSB 1.3.1. Driver calls are divided into at most 2048-byte transfers. Consecutive video packets can share a transfer; offline byte reassembly and visible hardware tests confirmed batching.

PC control uses V1 source type 10 / id 1. Each reply is matched by route, command, and sequence, and must have a success status. Before sending video:

| Request | Destination | Payload |
| --- | --- | --- |
| Heartbeat `00/00` | type 28 / id 0 | `000020000000` |
| Identity `00/ff` | type 28 / id 1 | `00` |
| Simulator mode `0b/1a` | type 28 / id 0 | `01010000` |

The tested identity contains `E3T ZV900 AC`. Heartbeats continue every 500 ms. A simulator-mode acknowledgement alone means only that the command succeeded. Original moving imagery in the goggles established video acceptance separately.

## Working video packets

Video command `0b/53` is carried in raw DUML V1, request/no-ACK, source type 10 / id 1 to destination type 28 / id 1. The V1 size limit is 1023 bytes: 13 bytes framing/checksum + 32 bytes metadata + **978 encoded bytes**. Control and video share a 16-bit packet sequence allocator, which skips outstanding control requests.

The video payload starts with this little-endian structure, followed by the encoded chunk:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 1 | Zero |
| 1 | 1 | Frame needs multiple fragments |
| 2 | 1 | Last fragment of frame |
| 3 | 1 | Zero |
| 4 | 4 | Global fragment counter, wrapping uint32 |
| 8 | 8 | Millisecond timestamp, with the native truncation below |
| 16 | 4 | Metadata size: 32 |
| 20 | 4 | Encoded bytes in this chunk |
| 24 | 1 | First fragment of frame |
| 25 | 7 | Zero padding |

The timestamp preserves the native operation: sample Unix milliseconds, retain the low 32 bits, interpret them as signed, then sign-extend to 64 bits. It is not a full-width Unix millisecond value. The packet header CRC8 uses seed `77`, reflected polynomial `8c`; CRC16 uses seed `3692`, reflected polynomial `8408`, without a final XOR.

The encoder supplies Annex-B H.264 with AUDs for host-side access-unit splitting. AUDs are removed before transmission; SPS/PPS and every other NAL are retained. Each complete access unit is fragmented with first/last markers. This parser deliberately requires AUD-equipped encoder output and is not a general arbitrary-H.264 picture parser.

## Quality and timing boundaries

The current responsive desktop path is Windows Graphics Capture, GPU bicubic scaling with aspect preservation, and direct D3D11 input to NVENC. The tested preset sends 1080p100 at 20 Mbps, p4/ultra-low-latency, no B frames, a two-frame rate-control buffer, and three-second keyframes. The goggles visibly accept it; actual distinct panel frames and end-to-end latency remain unmeasured.

Earlier Desktop Duplication capture at a requested 100 fps produced substantial repeated output frames in a static-desktop test. A moving source and the newer GPU capture path improved the observed smoothness. Neither a console fps counter nor a USB write success proves a new image was displayed. Source rendering, capture duplication, encoding, USB queueing, decode, and scanout must be considered separately.

A slight gray/brightness pulse tracked the keyframe interval from one second to three seconds in a controlled visual comparison. This ties the effect to keyframes, but does not by itself identify the exact rate-control mechanism. Periodic intra-refresh and constant-quality encoding are investigation candidates, not verified fixes.

No firmware was flashed, unlocked, or modified. Other device models and receiver firmware remain outside the verified scope.
