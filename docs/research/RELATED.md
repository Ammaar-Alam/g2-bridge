# Sources and related work

The following sources were inspected on November 6, 2026. Each entry identifies the device or transport it covers:

| Source | Scope |
| --- | --- |
| [DJI Virtual Flight support](https://repair.dji.com/help/content?customId=01700008917&lang=en&paperDocType=ARTICLE&re=US&spaceId=17) | Documents mobile Goggles 2 mode and Android Open Accessory (AOA) transport. The official Windows app excludes goggles support |
| [Goggles 2 specifications](https://www.dji.com/support/product/goggles-2) | Display and playback specifications. Aircraft-link latency figures describe a different video path |
| [Goggles 2 manual](https://dl.djicdn.com/downloads/DJI_Goggles_2/20221117/DJI_Goggles_2_User_Manual_v1.0_en.pdf) | Wireless playback and documented USB-A-to-C Assistant workflow |
| [Virtual Flight downloads](https://www.dji.com/downloads/djiapp/dji-virtual-flight) | Maintenance-ended notice and app downloads. Acquired versions and hashes are in the [artifact records](ARTIFACTS.md) |
| [Android USB accessory](https://developer.android.com/develop/connectivity/usb/accessory), [AOA](https://source.android.com/docs/core/interaction/accessories/aoa) | Mobile USB roles and accessory transport |
| [Windows dual-role USB](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-dual-role-driver-stack-architecture) | Peripheral support depends on the USB controller and drivers |
| [dr00min/o3-usb-decoder](https://github.com/dr00min/o3-usb-decoder), [protocol notes](https://github.com/dr00min/o3-usb-decoder/blob/main/docs/protocol_notes.md) | Goggles 2/O3 video output research. Its MI04 receive observation led to the local interface tests |
| [samuelsadok/dji_protocol](https://github.com/samuelsadok/dji_protocol/blob/master/usb_mobile_protocol.md) | Apple-style role switching and framing on N3 and Mavic Pro |
| [voc-poc input discussion](https://github.com/fpv-wtf/voc-poc/issues/15) | Reported Pi video-input prototype. Model support and measurements were not reproduced here |
| [dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim), [WTFOS](https://github.com/fpv-wtf/wtfos) | Receiver work for older FPV Goggles V1/V2 |
| [Goggles 3 engineering-unit work](https://github.com/ggurov/dji-goggles3-display-unit) | Display work on rooted Goggles 3 engineering units |
| [Cosmostreamer post](https://www.facebook.com/reel/2184285668786152) | Commercial goggles video-out developer: video input works with the Virtual Flight goggles, Goggles 2 and Integra; other models require modified firmware, expected soon |
| [third-eye](https://github.com/wllm-rbnt/third-eye) | Goggles 3 video out on a Raspberry Pi acting as the Android accessory; documents the AOA handshake, LogicLink tunnel and DUML registration the goggles expect from a phone |
| [YStreamer](https://github.com/YLabs-FPV/YStreamer) | Free Raspberry Pi 4 video-out for Goggles 2, Integra, Goggles 3 and N3 as an `18d1:2d00` FunctionFS gadget, plus experimental FPV Goggles V1/V2 video out; GPL-3.0, Rust |
| [dji-firmware-tools ZV900 tests](https://github.com/o-gs/dji-firmware-tools/blob/master/tests/test_dji_imah_fwsig_rebin1.py) | ZV900 firmware tests refer to the unavailable `UFIE-9999-99` key |
| [GogglePlayer](https://goggleplayer.app/) | DLNA video input. The vendor-reported delay exceeds the simulator latency target |
| [Cosmostreamer](https://cosmostreamer.com/products/djigoggles2/), [DigiView](https://github.com/fpv-wtf/fpv_viewer_android), [YStreamer](https://ystreamer.yarosfpv.com/en/docs/) | Video-output projects with transport details |
