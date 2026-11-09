# FPV Goggles V2 and V1 over the PC USB route

The DJI FPV Goggles V2 (2021) and the original Digital FPV Goggles V1 (2019) are a different platform from Goggles 2. This page collects what is known, what the bridge prepares for them, the steps to test a pair, and the results from a Goggles V2 on firmware 01.07.0000. Every statement names its source.

## What is known

| Fact | Source |
| --- | --- |
| The Virtual Flight app has a second device profile, codename **Pigeon**, which encodes **1440x810** and sends video to DUML type **14** (HD transmission, ground side) ID 1, index `0701`, without the LogicLink wrapper. ZV900 (Goggles 2) uses type 28 ID 1 at 1920x1080 | Static analysis of the Android app, [mobile protocol](MOBILE_PROTOCOL.md) |
| The FPV Goggles V2 panels are 1440x810, and DJI's Virtual Flight app connects to them over USB | DJI product pages; the Pigeon profile matches no other DJI goggles |
| The V2 enumerates as USB `2ca3:001f`. Its interface 3 (`MI_03`, bulk OUT `0x03`, IN `0x84`) carries video **out** when sent the magic `RMVT` | [Evols/dji-goggles-bridge PROTOCOL.md](https://github.com/Evols/dji-goggles-bridge/blob/main/PROTOCOL.md), [fpv-wtf/voc-poc](https://github.com/fpv-wtf/voc-poc) |
| DJI's bulk USB driver, installed by DJI Assistant 2, claims `USB\VID_2CA3&PID_001F&MI_04`, so the V2's interface 4 is a DJI bulk interface that the already-installed driver binds, like `MI_04` on Goggles 2 | The driver INF on a PC with DJI Assistant 2 (`oem27.inf`, driver 5.0.0.1 dated January 2, 2024) |
| Command set 11 is "Simulator" in DUML; `0b/1a` is simulator mode and `0b/53` is video | [DJI firmware tools dissector](https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dissector/wireshark/dji-dumlv1-proto.lua) |
| Goggles V1 share the panels and platform with V2, and DJI added DJI FPV drone compatibility to V1 in 2021 | DJI release notes. Virtual Flight on V1 is not confirmed |
| For **rooted** V1 and V2, [WTFOS](https://github.com/fpv-wtf/wtfos) and [dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim) already stream a PC to the goggles with Moonlight, reporting 7 to 14 ms latency at 120 Hz | fpv.wtf READMEs |

Unknown until a pair is probed: the identity string the V2 returns to `00/ff`, which DUML type answers heartbeats and simulator mode (28 as on Goggles 2, or 14), whether the PC route accepts V1-fragmented video like Goggles 2 or needs the app's V2 envelope, the per-frame size limit, and the endpoint addresses of interface 4.

## What the bridge prepares

- `goggles_bridge/models.py` holds a **DJI FPV Goggles V2** profile (and a V1 twin): 1440x810, video to 14/1, control at 28/0 by default. Neither has an identity code yet, so they are selected with `--assume-model` or the app's **Advanced > Goggles** setting. When a V2 identity is known, its code goes into the table and detection becomes automatic.
- The USB transport accepts product `001f`, reads the bulk endpoint addresses from the descriptor instead of assuming `0x04`/`0x85`, and still claims interface 4 by default (`--interface` overrides it).
- The encoder and the test picture follow the profile's size, and the packetizer follows its video destination. `--control-type 14` moves heartbeat, identity and simulator mode to type 14 if type 28 does not answer.
- The probe can send the picture as PC-route V1 packets (default) or as the app's V2 envelope (`--video-format v2`), scan both types 28 and 14, and records every reply.

## Test plan

Run these on Windows with DJI Assistant 2 installed and closed, from the repository root with the dependencies installed. Each command writes a log under `work/probe/`. Keep the goggles on their normal menu first; if a step gets no simulator reply, look for any menu item about connecting a phone or Virtual Flight and repeat.

1. **Descriptors only.** Confirms the product ID, lists the vendor interfaces, and shows which one the bridge would claim.

   ```powershell
   python tools/research/probe_goggles.py --descriptors-only
   ```

   Expect `2ca3:001f` and an `MI04` line with class `ff/43/01` and two bulk endpoints. If `MI04` is missing but another `ff/43/01` interface exists, pass `--interface N` to the later steps.

2. **Identity, read-only.** Heartbeats and the identity request, with the firmware manifest read.

   ```powershell
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2"
   ```

   The identity line is the most valuable result; please report it exactly (it contains no serial). If the heartbeat itself times out ("Control handshake timed out"), repeat with `--control-type 14`.

3. **Route scan.** Which modules on types 28 and 14 answer identity, and which accept simulator mode.

   ```powershell
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2" --scan
   ```

4. **Simulator mode and the test picture.** A 1440x810 pattern at 30 fps. Watch the lenses.

   ```powershell
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2" --simulator --test-video
   ```

   If simulator mode is acknowledged but the lenses stay black, try in turn, power-cycling the goggles between attempts:

   ```powershell
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2" --simulator --test-video --video-format v2
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2" --force-video
   python tools/research/probe_goggles.py --assume-model "DJI FPV Goggles V2" --control-type 14 --simulator --test-video
   ```

5. **The desktop.** Once the pattern shows, stream for real:

   ```powershell
   python scripts/stream_desktop.py --assume-model "DJI FPV Goggles V2"
   ```

   In the Windows app, pick **DJI FPV Goggles V2 (untested)** under **Advanced settings > Goggles**.

The test picture is 37 KB, under the Goggles 2 frame limit. A frame too large for the receiver can leave the goggles black until power-cycled, as on Goggles 2; if that happens, note which step did it.

## Results on a Goggles V2, November 8, 2026

Hardware: a DJI FPV Goggles V2 freshly updated to firmware 01.07.0000, in O3 air-unit mode, with no air unit powered. Windows 11 PC with DJI Assistant 2 installed but closed. USB-C data cable.

### USB

Windows shows `2ca3:001f` as a composite device: `MI_00` RNDIS, `MI_02` mass storage, **`MI_03` "Vision (Interface 3)"** (class `ff/43/01`, bulk out `0x03`, in `0x84`, 512-byte packets) bound to libusb-win32 from an earlier video-out tool, and **`MI_04` "DEVICE USB Virtual COM" (COM10)**, a CDC serial port (class `02/02/01` with its data interface `MI_05`). DJI's `oem27.inf` entry for `PID_001F&MI_04` is therefore its virtual COM driver, not a bulk driver. DJI's `libusb0_device.dll` enumerates none of these interfaces, and `DJIService.exe` holds the COM port while DJI Assistant runs.

### Control over the COM port

With `--serial`, the probe reached every control step over COM10 using the Goggles 2 routes, with the goggles on their normal screen:

| Request | Result |
| --- | --- |
| Heartbeat `00/00` to 28/0 | Answered |
| Identity `00/ff` to 28/1 | **`WM170 PIGEON GLS Mar 21 2023\|20:20:34`** |
| Firmware manifest `00/4f` to 28/5 | 01.07.0000: `GLS_CPLD` 03.00.01.34, `GL170_PIGEON` 10.05.20.64 |
| Route scan | Identity answered by 28/1 and 14/0 (status `00`), `e0` from 28/0, 28/2–28/5; simulator mode accepted only by 28/0 |
| Simulator mode `0b/1a` to 28/0 | **Accepted (status `00`)** without any menu step. The lenses went black and stayed black until a power cycle |
| Heartbeat to 14/0 (`--control-type 14`) | No reply |

`PIGEON` and `GL170` are now identity codes of the V2 profile, so detection is automatic.

### Video

No variant displayed anything. Each ran after a successful simulator-mode reply.

| Transport | Packets | Rate | Frames | Outcome |
| --- | --- | --- | --- | --- |
| COM10 | V1 (978-byte chunks) to 14/1 | 30 fps | 450 | Accepted, no picture |
| COM10 | V1 to 28/1 | 30 fps | 1 | Port stalled (write timeout) after one frame |
| COM10 | V1 to 14/1 from sender 2/0 | 30 fps | 360 | Accepted, no picture |
| COM10 | App V2 envelope to 14/1 | 30 fps | 13 | Heartbeats lost: the port was saturated |
| COM10 | App V2 envelope to 14/1, 28/1, 14/0 | 5 fps | 50 each | Accepted, no picture |
| Bulk interface 3 (libusb-win32 x64 DLL) | heartbeat, `RMVT`, V1, V2 | | 0 | Every bulk write and read timed out, before and after simulator mode; control transfers through the same handle worked |

The COM port cannot carry a stream in any case: 37 KB frames at 30 fps already saturate it.

### Air Unit / Vista mode

With the goggles switched to the Air Unit / Vista transmission mode and rebooted, the identity became **`WM150 PIGEON GLS`** (the original Digital FPV system; `WM170` is the DJI FPV drone system) and simulator mode `0b/1a` was **rejected with `e0`**. Virtual Flight therefore exists only in O3 mode. In this mode bulk interface 3 accepted one 19-byte write and then stalled again; reads still timed out.

### Unsolicited traffic and the network link

Over the COM port the V2 pushes, without requesting acknowledgement: `09/43` from 14/0 (payload `03`) twice a second, `00/81` from 28/5 (an advertisement naming `GL170`) once a second, and `06/1e` from 28/0 once a second with a 52-byte payload that is zero apart from a changing 16-bit counter. Nothing in them asks the PC for a reply.

The goggles also run a network over their RNDIS interface and hand the PC an address by DHCP; the goggles answer at 192.168.42.5 with DJI Assistant's FTP service and a block of TCP service ports. None of those ports answered a DUML heartbeat. They were not explored further.

### Conclusion

Over the PC-side USB connection, in the only mode that has Virtual Flight, the V2 accepts the control commands but exposes no interface that takes video. Interface 3 behaves as the video-out channel described by the fpv.wtf tools, idle without an air unit. In the phone setup the goggles are the USB host and the phone is an Android Open Accessory, so the video enters through the goggles' host role, which a Windows PC cannot present. The remaining options are a Linux device with USB gadget support acting as the accessory (the "Pi video-input prototype" discussed in [voc-poc issue 15](https://github.com/fpv-wtf/voc-poc/issues/15)), or root with [WTFOS](https://github.com/fpv-wtf/wtfos) and [dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim). The bridge keeps the V2 profile, the serial transport and the probe options so either path can build on them.

Logs of every run are in the owner's `work/probe/`; they contain the identity line and no serial numbers.

## Report

Please share the identity line, the firmware manifest output if it was read, the `work/probe/*.jsonl` logs (they contain no serials), and which steps showed a picture. Open an issue or a pull request; the next change is adding the identity code to `models.py`.
