# Stereo and head tracking

The bridge sends one 1920x1080 picture, and both lenses show it. PC VR needs two more things from the goggles: a different picture for each eye, and the head orientation. This page records what is known about each on stock Goggles 2 firmware and the test that answers the display question.

## Hardware

DJI Goggles 2 has two 1080p micro-OLED panels, one for each eye. They also have head tracking: with supported aircraft, head movement turns the aircraft and tilts the gimbal. The goggles Shortcut Menu turns it on ([manual](https://dl.djicdn.com/downloads/DJI_Goggles_2/20221117/DJI_Goggles_2_User_Manual_v1.0_en.pdf), page 36). The goggles therefore contain an orientation sensor. No DJI document says how its data leaves the goggles, apart from the radio link to the aircraft.

## Separate views for each eye

Nothing found so far shows the stock firmware driving the two panels with different pictures:

- **No 3D playback.** The [Goggles 2 release notes](https://www.dji.com/downloads/products/goggles-2) from v01.02 to v01.11 add no 3D or side-by-side mode. A [Heliguy FAQ](https://www.heliguy.com/blogs/knowledge-base/does-dji-goggles-2-support-3d-video-playback/) also answers no. Later releases were not checked. DJI lists 3D playback for Goggles 3, a later model.
- **Virtual Flight sends one view.** The Android app encodes one 1920x1080 H.264 picture for ZV900 and sends the same buffer to the goggles object. The 32-byte video metadata has fragment flags, a counter, a timestamp, and sizes. Its remaining bytes are zero padding, with no eye or layout field. See the [mobile protocol](MOBILE_PROTOCOL.md).

The decoder may still accept a wider or taller picture and route each half to one panel. Only a live test can show this. The [stereo probe](../../tools/research/stereo_probe.py) streams a test pattern through the normal handshake and video packets. Each view shows the same moving gray pattern with a red border for the left view and a blue border for the right view.

| Layout | Encoded size | Purpose |
| --- | --- | --- |
| `sbs` | 1920x1080, two 960x1080 views | Control. Both eyes are expected to show red and blue |
| `fsbs` | 3840x1080, two 1920x1080 views | Full side-by-side |
| `ftb` | 1920x2160, two 1920x1080 views | Full top-bottom |

All three layouts use H.264 High profile, level 5.1, at 60 fps. They encode in real time with NVENC and decode correctly with FFmpeg. Run each layout separately with the goggles in Virtual Flight mode:

```powershell
python tools/research/stereo_probe.py fsbs --seconds 60
```

Close one eye at a time and record the border color that each eye sees, and whether the picture is complete, squeezed, or cropped:

| Observation | Meaning |
| --- | --- |
| Left eye red, right eye blue | The panels can show separate views |
| Both eyes red and blue, squeezed | The decoder scales the whole picture to one view |
| Both eyes red only, or the top half only | The display reads a fixed 1920x1080 region |
| Black, frozen, or disconnected | The decoder rejects that size. Restart the goggles |

## Head orientation over USB

No source shows the goggles reporting orientation to a PC:

- **No orientation traffic.** About 43 minutes of logged desktop streaming, including sessions in which the goggles were worn, contained 11,246 packets from the goggles. All were heartbeat replies, identity and simulator-mode replies, `00/81` advertisements, and the `09/43` status push. The probe prints the same count for each run and marks any new packet type.
- **Virtual Flight does not use it.** The goggles class in the Android app handles heartbeat, firmware version, simulator mode, video, and controller status pushes. The app's strings refer to a controller gimbal wheel but not to goggles orientation.
- **No public command.** The public [DUML dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector/wireshark) names command set 21 `Glass` but lists no commands for it. Its gimbal set has no head-tracking command. The goggles firmware is encrypted with an unpublished key, as noted in [related work](RELATED.md).

Head tracking likely sends gimbal and flight commands from the goggles to the aircraft over the radio link, which a USB host does not see. That is an inference. Finding a request that makes the goggles report orientation over USB would need firmware analysis or an unbounded command search. Unknown commands can change device state, so the bridge does not send them.

## SteamVR

A SteamVR headset driver needs a pose source and a display output. If the goggles cannot provide the pose, an external tracker such as [OpenTrack](https://github.com/opentrack/opentrack) can. Existing drivers such as [OpenVR-OpenTrack](https://github.com/r57zone/OpenVR-OpenTrack) take an OpenTrack pose and draw the headset view in a desktop window, which the bridge can capture. Without separate views, both eyes would see the same picture. This combination has not been tested.
