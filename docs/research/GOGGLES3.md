# Goggles 3 probe

The bridge doesn't support DJI Goggles 3 yet. This page lists what other projects report about the model, what the bridge would need, and how to check it on hardware with [`probe_goggles.py`](../../tools/research/probe_goggles.py). No Goggles 3 hardware has been tested with this repository.

## What is known

The [Goggles 3 engineering-unit work](https://github.com/ggurov/dji-goggles3-display-unit) describes retail and engineering units over USB. It reports these values:

| Item | Goggles 2 (tested here) | Goggles 3 (reported) |
| --- | --- | --- |
| Identity | `E3T ZV900` | `E3T ZV902` (`product_type` `e3t_zv902`) |
| VID:PID | `2ca3:0020` | `2ca3:0020` |
| Vendor interfaces | MI03–MI07, `ff/43/01` | MI03–MI07 vendor; DJI Assistant uses MI04, endpoints `04`/`85` |
| System address | `28/1` | `28/1` (`0x1C01`) |
| Processor | E3T | E3T on a Unisoc AArch64 platform |

Retail Goggles 3 units have no ADB, so MI04 is their only host access. The Goggles 3 release notes from v01.00.0100 to v01.00.0900 mention no Virtual Flight or simulator support. The Wireless Streaming feature added in v01.00.0200 works with DJI Fly and appears to share the goggles' view with a phone, not to accept video input.

## What remains unknown

The bridge needs three things that haven't been checked on Goggles 3:

- MI04 must match the tested descriptor: class `ff/43/01`, two bulk endpoints, and high-speed 512-byte packets. A SuperSpeed link would report 1024-byte packets. The bridge rejects that size unless `allow_superspeed` is set.
- The goggles must accept simulator mode `0b/1a` from `10/1` to `28/0`. On Goggles 2, the bridge sends it while the goggles show **More > DJI Virtual Flight**. The tested Goggles 3 menu has no such entry.
- After that, the goggles must decode and display V1 `0b/53` video.

## Run the probe

The probe runs on Windows, macOS, or Linux. On Linux, install the udev rule first so libusb can claim MI04 without root:

```bash
sudo cp scripts/linux/60-dji-goggles.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

The rule grants access to a local desktop session through `uaccess` and to members of the `plugdev` group, which also covers SSH sessions. Distributions without `plugdev` need that group or a different `GROUP` value.

Close DJI Assistant, power on the goggles, and connect a USB data cable. Then run each step separately and check the output before you go on:

```bash
# Step 1: descriptors only
.venv/bin/python tools/research/probe_goggles.py --descriptors-only
# Step 2: heartbeats and identity, display mode unchanged
.venv/bin/python tools/research/probe_goggles.py
# Step 3: also send simulator mode 0b/1a
.venv/bin/python tools/research/probe_goggles.py --simulator
# Step 4: also send the synthetic test picture at 30 fps for 20 seconds
.venv/bin/python tools/research/probe_goggles.py --simulator --test-video --seconds 20
```

Each run writes a new JSON Lines log to `work/probe/`. The log holds descriptors, the bytes sent and received, decoded packet fields, state changes, and a final `result` row. Step 2 stops in the `identified` state and keeps sending heartbeats. Step 3 reports the status byte from the goggles: `00` means success, and any other value means a rejection. Step 4 sends the [synthetic test frame](evidence/synthetic-frame.h264), a static `testsrc2` picture. Watch the lenses for it.

If step 1 reports a SuperSpeed link, try a USB 2.0 port or cable first. Add `--allow-superspeed` only to collect evidence from that link.

If simulator mode gets no reply, run the follow-up checks. Each needs the goggles restarted first, so that the earlier request can't affect the result:

```bash
# Identity to 28/0-28/7, then simulator mode to each module that answered
.venv/bin/python tools/research/probe_goggles.py --scan
# Test picture without simulator mode; watch the lenses
.venv/bin/python tools/research/probe_goggles.py --force-video --seconds 20
```

## Results

On November 8, 2026, one retail Goggles 3 was probed from Linux over SSH. Its owner had not installed the latest firmware, and the menu had no Virtual Flight entry. The results were:

| Step | Result |
| --- | --- |
| Descriptors | `2ca3:0020`, USB 2.10, high speed. MI04 `ff/43/01` with `0x04/512` and `0x85/512` matches the tested profile |
| Heartbeat and identity | `E3T ZV902 AC Feb 20 2025\|04:26:31` from `28/1`. Heartbeats from `28/0` answered 29 of 29 requests in 15 s. `28/5` sent a `00/81` advertisement every second with `ZV902` in the payload, as Goggles 2 does |
| Simulator mode `0b/1a` to `28/0` | No reply after three attempts, and the display didn't change. Heartbeats kept being answered |
| Route scan, after a restart | Identity answered `00` only from `28/1`. `28/0`, `28/2`, `28/3`, `28/4` and `28/5` answered `e0`, and `28/6` and `28/7` didn't answer. Simulator mode got `e0` from `28/1`, `28/2` and `28/4` and no reply from `28/0` |
| Forced video, after a restart | 601 test pictures at 30 fps over 20 s, with no USB error. Heartbeats kept being answered. No other reply arrived, and the display didn't change |
| OTG wired connection enabled, same USB-A-to-USB-C cable to the PC | Byte-identical configuration descriptor, `00/81` advertisements, and route scan replies |

Goggles 2 answers `0b` requests even when it rejects them, with status `e0` or `d6`. On this Goggles 3, `e0` also answers identity requests to modules other than `28/1`, so it probably means that the module doesn't support the request. No module accepted simulator mode. MI04 accepted video writes without error, but the goggles displayed nothing. On this firmware, the Goggles 2 PC route reaches no video input. Other firmware versions remain untested.

## Android phone and OTG wired connection

On Goggles 2, mobile Virtual Flight reverses the PC roles: the goggles are the USB host, and the phone runs in Android Open Accessory (AOA) mode as `DJI / com.dji.logiclink` or `DJI / com.dji.link`. See the [mobile protocol](MOBILE_PROTOCOL.md). These tests checked whether the Goggles 3 **OTG wired connection** setting gives the same arrangement.

[`android_accessory_probe.sh`](../../tools/research/android_accessory_probe.sh) runs over wireless adb while the goggles are plugged into the phone's USB-C port. It records the phone's USB state, asks the phone's port for the device role, records the state after a hold period, and then restores the original roles. Logcat is filtered to USB, role, and accessory lines. The goggles' product name contains the unit serial, and the script redacts it.

```bash
# With the goggles plugged into the phone; LABEL names work/android/<time>-LABEL
tools/research/android_accessory_probe.sh otg-on
# Also ask for a power-role swap, so the goggles would power the phone
tools/research/android_accessory_probe.sh otg-on-sink 20 sink
```

On November 8, 2026, the same goggles were tested with **OTG wired connection** enabled and a OnePlus CPH2653 running Android 16:

| Test | Result |
| --- | --- |
| Connected | The phone was the host and source (`dfp`, `source`/`host`). The goggles enumerated as `2ca3:0020`, `DJI` / `Goggles3-<serial>`, configuration `rndis,mass_storage,bulk,acm`, with the same eight interfaces as on the PC. No accessory was reported |
| Phone requests `source`/`device` | The phone's USB HAL logged `Role switch failed while writing to file` for `data_role`. The port stayed `host` |
| Phone requests `sink`/`device` | The power-role and data-role writes both failed. The port stayed `source`/`host` |
| Restore | The port reported `source`/`host` again, and the goggles stayed enumerated |

The phone port reports that it can change both roles, so the goggles probably rejected the swaps or don't support them. That is an inference, because USB Power Delivery traffic was not captured. In OTG wired connection, the goggles act as a USB device with the PC interface, not as an AOA host. The mobile Virtual Flight transport therefore isn't available, and the Android Virtual Flight app wasn't installed.

## Report results

Include the goggles firmware version, the operating system, the commands you ran, and the logs. The identity reply can include a build date. The probe reads descriptors without string descriptors, so its logs contain no serial numbers. On Android, `dumpsys usb` includes the serial in the goggles' product name. The Android script redacts it, but check its output anyway. Check the logs for personal information before sharing them.
