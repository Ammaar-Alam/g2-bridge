# Stereo and head tracking

The bridge sends one 1920x1080 picture, and both lenses show it. PC VR needs two more things from the goggles: a different picture for each eye, and the head orientation. On stock Goggles 2 firmware, both panels show the same picture, and no way to read head orientation over USB has been found. This page records the evidence and the display test.

## Hardware

DJI's [specifications](https://www.dji.com/support/product/goggles-2) list, for each screen, a 0.49-inch 1920x1080 display at up to 100 Hz with a 51° field of view. The interpupillary distance range is 56 to 72 mm and the diopter range is -8.0 to +2.0. SeeYA Technology [states](https://www.seeya-tech.com/en/html/news/4037.html) that it is the exclusive supplier of these micro-OLED panels. Its [0.49-inch 1920x1080 panels](https://www.seeya-tech.com/en/html/products/3971.html) use a MIPI interface; the exact variant, lane count, and maximum refresh rate are not published.

[Teardown photos](https://fpvwiki.co.uk/dji-goggles-2) show these parts:

| Part | Marking or observation |
| --- | --- |
| DJI P1 | `P1 V10R03`, next to Samsung DDR4 `K4A4G165WF`. Community sources describe it as the OcuSync 3 radio modem |
| DJI E3T | `E3T V10R05`, with its own memory. Community sources describe it as the media processor for the operating system and video. The PC identity reply names it: `E3T ZV900` |
| Radio | Two `IE1000` chips with four antenna connectors |
| Storage | Samsung eMMC `KLM8G1GETF` |
| Displays | Each panel and lens sits in its own sliding carriage, with its own cable to the main board |

Each eye therefore has a separate panel with its own link. The photos do not show whether the E3T has two independent display outputs or drives both panels from one image. In either case, the firmware decides what each panel shows. Goggles 2 firmware (`zv900`) is signed with a 3072-bit key and encrypted with a key that is not public ([dji-firmware-tools](https://github.com/o-gs/dji-firmware-tools/blob/master/dji_imah_fwsig.py)), so it cannot be modified without DJI's keys.

The 51° field of view is about half that of typical PC VR headsets, so even a stereo picture would look like a window rather than surround the user.

The goggles also have head tracking: with supported aircraft, head movement turns the aircraft and tilts the gimbal. The goggles Shortcut Menu turns it on ([manual](https://dl.djicdn.com/downloads/DJI_Goggles_2/20221117/DJI_Goggles_2_User_Manual_v1.0_en.pdf), page 36). The goggles therefore contain an orientation sensor. No DJI document says how its data leaves the goggles, apart from the radio link to the aircraft.

## Separate views for each eye

Nothing found so far shows the stock firmware driving the two panels with different pictures:

- **No 3D playback.** The [Goggles 2 release notes](https://www.dji.com/downloads/products/goggles-2) from v01.02 to v01.11 add no 3D or side-by-side mode. A [Heliguy FAQ](https://www.heliguy.com/blogs/knowledge-base/does-dji-goggles-2-support-3d-video-playback/) also answers no. Later releases were not checked. DJI lists 3D playback for Goggles 3, a later model.
- **Virtual Flight sends one view.** The Android app encodes one 1920x1080 H.264 picture for ZV900 and sends the same buffer to the goggles object. The 32-byte video metadata has fragment flags, a counter, a timestamp, and sizes. Its remaining bytes are zero padding, with no eye or layout field. See the [mobile protocol](MOBILE_PROTOCOL.md).

A live test checked whether the goggles route each half of a wider or taller picture to a different panel. The [stereo probe](../../tools/research/stereo_probe.py) streams a test pattern through the normal handshake and video packets. Each view shows the same moving gray pattern with a red border for the left view and a blue border for the right view. All layouts use H.264 High profile, level 5.1, at 60 fps.

On November 7, 2026, a ZV900 with firmware 01.11.00.00 showed the whole picture, with both borders, in each eye for every layout:

| Layout | Encoded size | Sent | Each eye showed |
| --- | --- | --- | --- |
| `sbs` | 1920x1080, two 960x1080 views | 45 s, 60 fps | Red and blue views side by side |
| `fsbs` | 3840x1080, two 1920x1080 views | 55 s, 60 fps | Red and blue views side by side, fitted to one screen |
| `ftb` | 1920x2160, two 1920x1080 views | 35 s, 60 fps | Red and blue views, both visible |

The decoder accepts pictures larger than 1920x1080 at level 5.1 and fits the whole picture to the display. Both panels then show the same image. On this firmware, picture layout cannot give each eye its own view. Separate views would need a mode that the stock receiver does not expose.

To repeat a layout, open Virtual Flight and run:

```powershell
python tools/research/stereo_probe.py fsbs --seconds 60
```

The goggles reject a new simulator session immediately after the previous one ends, with status `d6`. Leave and reopen Virtual Flight, or restart the goggles, between runs.

## Head orientation over USB

No source shows the goggles reporting orientation to a PC:

- **No orientation traffic.** About 43 minutes of logged desktop streaming, including sessions in which the goggles were worn, contained 11,246 packets from the goggles. All were heartbeat replies, identity and simulator-mode replies, `00/81` advertisements, and the `09/43` status push. The three probe runs added 713 packets of the same five types.
- **No menu option.** In Virtual Flight mode, the goggles menu shows no head-tracking option.
- **Virtual Flight does not use it.** The goggles class in the Android app handles heartbeat, firmware version, simulator mode, video, and controller status pushes. The app's strings refer to a controller gimbal wheel but not to goggles orientation.
- **No public command.** The public [DUML dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector/wireshark) names command set 21 `Glass` but lists no commands for it. Its gimbal set has no head-tracking command. The goggles firmware is encrypted with an unpublished key, as noted in [related work](RELATED.md).

Head tracking likely sends gimbal and flight commands from the goggles to the aircraft over the radio link, which a USB host does not see. That is an inference. Finding a request that makes the goggles report orientation over USB would need firmware analysis or an unbounded command search. Unknown commands can change device state, so the bridge does not send them.

## SteamVR

Stereoscopic SteamVR is not possible on stock firmware, because both eyes receive the same picture. A flat SteamVR view is possible in principle. An external tracker such as [OpenTrack](https://github.com/opentrack/opentrack) can supply the head pose, and drivers such as [OpenVR-OpenTrack](https://github.com/r57zone/OpenVR-OpenTrack) draw the headset view in a desktop window that the bridge can capture. This combination has not been tested.
