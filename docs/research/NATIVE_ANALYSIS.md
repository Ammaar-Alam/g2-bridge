# Native analysis map

Analysis used Ghidra 12.1.4 and JDK 26.0.2. See [artifacts and provenance](ARTIFACTS.md) for binary hashes and acquisition details.

## Android ARM32

The table lists **original ELF virtual addresses (VAs)** in the pinned `libUE4.so`. The saved Ghidra project adds image base `0x10000` to these values. Check the import base when using another project.

| ELF VA | Function or role |
| --- | --- |
| `049f3548` | `UDeviceManager::InitAllDeviceRef`; transport/service selection |
| `049efa28` | `DeviceBaseGlass::InitDevice`; local receive observers |
| `049f1d2c` | ZV900 constructor; control/video destinations |
| `049f0adc` | Pigeon constructor; separate profile |
| `049f0810` | Device `SetSimMode`; four request bytes |
| `049f08b0` | Command-set `SetSimMode`; V1 `0b/1a` |
| `049f52ac` | `GetSimMode`; V1 `0b/1b`, payload `00` |
| `049feb48` | Recovered heartbeat-timer callback; six request bytes |
| `049fdc0c` | Simulator acknowledgement callback |
| `049fec98` | Device-identity callback |
| `049f0094` | Connected-state check before video send |
| `049f0128` | Native video fragmentation, 1276-byte function |
| `049e3924` | V2 session serialization and optional LogicLink, 648 bytes |
| `049f5c74` | V1 serializer, 480 bytes |
| `049f6448` | V2 serializer, 664 bytes |
| `049f4120` / `049f4158` | CRC8 / CRC16 helpers |
| `049b28b4` | Android MediaCodec encoder configuration |
| `04f64a9c` | Game back-buffer callback; ZV900 1920x1080 selection |
| `04f663a0` | Compression callback feeding goggles |

The [target lists](../../tools/research/targets) retain symbol names, sizes and ARM/Thumb state. `FocusedNative.java` removes overlapping definitions in the selected ranges before disassembling and decompiling them. Reproduction uses a fresh analysis project.

The send path also uses these functions:

| Library | ELF VA | Role |
| --- | --- | --- |
| `libunrealbridge.so` | `00008e88` | `GetAsyncIO` service mapping |
| `libunrealbridge.so` | `000077f6` | `ServiceportAsyncIO::Write` |
| `libdjisdk_datalink.so` | `00074788` | `ServicePortFactory::GetServicePort` |
| `libdjisdk_datalink.so` | `0006b8d4` | `AoaServicePort::Impl::SendData` |
| `libc++_shared.so` | Thumb `0003ffa8` | Clock unit confirmation; `clock_gettime(0)` to microseconds |

## Native emulation

The emulators execute selected ARM functions and intercept allocation, memory copy and zeroing, clock, and signed-division calls. Unexpected execution addresses fail. Retained synthetic references prevent unrelated C++ destructors from running. Android, JNI, the dynamic loader, and network and USB calls are not executed.

Each harness has an instruction and time limit:

| Harness | Checked behavior | Budget per case |
| --- | --- | --- |
| `emulate_serializer.py` | V2 bytes for varied routes, flags, payloads | 3 million instructions / 5 s |
| `emulate_v1.py` | V1 request/response serializer bytes | 3 million instructions / 5 s |
| `emulate_video.py` | Fragmentation and counter rollover for 1, 65,404, 65,405, and 130,809-byte inputs | 1 million instructions / 5 s |
| `emulate_video_wire.py` | Complete send path through intercepted AsyncIO, with raw and wrapped 200-byte and 130,809-byte inputs | 20 million instructions / 20 s |

The full-chain harness checks the Python implementation byte-for-byte before writing its result. Each harness checks the binary hash against the pinned artifact. Their outputs correspond to the [native emulation fixtures](../../tests/fixtures).

## Windows simulator

`DFSM-Win64-Shipping.exe` uses image base `0x140000000`. The table lists **relative virtual addresses (RVAs)**, which must be added to that base. Portable Executable (PE) unwind entries can describe function fragments rather than whole functions.

| RVA | Observation |
| --- | --- |
| `03004dd0` | Exported `GetAsyncIO`: service 1 maps to core 2 / `Win32UsbServicePort`; service 7 maps to core 3 |
| `00b04150` | Application initialization requests service 1 for goggles/common devices |
| `00783690` | USB profile: PID `0020`, interface 4, IN85, OUT04 |
| `035341e0` | USB enumeration, interface claim, and asynchronous endpoint setup, including a fixed USB location check |
| `03533f10` | Copies outgoing data into a 2048-byte task and queues it; no LogicLink prefix here |
| `035355c0` | Asynchronous submit/reap writer, 150 ms timeout and bounded retries |
| `030065e0` | `ServiceportAsyncIO::Write` forwarding |
| `00aff100` | ZV900 destinations and initial LogicLink flag |
| `00b07d80` | V1 `0b/1a` request with `01010000` |

The fixed comparison string at data RVA `043a0a50` is `USB0000.0014.0000.005.000.000.000.000.000`. This check may restrict which PC connections the build accepts. RVA `00b083f0` is a timer worker. A constant search in `00afd000..00b10000` did not find the mobile video-fragment limit. The rest of the executable was not searched for that constant.

## DJI USB DLL and Assistant

The bridge uses the x64 `libusb0_device.dll` from Assistant and verifies its hash before loading it. The simulator ships different USB DLLs.

DJI extends `usb_device` with an extra 512-byte `location` array after its 512-byte `filename`. With 64-bit pointers and packed fields, the device descriptor starts at offset 1,048 and the structure is 1,092 bytes. Unmodified PyUSB's libusb0 structure was incompatible. The backend uses the adapted application binary interface (ABI) for these functions:

| x64 DLL VA | Observation |
| --- | --- |
| `1800047a8` | Exported `usb_bulk_write`, calls the synchronous helper |
| `1800046cc` | Creates context, submits, waits and frees; chunks requests above 65,536 bytes |
| `1800049b0` | Asynchronous bulk setup: 80-byte context and Windows event |
| `180004410` | Asynchronous submit: event reset and overlapped `DeviceIoControl` |
| `180004524` | Wait/reap helper |
| `180004674` | Close event and free context |
| `1800056d0` | Endpoint cancellation helper, unused by the bridge |

Both 2 KiB and 16 KiB bridge writes displayed video correctly. These API write sizes are independent of the USB endpoint's 512-byte maximum packet size. Reusing asynchronous contexts could avoid repeated allocation, but cancellation behavior and buffer lifetime need verification before implementation.

In Assistant's separate `DJIService.exe`, VA `00754870` (`DJIUSBDeviceIO::writeData`) uses 2,048-byte tasks. VA `00752ff0` submits and reaps them asynchronously. This task size was the basis for the initial segmentation experiment.
