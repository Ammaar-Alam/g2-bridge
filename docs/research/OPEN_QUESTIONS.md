# Open questions

## Latency and displayed frame rate

The live A/B comparison favored the optimized mode, and host framing and send times decreased. Further timing measurements and receiver analysis are needed to answer these questions:

- How much delay comes from capture freshness, encoding, transport, receiver buffering, and panel presentation?
- How much does a real simulator's GPU load add in-game? Synthetic saturation roughly doubled host latency and realtime GPU scheduling for the encoder recovered most of it, but no in-game or optical measurement under load exists yet.
- How does the receiver buffer pictures? The stream has no B frames and signals no reordering. Its three reference/decoder-buffer pictures do not establish a three-frame presentation delay.
- Does the receiver use the one-frame decoded picture buffer (DPB) offset in picture-timing supplemental enhancement information (SEI)? Removing SEI preserved decoded pixels offline but gave no clear subjective improvement. A USB interruption also occurred. The cause is unknown, and SEI removal was not adopted.
- How many distinct frames reach the panels? Source, capture, encoder, and panel frame rates can differ. A 100 fps send counter measures only the sender.
- Can ScreenCaptureKit raise the macOS capture rate above about 79 distinct frames per second and remove the 25 ms that AVFoundation adds before encoding? How far do the lenses trail a Mac display?

## Quality and pacing

The encoder and capture tests leave these issues unresolved:

- A subtle pulse followed the keyframe interval from one to three seconds. The contribution of rate control and decoding is unknown.
- High/p4 improved offline reference metrics at 20 Mbps without signaling frame reordering. The goggles displayed it correctly, but receiver latency was not measured.
- Intra refresh reduced a synthetic keyframe dip but created larger scene-change bursts. A useful replacement must preserve quality while bounding transmission delay.
- The source display's aspect ratio differs from the goggles. The pinned `gfxcapture` implementation places fitted content at the top left. Scaling and placement need explicit control in any replacement capture path.
- The attempted D3D11 scaler failed resource creation. Its device/texture requirements need investigation before that path can be compared fairly.

## USB reliability and receiver diagnostics

The following details remain unknown:

- What causes intermittent device disappearance and the observed fallback from 480 Mbps to 12 Mbps?
- What do simulator status `d6` and diagnostic status `e0` mean?
- How does the receiver schedule decoded pictures for display? Receiver firmware has not been recovered. The public firmware-tools code refers to an unavailable ZV900 encryption key.
- Is there another receiver configuration request that affects latency? The traced mobile initialization callbacks did not reveal one.

## Other platforms and mobile work

The packet layer is portable. Windows and macOS have been tested with one Goggles 2. Linux, other goggles, and other firmware versions need descriptor checks, control exchanges, and video tests.

An iOS relay or diagnostic app remains unimplemented. The original iPhone Virtual Flight app displayed video, but a custom app's accessory protocols, entitlements, signing, and store eligibility have not been verified. A relay would require a phone during streaming. Apple's [EASession](https://developer.apple.com/documentation/externalaccessory/easession) and [protocol declaration](https://developer.apple.com/documentation/bundleresources/information-property-list/uisupportedexternalaccessoryprotocols) describe the APIs to investigate for a custom client. Access to the goggles' channel remains unverified.
