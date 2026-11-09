# Goggles 3 probe

The bridge doesn't work with DJI Goggles 3 on the tested firmware. One retail unit answered heartbeat and identity requests, but no module accepted simulator mode, and the goggles displayed no test video. This page lists the reported Goggles 3 USB details, the probe results, and how to run [`probe_goggles.py`](../../tools/research/probe_goggles.py) on other firmware versions or models.

## Reported details

The [Goggles 3 engineering-unit work](https://github.com/ggurov/dji-goggles3-display-unit) describes retail and engineering units over USB. It reports the following values:

| Item | Goggles 2 (tested here) | Goggles 3 (reported) |
| --- | --- | --- |
| Identity | `E3T ZV900` | `E3T ZV902` (`product_type` `e3t_zv902`) |
| VID:PID | `2ca3:0020` | `2ca3:0020` |
| Vendor interfaces | MI03–MI07, `ff/43/01` | MI03–MI07 vendor; DJI Assistant uses MI04, endpoints `04`/`85` |
| System address | `28/1` | `28/1` (`0x1C01`) |
| Processor | E3T | E3T on a Unisoc AArch64 platform |

Retail Goggles 3 units have no ADB, so MI04 is their only host access. The Goggles 3 release notes from v01.00.0100 to v01.00.0900 mention no Virtual Flight or simulator support. The Wireless Streaming feature in v01.00.0200 works with DJI Fly. It appears to share the goggles' view with a phone, not to accept video input.

## What the bridge needs

The bridge needs three things from the goggles. The tested Goggles 3 meets only the first:

- MI04 matches the tested descriptor: class `ff/43/01`, two bulk endpoints, and high-speed 512-byte packets. Goggles 3 matches it.
- The goggles accept simulator mode `0b/1a` from `10/1` to `28/0`. On Goggles 2, the bridge sends this request while the goggles show **More > DJI Virtual Flight**. The tested Goggles 3 has no such menu entry, and no module accepted the request.
- The goggles decode and display V1 `0b/53` video. The tested Goggles 3 displayed nothing, even when the probe sent video without simulator mode.

## Results

On November 8, 2026, the probe ran from Linux over SSH against one retail Goggles 3. Its identity was `E3T ZV902 AC Feb 20 2025|04:26:31`, and it ran firmware 01.00.08.00. Its menu had no Virtual Flight entry. The results were the following:

| Step | Result |
| --- | --- |
| Descriptors | `2ca3:0020`, USB 2.10, high speed. MI04 `ff/43/01` with `0x04/512` and `0x85/512` matches the tested profile |
| Heartbeat and identity | `E3T ZV902 AC Feb 20 2025\|04:26:31` from `28/1`. Heartbeats from `28/0` answered 29 of 29 requests in 15 seconds. `28/5` sent a `00/81` advertisement every second with `ZV902` in the payload, as Goggles 2 does |
| Simulator mode `0b/1a` to `28/0` | No reply after three attempts, and the display didn't change. Heartbeats kept being answered |
| Route scan, after a restart | Identity answered `00` only from `28/1`. `28/0`, `28/2`, `28/3`, `28/4`, and `28/5` answered `e0`, and `28/6` and `28/7` didn't answer. Simulator mode got `e0` from `28/1`, `28/2`, and `28/4` and no reply from `28/0` |
| Forced video, after a restart | 601 test pictures at 30 fps over 20 seconds, with no USB error. Heartbeats kept being answered. No other reply arrived, and the display didn't change |
| **OTG wired connection** turned on, same USB-A-to-USB-C cable to the PC | Byte-identical configuration descriptor, `00/81` advertisements, and route scan replies |

Goggles 2 answers `0b` requests even when it rejects them, with status `e0` or `d6`. On this Goggles 3, `e0` also answers identity requests to modules other than `28/1`, so it probably means that the module doesn't support the request. MI04 accepted video writes without error, but the goggles displayed nothing. On this firmware, the Goggles 2 PC route reaches no video input. Other firmware versions are untested.

## Run the probe

The probe uses the bridge's USB transport, so it runs on Windows, macOS, or Linux. The Goggles 3 results come from Linux. On Linux, install the udev rule first so that libusb can claim MI04 without root:

```bash
sudo cp scripts/linux/60-dji-goggles.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

The rule gives access to a local desktop session through `uaccess` and to members of the `plugdev` group, which also covers SSH sessions. On distributions without `plugdev`, create that group or change the `GROUP` value.

Close DJI Assistant, power on the goggles, and connect a USB data cable. Then run each step separately, and check the output before you go on:

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

If simulator mode gets no reply, run the follow-up checks. To keep an earlier request from affecting the result, restart the goggles before each check:

```bash
# Identity to 28/0-28/7, then simulator mode to each module that answered
.venv/bin/python tools/research/probe_goggles.py --scan
# Test picture without simulator mode; watch the lenses
.venv/bin/python tools/research/probe_goggles.py --force-video --seconds 20
```

## Android phone and OTG wired connection

On Goggles 2, mobile Virtual Flight reverses the PC roles: the goggles are the USB host, and the phone runs in Android Open Accessory (AOA) mode as `DJI / com.dji.logiclink` or `DJI / com.dji.link`. For more information, see the [mobile protocol](MOBILE_PROTOCOL.md). These tests checked whether the Goggles 3 **OTG wired connection** setting gives the same arrangement.

The tests ran over wireless adb, with the goggles plugged into the phone's USB-C port. Each test recorded the phone's USB state, asked the phone's port for the device role, and then restored the original roles:

```bash
# Record the port ID and the current power and data roles
adb shell dumpsys usb
# Ask for the device data role, so that the goggles get the host role
adb shell dumpsys usb set-port-roles PORT_ID source device
# Also ask for a power-role swap, so that the goggles power the phone
adb shell dumpsys usb set-port-roles PORT_ID sink device
# Restore the original roles
adb shell dumpsys usb set-port-roles PORT_ID source host
```

Replace `PORT_ID` with the port ID from the `usb_ports` section of the `dumpsys usb` output. To see why a role switch failed, check `adb logcat` for USB lines.

On November 8, 2026, the same goggles were tested with **OTG wired connection** turned on and a OnePlus CPH2653 running Android 16:

| Test | Result |
| --- | --- |
| Connected | The phone was the host and source (`dfp`, `source`/`host`). The goggles enumerated as `2ca3:0020`, `DJI` / `Goggles3-<serial>`, configuration `rndis,mass_storage,bulk,acm`, with the same eight interfaces as on the PC. No accessory was reported |
| Phone requests `source`/`device` | The phone's USB hardware abstraction layer (HAL) logged `Role switch failed while writing to file` for `data_role`. The port stayed `host` |
| Phone requests `sink`/`device` | The power-role and data-role writes both failed. The port stayed `source`/`host` |
| Restore | The port reported `source`/`host` again, and the goggles stayed enumerated |

The phone port reports that it can change both roles, so the goggles probably rejected the swaps or don't support them. That's an inference, because USB Power Delivery traffic wasn't captured. With **OTG wired connection** turned on, the goggles act as a USB device with the PC interface, not as an AOA host. The mobile Virtual Flight transport therefore isn't available. The Android Virtual Flight app wasn't installed.

## Report results

Include the goggles firmware version, the operating system, the commands that you ran, and the logs. The identity reply can include a build date. The probe doesn't read string descriptors, so its logs contain no serial numbers. On Android, `dumpsys usb` and logcat show the serial in the goggles' product name, for example `Goggles3-SERIAL`. Before you share any logs, remove the serial and check them for other personal information.
