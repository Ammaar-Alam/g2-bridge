# Reproduce the evidence

Run these commands from the repository root and write generated output under the ignored `work/` directory. Acquire vendor binaries separately and verify their [artifact hashes](ARTIFACTS.md).

## Run packet and parser tests

Run the test suite without goggles or a GPU:

```powershell
python -m unittest discover -s tests -v
```

The suite covers native serializer fixtures, fragmentation and counter rollover, CRC validation, control reply matching, descriptor selection, AVI frame boundaries, engine cleanup, and byte preservation across 2 KiB and 16 KiB writes.

The [control-session fixture](evidence/pc-control-session.json) contains selected live request and reply bytes. The [USB fixtures](../../tests/fixtures) include a complete configuration descriptor and both observed link-speed profiles, without device serials or hub paths.

## Packetize a synthetic video frame

The [synthetic H.264 frame](evidence/synthetic-frame.h264) contains one generated `testsrc2` picture with sequence and picture parameter sets (SPS/PPS). Its access unit delimiter (AUD) is removed. The [PC packet file](evidence/synthetic-frame-v1.bin) contains the deterministic V1 packets for that frame. The [frame manifest](evidence/synthetic-frame.json) records the source and hashes.

Generate the packet file with this command:

```powershell
python tools/research/packetize_pc_frame.py --frame docs/research/evidence/synthetic-frame.h264 --output work/research/example-v1.bin
```

This command writes a local packet file. For live streaming, the bridge also identifies the device, handles heartbeats, shares sequence allocation with control requests, and sends successive complete frames.

## Run native ARM emulation

Extract ARM32 `libUE4.so` from the pinned Android APK into `work/native/`. Install the research dependency, then run the emulation harnesses:

```powershell
python -m pip install -r tools/research/requirements.txt
python tools/research/emulate_v1.py --binary work/native/libUE4.so --output work/research/v1-oracle.json
python tools/research/emulate_serializer.py --binary work/native/libUE4.so --output work/research/serializer-oracle.json
python tools/research/emulate_video.py --binary work/native/libUE4.so --output work/research/video-oracle.json
python tools/research/emulate_video_wire.py --binary work/native/libUE4.so --output work/research/video-wire-oracle.json
```

Each command checks the binary hash and refuses to overwrite an existing output file. Compare the `cases` and `binary_sha256` fields with the matching tracked fixture. The full-chain harness also compares native output with `VideoPacketizer` internally. Native code runs inside Unicorn with intercepted memory and clock calls, without an Android process or hardware I/O.

## Export the REA inventory

In a REA 6.7.0-compatible client and server, open the original APK, run `inspect_artifact` and `inventory_artifact`, and export the evidence bundle. The [published inventory](evidence/rea-inventory.json) contains all three records. Six local path fields use `${WORK}`, and source record IDs are stored as `original_evidence_id`.

For tool documentation, see [REA](https://github.com/morluto/rea), [JADX 1.5.6](https://github.com/skylot/jadx/releases/tag/v1.5.6), [Ghidra](https://github.com/NationalSecurityAgency/ghidra), and [Unicorn](https://github.com/unicorn-engine/unicorn).

## Analyze selected functions in Ghidra

The [Java scripts](../../tools/research/ghidra) create and decompile the function ranges in the [target lists](../../tools/research/targets). `FocusedNative` replaces function definitions in those ranges, so use a new analysis project.

Install a compatible JDK and create the project and output directories. Replace `GHIDRA_DIR` with the Ghidra installation directory, then run:

```powershell
$ghidraPath = 'GHIDRA_DIR'
& "$ghidraPath\support\analyzeHeadless.bat" work/research/ghidra g2-arm `
  -import work/native/libUE4.so -noanalysis `
  -scriptPath tools/research/ghidra `
  -postScript FocusedNative.java work/research/arm-protocol.txt tools/research/targets/ue4-targets.tsv `
  -max-cpu 2
```

Additional target files cover constructors, CRC routines, encoder configuration, session initialization, and game callbacks. ARM rows contain the original ELF virtual address, decimal length, ARM/Thumb flag, and symbol. The script adds the import's image base. `FocusedPe.java` accepts a relative virtual address, decimal length, and label, then adds the Portable Executable (PE) image base. PE unwind fragment lengths can cover only part of a function.

For the USB DLL, run normal analysis followed by `InspectTransport.java` to export names matching this expression:

```text
usb_(bulk_write|bulk_setup_async|submit_async|reap_async|reap_async_nocancel|cancel_async|free_async)$
```

Follow the callee addresses in the [native analysis map](NATIVE_ANALYSIS.md) for allocation, waiting, and cancellation details. Check inferred signatures for tail-call exports against their callees before relying on them.

## Benchmark frame release

Replace `FFMPEG_PATH` with the path to `ffmpeg.exe`, then run:

```powershell
python tools/research/benchmark_framing.py --ffmpeg "FFMPEG_PATH" --out-dir work/research/framing-run-1
```

This runs the real NVENC encoder on paced gray and moving testsrc2 sources, without opening USB. A raw-payload tap feeds codec bytes to the Annex-B parser as they arrive, before the AVI packet is complete. This gives both readers the same input timing. Match frame hashes before comparing release times. Use the pinned build when reproducing the original measurements, and record GPU/driver versions. Avoid running this GPU workload during another performance test.

## Compare streams on hardware

Use the [bridge CLI](../../README.md#start-streaming) for live tests. It checks the pinned DLL, MI04 descriptor, high-speed USB connection, ZV900 identity, and simulator-mode acknowledgement. Run one client at a time. See the [transport experiments](EXPERIMENTS.md) for the commands and packet formats already tested.

Change one setting per comparison and use a repeatable moving source. Keep the full log locally. Before publishing excerpts, remove device serials and local paths. A 240 fps recording containing both the reference display and a goggle lens can measure added display delay with finite sampling uncertainty. Controller-to-photon delay additionally includes controller polling, game simulation and rendering. Host queue/send statistics alone cannot supply either measurement.

For the optical test pattern, camera setup, and frame-counting procedure, see [Measure video delay](../LATENCY.md).
