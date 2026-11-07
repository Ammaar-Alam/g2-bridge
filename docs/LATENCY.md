# Measure video delay

Film the monitor and one goggle lens together to measure how far the goggles trail the monitor. At 240 fps, each camera frame spans about 4.17 ms. This measures the difference between the two displays, including their scanout and pixel response. It does not measure controller-to-photon latency.

A 240 Hz monitor and a 240 fps camera have separate clocks. Measure the visible changes in the recording. Do not add or subtract a monitor refresh period from the result.

## Start the pattern

1. Start the bridge from the repository root:

   ```powershell
   python scripts/stream_desktop.py
   ```

2. In a second terminal, open the test pattern:

   ```powershell
   python scripts/latency_pattern.py
   ```

   The command uses FFplay from the FFmpeg installation. If it isn't on your path, pass `--ffplay "FFPLAY_PATH"`, replacing `FFPLAY_PATH` with the path to `ffplay.exe`.

3. Place the pattern window on the display that the bridge captures. Confirm that its center square changes between black and white on both displays.

The square changes every 0.65 seconds over a moving background. The corner counter is not needed. Press **Escape** in the pattern window to close it. The window also closes after 15 minutes. Stop the bridge separately with **Ctrl+C**.

## Record both displays

1. Select the rear camera's **Slo-mo** mode and confirm **240 fps** before recording. On iPhone, this setting is available under **Settings > Camera > Record Slo-mo**. See [Apple's recording settings](https://support.apple.com/guide/iphone/change-video-recording-settings-iphc1827d32f/ios).
2. Frame the real monitor and one eyepiece in the same recording. Keep both center squares visible, with as little vertical separation as practical. Camera rolling shutter can add an offset when it samples them at different times.
3. Hold the camera steady. Set focus and exposure so the square through the eyepiece stays distinguishable in both states. Its edges need not fill the lens view.
4. Record 10–15 seconds after the framing is stable. Keep stream settings and other PC activity unchanged during the take.
5. Transfer the unmodified camera file to the PC. On iPhone, use **Share > Export Unmodified Originals** to save it in Files. You can also download **Unmodified Originals** from iCloud Photos. See [Apple's original-file export instructions](https://support.apple.com/en-ie/111762).

Messaging apps can convert video during upload. For example, [Discord compresses mobile video uploads](https://support.discord.com/hc/en-us/articles/9665451164951-Video-Upload-Quality-Settings-on-Mobile-FAQ). To preserve an original while transferring it as an attachment, put it in a ZIP archive first. Keep edited exports separate from the original.

## Check the recording

Check the stored frame rate before calculating a delay. Replace `RECORDING_PATH` with the file path:

```powershell
ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,r_frame_rate,nb_frames,duration -of default=noprint_wrappers=1 "RECORDING_PATH"
```

A 240 fps capture can be exported with a different playback rate. If the file reports 30 or 60 fps, establish whether it was retimed or had frames removed. Do not multiply its frame count by 4.17 ms without that information. For a normal 60 fps recording, each frame spans about 16.67 ms.

## Count matching transitions

Open the recording in a viewer that can advance one frame at a time and show frame numbers. To use FFplay with a frame-number overlay, run:

```powershell
ffplay -noframedrop -vf "drawtext=fontfile='C\:/Windows/Fonts/consola.ttf':text='%{n}':x=20:y=20:fontsize=40:fontcolor=white:box=1:boxcolor=black" "RECORDING_PATH"
```

This command uses the Windows Consolas font. Adjust the font path if Windows is installed elsewhere. Press **P** to pause and **S** to advance one frame. Don't seek between the two frames in a measurement pair.

Count from the same point near the center of each square. Use the same transition criterion for both displays, such as the first frame past halfway between the dark and bright levels.

For each transition, record the monitor frame number and the frame number where the goggles show the matching change. For an original recording with capture rate `F`:

```text
delay_ms = (goggles_frame - monitor_frame) * 1000 / F
```

For example, 12 frames at 240 fps is 50 ms. Measure at least 10 transitions, including both directions, and report the median and range. Exclude sections where framing obscures the lens. Keep the individual measurements so others can check the result.

For an export slowed to a constant, known speed, use playback timestamps instead:

```text
delay_ms = (goggles_playback_seconds - monitor_playback_seconds) * playback_speed * 1000
```

At 10% speed, `playback_speed` is `0.1`. A 30 fps export can contain repeated frames even when the original capture was 240 fps. Use the export's playback timestamps for this calculation. Avoid the speed ramps at the start and end of an edited clip.

Camera exposure, rolling shutter, display scanout, and threshold choice affect the measurement. The 4.17 ms interval is sampling granularity, not a guarantee of absolute accuracy. Use actual frame timestamps when they are irregular, and resolve any slow-motion retiming before converting them to capture time.

## Report a result

Include the goggles model and firmware, PC and GPU, reference monitor refresh rate, camera mode and frame rate, FFmpeg version, bridge commit, complete command, and bridge log filename. Record the transitions measured, any excluded section, and the median and range.

Label this result as monitor-to-goggles delay with a synthetic moving source. Compare settings using the same setup and source. A separate test under simulator GPU load is needed to describe performance during flight. Keep personal recordings and full logs local unless you have reviewed them for sharing.
