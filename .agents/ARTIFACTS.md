# Acquire and identify artifacts

Checked November 6, 2026. No DJI executable, firmware image, or USB capture is included in this repository.

## Original Virtual Flight Android package

Use the [official DJI Android download entrypoint](https://service-adhoc.dji.com/download/app/android/cefd8003-3668-4613-81e8-623bbf5f9839). This link was found in the exact `dji-virtual-flight` object in [DJI's mobile product-page data](https://www.dji.com/mobile/downloads/products/dji-virtual-flight). Do not substitute a similarly named DJI Store simulator or a global-navigation download.

The initial retrieval observed these values:

| Field | Observation |
| --- | --- |
| Catalog version | 1.4.0 |
| Catalog Android requirement | Android 9.0 or later |
| APK filename | `1664350982812-DJI_VIRTUAL_FLIGHT_SHIPPING_142.apk` |
| Object size | 1,991,573,787 bytes, about 1.99 GB |
| HEAD status | HTTP 200 using the fresh signed target |
| Last-Modified | September 28, 2022, 07:44:02 UTC |
| ETag | `791F3CB3BD931E5DEE39BAD563BA2083-52` |
| Internal version, package ID, SHA-256, signer | Not inspected |

The launcher returns an expiring URL on `terra-2-g.djicdn.com`. The observed object path was `/a81c919a2cba4e93a2147801711c04d1/1664350982812-DJI_VIRTUAL_FLIGHT_SHIPPING_142.apk`. Requesting the unsigned object returned HTTP 403. Revisit the stable entrypoint instead of reusing a stale signature.

The catalog's `1.4.0` and filename's `142` are different observations. Inspect the actual manifest before assigning a version. The multipart ETag is not a SHA-256 checksum or signing verification.

To prepare the artifact:

1. Download the original package into ignored `work/` and retain its source and retrieval time. A suggested local filename is `work/dji-virtual-flight.apk`.
2. Record its byte count and SHA-256. On Windows, after saving that file, use `Get-FileHash .\work\dji-virtual-flight.apk -Algorithm SHA256`.
3. Verify package signing with an available Android signing tool and record what was checked. A valid signature alone does not establish an independently trusted DJI signer.
4. Read the manifest for the real package ID, version, permissions, USB declarations, and native library inventory.
5. Preserve original bytes. Place derived extractions and REA evidence in separate subdirectories of `work/` with a link to the original hash.

No Android phone is required for static analysis. The owner has an iPhone. If a user-owned Android installation later becomes available, discover its package ID and base/split APK paths instead of guessing them.

## iPhone reference

The [DJI Virtual Flight App Store listing](https://apps.apple.com/gb/app/dji-virtual-flight/id1541992396) is a source for app identity and release history. Installation availability in the owner's region and operation on their iPhone are unverified.

Use the phone first to establish a working visible baseline through DJI's documented connection. No iOS app binary has been acquired. Do not assume an App Store executable is unencrypted or that Ghidra can recover a usable binary merely from the store link.

## Firmware and captures

No firmware package has been selected. Inspect the mobile app first; obtain firmware only when a precise question cannot be answered from that app and the stock interfaces.

For any later capture, record both connected devices, firmware/app versions, cable topology, capture location, direction, time range, and known actions. A PC capture covers traffic involving that PC; it does not passively observe a separate iPhone-to-goggles cable. Decide whether application-level instrumentation or a bridge is needed only after static analysis identifies the missing evidence.

## Repository boundary

Keep APKs, IPAs, firmware, full decompiled trees, signed download URLs, raw device logs, captures, and analysis databases out of Git. They can be large, proprietary, or contain device/account information. Commit original implementation work and concise, redacted findings with provenance. Review third-party licenses before reusing code; a research link is not a license grant.
