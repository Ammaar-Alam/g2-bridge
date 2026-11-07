# Artifacts and provenance

These artifacts were acquired and inspected on November 6, 2026. The DJI download endpoints return expiring CDN URLs.

## Android Virtual Flight

The [Android download endpoint](https://service-adhoc.dji.com/download/app/android/cefd8003-3668-4613-81e8-623bbf5f9839) appears in the `dji-virtual-flight` item of [DJI's mobile product-page data](https://www.dji.com/mobile/downloads/products/dji-virtual-flight). It returned the following APK:

| Field | Observed value |
| --- | --- |
| Catalog version | 1.4.0 |
| Filename | `1664350982812-DJI_VIRTUAL_FLIGHT_SHIPPING_142.apk` |
| Manifest package | `com.dji.virtual_flight` |
| Manifest `versionName` / `versionCode` | `1.0` / `1` |
| Bytes | 1,991,573,787 |
| SHA-256 | `e6181ea1f5e1dab39f67713c647d1c175de614019b90252a082fd8f2bd122fc2` |
| Object `Last-Modified` | 2022-09-28 07:44:02 UTC |

REA recorded 180 ZIP central-directory occurrences, 152 graph nodes, and 179 edges, with no reported contradictions. APK signing-block validation was not performed.

JDK `jarsigner` verified the JAR signature but warned about a self-signed certificate, 1,024-bit RSA/SHA1, a missing timestamp, and `JarFile`/`JarInputStream` inconsistencies. This check did not establish a trusted signer identity or validate the full APK signing block. The certificate subject is `CN=Android Debug, O=Android, C=US`, with SHA-256 `ED76702CC1C2C111BA8C5EB4CBAB4C3ADCD5023784548041232A349385E73202`.

The APK contains these ARM32 libraries:

| ARM32 library | Bytes | SHA-256 |
| --- | ---: | --- |
| `libunrealbridge.so` | 54,928 | `4657276ff632719ed65f643c276e6804b9fd67c9f8605d139086cd00d648b145` |
| `libdjisdk_datalink.so` | 1,116,256 | `62fc4cdae1f9085eed390c1a62a708d74ed6bac494c300490d3077755d229501` |
| `libdjisdk_jni.so` | 6,698,764 | `1fb6d165a1aac28ec93a21ffb6ce9fe2d2f459630110b9d0bfb031a51cd95a06` |
| `libUE4.so` | 143,645,900 | `c75d099fa9b7a4962909171808857a51c4ef88a02f21e9ae40c1e05924c66df7` |
| `libc++_shared.so` | See ZIP inventory | `66336f9675f720201d2c314f3d559da20b909fcc3eb8677d3ccbabd135e7f9b9` |

Static analysis used the APK without installing or launching it. JADX processed a subset containing the manifest, resources, and DEX files. That subset is not a signed, installable APK. One unrelated Google `zzf.java` file failed decompilation. The accessory code used in this analysis decompiled successfully.

## Windows Virtual Flight

The [Windows download endpoint](https://service-adhoc.dji.com/download/app/pc/3cf0bf93-8700-4b6d-af16-dbdabe3abd4f) lists version 1.4.0, released August 29, 2022. Analysis used extracted files without running the installer or simulator.

The 3,239,001,413-byte installer is an Advanced Installer self-extracting archive. Its `ADVINSTSFX` footer indexes 48 embedded entries. `FILES.7z` starts at byte 5,507,584 and is 3,082,720,056 bytes long. Its first 512 bytes are XOR-encoded with `0xff`. Checked HTTP range requests retrieved the embedded archive, which was decoded and hashed. The parent installer was only partially downloaded and has no full-file hash.

The extracted artifacts have these sizes and hashes:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Decoded `FILES.7z` | 3,082,720,056 | `56533e27ac57b99a53de30cf75d124d0b6f3709c39433287fc6e2292464677f4` |
| `DFSM-Win64-Shipping.exe` | 81,050,112 | `7a9a7bc2c05a8b2eabd1b83d8b688655b76848355e3f1ff46d28d80572126722` |
| `libusb0_dji.dll` | 83,824 | `23e6ca9418a102976485110cfb11c20aa3c69d0701cd993b782ca97012b01831` |
| `libusb0.dll` | 87,280 | `c24b231889c6c4856eafb9c90b99ae01cbbbe897498be161624d3bd36266a921` |
| `libusb-1.0.dll` | 108,032 | `9a6d52cf0f9cf6df8986c426f452b6655aa3575c181d7167daf9d9552a827cd4` |

See [archive provenance](evidence/windows-archive-provenance.json) and [selected-binary records](evidence/windows-selected-binaries.json). Finding transport SDK code in this executable does not establish official Windows Virtual Flight goggles support.

## DJI Assistant driver

The driver came from [DJI Assistant 2 Consumer Drones Series](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series), version 2.1.42. The installer SHA-256 is `95766b985f38658b3aa8ed7c0b79bada38b9c9571111e55a2f1225349a8c5d33`.

PnPUtil installed the extracted `Drivers_Win10/BULK_DRIVER/bulk_amd64/DEVICE_BULK.inf`, version 5.0.0.7, dated March 27, 2024. The Assistant installer and application were not run. The catalog and SYS file signatures verified as Microsoft Windows Hardware Compatibility Publisher. Windows assigns published INF names per machine, so those names cannot be reused as installation identifiers.

The live backend pins x64 `libusb0_device.dll` to SHA-256 `d2c16bd7c7fb2344408259fd083c8fdbeda3b096b8c9d07e48848e99fc2c3743`. A separate Assistant `DJIService.exe` used in static analysis has SHA-256 `d1087c83b13c9f56685ac65466e276c30be4f87651c51c0eb4ebaa3dce2b4383`.

## Tools used

Analysis used REA 6.7.0, Ghidra 12.1.4, JDK 26.0.2, JADX 1.5.6, Unicorn 2.1.4, Capstone 5.0.6, PyUSB 1.3.1, py7zr 1.1.4, innoextract 1.9, and Python 3.12.13. The JADX release ZIP SHA-256 is `545ea2be9c242511bc145755cf4bda2485ade42966e096f8b4d3da2a230e8974`.

GPU capture used Gyan `ffmpeg-2026-11-05-git-0893feba65-essentials_build`, obtained from FFmpeg's linked distributor. The archive SHA-256 is `9d2c2ca426699e4e0f180341f001d1e4ed95ae3231b160853f24891c15706ccd`. The executable SHA-256 is `a4156224c87b6f2decb59af159360237b4d82b48080bd2b2381c0fb7cd4332d4`. Tests used an RTX 5060 Laptop GPU and NVIDIA driver 610.74. Earlier tests used FFmpeg 7.1 from imageio-ffmpeg 0.6.0.
