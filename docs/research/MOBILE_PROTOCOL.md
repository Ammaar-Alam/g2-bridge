# Mobile protocol and native send chain

The Android application sends V2 video packets. The Windows bridge uses a [V1 adaptation](../PROTOCOL.md) of the same video metadata.

ARM addresses on this page are original ELF virtual addresses (VAs) in the `libUE4.so` identified by the [artifact hashes](ARTIFACTS.md). The saved Ghidra import adds image base `0x10000` to these addresses. File offsets are separate values.

## Entry points and routing

The send path follows these calls:

1. `GameActivity.InitSDKManager_Java` registers `WM170` and `LinkDevice` using `AppType.MIMO`. Accessory identities include `DJI / com.dji.logiclink` and `DJI / com.dji.link`.
2. `DJIUsbAccessoryReceiver` calls `UsbManager.openAccessory`. The descriptor reaches `JNIUsbAccessory.native_OnUsbConnected(fd, model)`.
3. `UDeviceManager::InitAllDeviceRef` (`049f3548`) normally selects unrealbridge service type 4. `libunrealbridge.so` `GetAsyncIO` (`00008e88`) maps this to core service type 5. `libdjisdk_datalink.so` `ServicePortFactory::GetServicePort` (`00074788`) constructs `AoaServicePort` for type 5.
4. The conditional RM510 branch selects TCP service type 2 and `127.0.0.1:40007`. The address refers to the controller. This branch does not establish a goggles RNDIS video service.
5. `DeviceBaseGlass::SendLiveVideoStream` (`049f0094`) checks connected state 1 and a video command object, then calls `V2SimCommandSet::SendVideo` (`049f0128`).
6. `CommandSession::SendV2Packet` (`049e3924`) serializes V2 and optionally wraps LogicLink. Unrealbridge `ServiceportAsyncIO::Write` (`000077f6`) forwards the bytes. Datalink `AoaServicePort::Impl::SendData` (`0006b8d4`) queues them without adding the video metadata below.

The device constructors set these initial values. Destination types and indices are hexadecimal:

| Constructor | ELF VA | Video destination type/ID/index | Initial LogicLink flag |
| --- | --- | --- | --- |
| ZV900 | `049f1d2c` | `1c / 1 / 0900` | true |
| Pigeon | `049f0adc` | `0e / 1 / 0701` | false |

Callbacks can change the shared session's LogicLink setting after construction. The Pigeon profile was inspected statically and has not been tested on hardware.

## DUML V1

The V1 serializer at `049f5c74` is 480 bytes long. It writes multibyte fields in little-endian order:

| Offset | Bytes | Field |
| --- | ---: | --- |
| 0 | 1 | `55` |
| 1 | 2 | Total length in low 10 bits; version 1 in upper bits |
| 3 | 1 | CRC8 of bytes 0..2 |
| 4 | 1 | Sender type in bits 0..4; ID in bits 5..7 |
| 5 | 1 | Receiver type in bits 0..4; ID in bits 5..7 |
| 6 | 2 | Sequence |
| 8 | 1 | Response bit 7; ACK bits 5..6; remaining bits zero for these packets |
| 9 | 1 | Command set |
| 10 | 1 | Command ID |
| 11 | variable | Payload |
| end-2 | 2 | CRC16 of preceding bytes |

The maximum packet length is 1,023 bytes, including 13 bytes of overhead. Native emulation fixtures cover heartbeat, identity, and simulator-mode requests, plus a response. The PC sender is type 10, ID 1. The mobile sender is type 2, ID 0. Using the mobile return address on the PC interface did not produce matching replies in the recorded test.

## DUML V2

The V2 serializer at `049f6448` is 664 bytes long and writes this layout:

| Offset | Bytes | Field |
| --- | ---: | --- |
| 0 | 3 | `55 18 08` |
| 3 | 2 | Total length including checksums |
| 5 | 2 | `(ack & 7) << 5` |
| 7 | 4 | Sequence |
| 11 | 4 | Sender: `(type << 16) \| (id << 8)` |
| 15 | 2 | Sender index |
| 17 | 4 | Receiver: `(type << 16) \| (id << 8)` |
| 21 | 2 | Receiver index |
| 23 | 1 | CRC8 of bytes 0..22 |
| 24 | 1 | Command set |
| 25 | 2 | Command ID, sourced from one byte in this implementation |
| 27 | variable | Payload |
| end-2 | 2 | CRC16 of preceding bytes |

V2 adds 29 bytes of overhead. CRC8 uses seed `0x77` and reflected polynomial `0x8c`. CRC16 uses seed `0x3692` and reflected polynomial `0x8408`, with no final XOR. Generated tables matched the binary at `04026093` and `04026194`. The CRC16 seed pointer resolves through `088a123c` to `088e71e0`.

Native V1 and V2 use separate sequence storage. V1 has a 16-bit counter at `0892a7ac`, referenced through global offset table (GOT) entry `088a1158`. V2 has a 32-bit counter at `0892a7b0`, referenced through GOT entry `088a115c`. V2 assigns that counter except for ACK value 2. See the [sequence-storage records](evidence/sequence-storage.json). The Windows adaptation puts both control and video into V1 and therefore shares its V1 allocator, skipping outstanding control sequences.

## LogicLink

LogicLink adds an optional eight-byte prefix: little-endian `<HHI>` containing magic `0xcc55`, a channel, and the inner packet length. The video channel is `0x574a`, and the command channel is `0x5749`. Wrapped video starts with `55 cc 4a 57`. The prefix has no checksum, and its channel values are separate from USB endpoint numbers.

## Video metadata

`SendVideo` (`049f0128`, 1,276 bytes) splits an encoder output buffer into chunks of at most 65,404 bytes. Each chunk receives this 32-byte prefix:

| Offset | Bytes | Field |
| --- | ---: | --- |
| 0 | 1 | Zero |
| 1 | 1 | Complete buffer needs multiple fragments |
| 2 | 1 | Last fragment |
| 3 | 1 | Zero |
| 4 | 4 | Global fragment counter, incremented per fragment |
| 8 | 8 | Truncated/sign-extended timestamp |
| 16 | 4 | Metadata size, 32 |
| 20 | 4 | Encoded bytes in this chunk |
| 24 | 1 | First fragment |
| 25 | 7 | Zero |

V2 video uses command `0b/53`, ACK 3, sender type 2/id 0/index `0101`. The ZV900 destination is type 28/id 1/index `0900`. The maximum inner video packet is 65,465 bytes, or 65,473 bytes with LogicLink. The PC V1 route reduces encoded chunks to 978 bytes while retaining this metadata structure.

The timestamp samples `std::__ndk1::chrono::system_clock::now` per fragment. Runtime-library Thumb VA `0003ffa8` calls `clock_gettime(0)` and produces microseconds. The send routine divides by 1000, retains the low 32 bits and sign-extends to 64 bits. Controlled time `1794000000123` ms yields `7b 94 bb b2 ff ff ff ff`. Static analysis and native emulation confirmed this truncation.

## Encoder and startup

`AndroidCoder::CopySurfaceDataToH264` (`049b28b4`) calls NDK MediaCodec with `video/avc`, color format `0x15`, 10,485,760 bits/s, a frame rate of 60 fps, and a three-second I-frame interval. The render callback `UDjiDFSMGameInstance::OnBackBufferReady_RenderThread` (`04f64a9c`) passes 1920x1080 for ZV900, 1440x810 for Pigeon. `OnFinishCompress` (`04f663a0`) forwards the encoded output. Saved codec-configuration bytes are prepended to keyframes. The similarly named `FDjiMultiForH264::OnFinishCompress` is not this callback.

`DeviceBaseGlass::SetSimMode` (`049f0810`) builds `01 01 00 00`, which `SimCommandSet::SetSimMode` (`049f08b0`) sends as V1 `0b/1a`. `InitDevice` registers local observers for `0b/51` and `0b/52`. The traced callbacks update local remote-controller state and log notifications. `SetEnableGlass` is a local boolean. Those routines did not reveal another receiver initialization command.
