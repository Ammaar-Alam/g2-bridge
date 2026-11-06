# Start here

Last research update: November 6, 2026. Phase: research complete enough to start a hardware-assisted investigation; no bridge implementation or device tests yet.

## Goal and owner constraints

Make **DJI Goggles 2** display an existing FPV simulator running on the owner's Windows PC, starting with **Uncrashed**. Keep normal simulator behavior and controller input on the PC. The owner does not want a new simulator.

Use this order of preference:

1. Windows software and an ordinary data cable, with stock goggles firmware.
2. A small Raspberry Pi bridge if the mobile USB connection cannot be reproduced through a normal PC-facing interface.
3. Firmware modification only if the simpler routes fail and the owner authorizes a concrete, recoverable procedure.

No purchase, firmware modification, public release, or contact with third parties is authorized. The owner authorized creating this private repository and tracking these agent notes for the handoff. The owner intends to consider publication if the project works.

## Hardware and environment

The following information comes from the owner or the initial tool inspection:

| Item | Known information | Still to verify |
| --- | --- | --- |
| Goggles | DJI Goggles 2, not FPV Goggles V2 | Exact firmware, USB descriptors, working simulator mode |
| Desktop | Windows PC with Uncrashed or similar simulators | Windows version, CPU architecture, GPU, available USB ports |
| Graphics hardware | Owner has a graphics card or display adapter | Exact model and hardware encoding support |
| Phone | iPhone | Model, iOS version, Virtual Flight availability and working display |
| Android phone | None supplied for this investigation | Not required for offline APK analysis |
| Raspberry Pi | Owner does not have one; a small bridge is acceptable at most | Whether a bridge is needed; no order requested |
| Controller | Model not supplied | Only needed when testing simulator controls; do not assume RC2 or Motion Controller |
| Windows tools | Owner believes Ghidra is installed | Version, Java compatibility, and REA integration |

The original research session ran on a Mac. Its tool configuration does not establish anything about the Windows PC. REA 6.7.0 responded, with skill version 42. Hopper was available. Ghidra was unconfigured, Java selected by REA was 11.0.18, and the Android JADX provider was missing. No binary target was opened. Do not copy the Mac's paths or settings into Windows configuration.

## Read in this order

Use these documents for the next session:

1. [Windows handoff](WINDOWS.md): concrete setup, experiments, and success criteria.
2. [Research and evidence](RESEARCH.md): primary sources, reported prototypes, model distinctions, and open questions.
3. [Artifact acquisition](ARTIFACTS.md): the verified original Android download path and provenance requirements.
4. [REA skill snapshot](skills/README.md): the user-requested skill and its reference guides.
5. [Publication procedure](PUBLISHING.md): how to keep internal material out of a later public history.

## Completed work

The initial investigation established the following:

- Official DJI documentation supports Goggles 2 in mobile Virtual Flight and excludes goggles from its Windows version.
- The Android connection references Android Open Accessory (AOA). PC-facing USB and mobile USB personalities must be treated separately.
- A recent researcher reported a Pi-based video-input prototype, but exact Goggles 2 validation and a public release were not located.
- Existing Moonlight/WTFOS instructions target older goggles. Video-output projects do not establish video-input support.
- DJI's original Android APK download entrypoint was found. A HEAD request confirmed a roughly 1.99 GB object. The APK was not downloaded, hashed, signature-checked, or decompiled.
- The owner chose an iPhone as the available reference device and plans to continue on Windows with Ghidra.

## Next experiment

On the Windows PC, open this repository in Codex, verify that the tools execute on that PC, then inventory the powered goggles through the documented USB-A-to-USB-C data connection. Record firmware and interfaces without changing the device.

In parallel with hardware availability, acquire the original Virtual Flight APK and trace its video-sending path through JADX and native analysis. Resolve the session setup, framing, encoder configuration, transport, and keepalives before writing a transmitter. Do not restart broad simulator-compatibility research.

## Completion gates

Track progress against these gates:

- [x] Gather primary compatibility, transport, and existing-project evidence.
- [x] Locate the original official Android download entrypoint.
- [x] Prepare portable research and a Windows handoff in a private repository.
- [ ] Verify REA and the required analysis providers on Windows.
- [ ] Record the owner's exact goggles firmware and USB interfaces.
- [ ] Identify and verify the downloaded APK, then recover the relevant send path.
- [ ] Confirm mobile Virtual Flight displays in the goggles, if the iPhone app is available.
- [ ] Establish a source-grounded session with stock goggles from the selected transport.
- [ ] Display our own moving test image in both lenses and measure end-to-end delay.
- [ ] Stream Uncrashed, test reconnect behavior, and measure sustained latency and stability.
- [ ] Decide whether latency is useful for FPV practice with the owner, based on measurements.
- [ ] Prepare a separate publication review if requested.

No numerical latency requirement has been agreed. Do not borrow DJI aircraft-link latency figures or older-goggles Moonlight results as acceptance criteria.

## Update after each session

Record what changed, the exact environment and artifact identities, observed results, unresolved questions, and the next smallest test. Keep raw captures in ignored `work/`; include a hash and a redacted evidence summary here. A useful failure narrows one hypothesis without claiming global impossibility.
