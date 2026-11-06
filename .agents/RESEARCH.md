# Research and evidence

Checked November 6, 2026. No hardware or binary-level claims in this document were independently reproduced unless marked as a local observation.

Use these evidence labels:

- **Official:** documented by the product or protocol owner.
- **Reported:** an upstream implementer describes their own result; not independently reproduced here.
- **Observed:** obtained by tools in the initial research session.
- **Inference:** a proposed explanation or design, not a verified behavior.
- **Unknown:** evidence is missing or does not cover this model and direction.

## R01: Mobile simulator imagery is supported

**Official.** [DJI's Virtual Flight support article](https://repair.dji.com/help/content?customId=01700008917&lang=en&paperDocType=ARTICLE&re=US&spaceId=17) lists Goggles 2 among supported mobile devices and excludes goggles from the Windows version. It instructs Goggles 2 users to enable **Menu > More > DJI Virtual Flight** and connect the phone with a data cable. Android troubleshooting explicitly mentions AOA communication. Compatible simulator controllers include FPV Remote Controller 2 and the original Motion Controller; do not assume the owner's controller model.

The article was retrieved through indexed content; some direct requests returned a regional selector. The [App Store release history](https://apps.apple.com/gb/app/dji-virtual-flight/id1541992396) also describes Goggles 2 connection and image fixes.

**Inference.** There is a software-controlled external imagery path. This does not establish a generic USB monitor interface, public SDK, or Windows-compatible transport. The actual video format, handshake, and authentication remain unknown.

## R02: Normal display inputs and wireless playback

**Official.** [DJI Goggles 2 specifications](https://www.dji.com/support/product/goggles-2) list no HDMI input/output or analog image transmission. They list DLNA wireless streaming and MP4/MOV playback with H.264/H.265 video and AAC/PCM audio. Playback codec support is not evidence of Virtual Flight's codec.

The [Goggles 2 manual](https://dl.djicdn.com/downloads/DJI_Goggles_2/20221117/DJI_Goggles_2_User_Manual_v1.0_en.pdf), page 36, permits wireless playback from a phone or computer. Page 44 documents a USB-A-to-USB-C connection for DJI Assistant 2 and says C-to-C computer connection is unsupported in that workflow. This does not establish that every experimental C-to-C topology is impossible.

DJI's advertised 30/40 ms aircraft transmission figures are not simulator, USB, or DLNA performance guarantees. No physical tests were performed here.

## R03: App maintenance and original package

**Official and observed.** The [Virtual Flight download page](https://www.dji.com/downloads/djiapp/dji-virtual-flight) states maintenance ended March 21, 2024. Catalog entries list iOS 1.4.3 and Android 1.4.0; old device lists do not certify present operating systems. The original Android download was recovered from exact app data in DJI's mobile product page. See [artifact acquisition](ARTIFACTS.md) for the verified entrypoint, size, and limitations.

## R04: Recent input prototype

**Reported.** The GitHub API exposed comments newer than the search engine's cached view of [fpv-wtf/voc-poc issue 15](https://github.com/fpv-wtf/voc-poc/issues/15):

- [October 11, 2026](https://github.com/fpv-wtf/voc-poc/issues/15#issuecomment-6113019440): YarosMallorca reported a Pi 4B prototype and said it should work with Goggles 2 and Integra. The statement does not identify which model was tested.
- [Latency follow-up](https://github.com/fpv-wtf/voc-poc/issues/15#issuecomment-6114626852): the author reported 125-200 ms through PC, network, Pi, and goggles USB.
- [October 12 follow-up](https://github.com/fpv-wtf/voc-poc/issues/15#issuecomment-6121697502): the author reported lower latency using Android, without a measurement.

Attachments were not independently inspected. Searches of the author's public repositories and website did not locate the promised input release. This is a bounded negative search, not proof that code is unavailable everywhere. The separately published [YStreamer documentation](https://ystreamer.yarosfpv.com/en/docs/) describes video leaving the goggles, not the input prototype. No message was sent to the author.

## R05: USB roles are a constraint, not a global impossibility proof

**Official.** [Android USB accessory documentation](https://developer.android.com/develop/connectivity/usb/accessory) defines the accessory as USB host and the phone as peripheral. [AOA 1.0](https://source.android.com/docs/core/interaction/accessories/aoa) documents setup requests and bidirectional bulk endpoints. [Windows dual-role documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-dual-role-driver-stack-architecture) requires suitable controller hardware and drivers. A USB-C connector alone does not establish peripheral capability.

**Inference.** A normal Windows USB host cannot reproduce a phone's peripheral behavior through application code alone when the controller lacks that role. However, Goggles 2 also has PC-facing interfaces. A route from those interfaces to the simulator decoder could avoid phone-role emulation. Neither that route nor its absence has been established.

An Android emulator or VM does not by itself create a USB peripheral controller. A passive hub also does not make a PC a transparent observer of an independent phone-to-goggles connection.

## R06: Goggles 2 USB output research

**Reported, with inspectable source.** [dr00min/o3-usb-decoder](https://github.com/dr00min/o3-usb-decoder) implements Goggles 2/O3 video output to a Pi. Its [protocol notes](https://github.com/dr00min/o3-usb-decoder/blob/main/docs/protocol_notes.md) describe a PC personality with USB ID `2ca3:0020`, RNDIS networking, mass storage, and vendor bulk interfaces. The Pi approach instead emulates the Android side of the mobile connection. The source names `raw_endpoint.py`, `gold_app_seq.py`, and `video_deframe.py` identify useful transport research.

Output packets and initialization traffic are clues, not an input implementation. Do not reverse packet direction or copy output start commands and claim simulator input. Exact endpoints, framing, firmware compatibility, power wiring, and session semantics must be established for the selected experiment. Never infer a safe wiring arrangement from a conceptual diagram.

## R07: Apple mobile role switching

**Reported, wrong model for a direct conclusion.** [samuelsadok/dji_protocol](https://github.com/samuelsadok/dji_protocol/blob/master/usb_mobile_protocol.md) documents an Apple-style mobile USB role switch and framed DUML/video channels. Its verified devices are Goggles N3 and a first-generation Mavic Pro controller. Its PC experiment uses special emulation hardware and has stated bus-state uncertainties.

The documented `55 cc` framing and `com.dji.logiclink` interface are search clues. They are not verified Goggles 2 simulator-input details. Do not copy N3 endpoints, payload lengths, or initialization packets into a Goggles 2 transmitter without evidence.

The [DJI-Unchained-VOC report](https://github.com/jtm2kfpv-git/DJI-Unchained-VOC/blob/main/report-source.md) is a useful map to these upstream sources, but is derivative research about video output. Prefer the underlying implementation or capture for technical claims.

## R08: Older-goggles Moonlight does not support this target

**Upstream documentation.** [dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim) supplies a goggles-side receiver for a Windows streaming client, using WTFOS. Its architecture is useful background, but it replaces the receiver path rather than implementing stock Virtual Flight's protocol.

The [WTFOS compatibility list](https://github.com/fpv-wtf/wtfos#compatability) supports older FPV Goggles V1/V2 and explicitly excludes Goggles 2 from its planned support. Older wiki statements saying to wait are not a supported root path. Moonlight's reported 7-14 ms result on an older-goggles setup does not apply to Goggles 2.

## R09: Engineering-unit work does not unlock retail Goggles 2

**Upstream documentation.** [ggurov/dji-goggles3-display-unit](https://github.com/ggurov/dji-goggles3-display-unit) concerns already-rooted Goggles 3 engineering units. Keeping their existing root after an update is not a retail Goggles 2 exploit.

No verified public retail Goggles 2 root method or direct Windows simulator-input implementation was found in the reviewed sources. That finding is scoped to the search, not a proof of impossibility. Firmware analysis may still reveal a stock entry point without requiring modification.

## R10: DLNA mirrors a desktop, with unsuitable reported delay

**Vendor report.** [GogglePlayer](https://goggleplayer.app/) offers Windows screen capture to Goggles 2 over DLNA. Its developer reports roughly three seconds of delay and says this is unsuitable for gaming. This establishes a practical video-input direction, not useful FPV latency. It does not prove that every possible DLNA implementation has an identical delay.

## R11: Video-output tools solve another direction

The following primary project pages describe video leaving goggles:

- [Cosmostreamer for Goggles 2](https://cosmostreamer.com/products/djigoggles2/): goggles-to-display video output.
- [DigiView](https://github.com/fpv-wtf/fpv_viewer_android): older FPV Goggles V1/V2 output to Android.
- [YStreamer](https://ystreamer.yarosfpv.com/en/docs/): goggles-to-Pi output and downstream streaming.

These products are not a Windows-to-Goggles-2 simulator solution. A label such as “USB video” is insufficient without confirming direction and model.

## Working hypothesis and unanswered questions

**Inference.** Reuse desktop capture and hardware encoding, then implement only the missing DJI transport. A PC-facing stock input path would provide the smallest runtime setup. If the mobile peripheral role is unavoidable, a Pi could forward an encoded stream while the simulator stays on Windows. Avoid decoding and re-encoding on the bridge unless the protocol requires it.

The next session must answer these questions:

| Question | Evidence needed | Status |
| --- | --- | --- |
| Which firmware and USB interfaces does the owner have? | Read-only device inventory | Unknown |
| What does Virtual Flight send? | APK manifest, Java/native send path, packet construction, encoder settings | Not analyzed |
| Is setup authenticated or tied to controller/firmware state? | Code trace and, where needed, working-session observations | Unknown |
| Can PC-facing endpoints reach the simulator decoder? | Source-grounded commands plus a moving-image hardware test | Unknown |
| Can the same stream pass through a Pi? | Reproduced protocol and a compatible USB peripheral controller | Reported elsewhere; unverified here |
| What resolution, frame rate, latency, and buffering are useful? | Measured output in the lenses, with capture conditions recorded | Unknown |

A test image, successful reconnect, and measured sustained performance are stronger evidence than a device appearing in Device Manager. Static analysis can resolve a protocol question; it cannot alone establish usable real-time display behavior.
