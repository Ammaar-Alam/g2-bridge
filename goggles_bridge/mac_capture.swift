// Capture a display with ScreenCaptureKit and write hardware-encoded H.264 to stdout,
// framed like FFmpeg's nonseekable AVI or Annex-B output so the bridge readers work unchanged
import CoreMedia
import Foundation
import ScreenCaptureKit
import VideoToolbox

struct Options {
    var display = 0, fps = 100, captureFps = 240, bitrate = 20_000_000, keyframeSeconds = 3, frames = 0
    var profile = "high", format = "avi", cursor = true
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func parseOptions() -> Options {
    var options = Options()
    var args = CommandLine.arguments.dropFirst().makeIterator()
    while let flag = args.next() {
        if flag == "--hide-cursor" {
            options.cursor = false
            continue
        }
        guard let value = args.next() else { fail("Missing value for \(flag)") }
        let number = Int(value) ?? -1
        switch flag {
        case "--display": options.display = number
        case "--fps": options.fps = number
        case "--capture-fps": options.captureFps = number
        case "--bitrate": options.bitrate = number
        case "--keyframe-seconds": options.keyframeSeconds = number
        case "--frames": options.frames = number
        case "--profile": options.profile = value
        case "--format": options.format = value
        default: fail("Unknown option \(flag)")
        }
    }
    if [options.display, options.fps, options.captureFps, options.bitrate, options.keyframeSeconds, options.frames].contains(where: { $0 < 0 })
        || !["high", "baseline"].contains(options.profile) || !["avi", "h264"].contains(options.format) {
        fail("Invalid options: \(CommandLine.arguments.dropFirst().joined(separator: " "))")
    }
    return options
}

func le(_ value: Int, _ bytes: Int = 4) -> Data {
    Data((0..<bytes).map { UInt8(truncatingIfNeeded: value >> (8 * $0)) })
}

func chunk(_ tag: String, _ body: Data) -> Data {
    Data(tag.utf8) + le(body.count) + body + (body.count % 2 == 1 ? Data([0]) : Data())
}

// Just enough AVI for the bridge reader: one H264 video stream, then an open-ended movie list
func aviHeader() -> Data {
    var avih = Data(count: 56)
    avih.replaceSubrange(24..<28, with: le(1))
    avih.replaceSubrange(32..<40, with: le(1920) + le(1080))
    let strh = Data("vidsH264".utf8) + Data(count: 48)
    let strf = le(40) + le(1920) + le(1080) + le(1, 2) + le(24, 2) + Data("H264".utf8) + Data(count: 20)
    let hdrl = chunk("LIST", Data("hdrl".utf8) + chunk("avih", avih) + chunk("LIST", Data("strl".utf8) + chunk("strh", strh) + chunk("strf", strf)))
    return Data("RIFF".utf8) + le(0x7fff_ffff) + Data("AVI ".utf8) + hdrl + Data("LIST".utf8) + le(0x7fff_ffff) + Data("movi".utf8)
}

let startCode = Data([0, 0, 0, 1])
let accessUnitDelimiter = startCode + Data([0x09, 0xf0])

func annexB(_ sample: CMSampleBuffer) -> Data {
    var unit = accessUnitDelimiter
    guard let format = CMSampleBufferGetFormatDescription(sample), let block = CMSampleBufferGetDataBuffer(sample) else { return unit }
    var count = 0, headerLength: Int32 = 4
    CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format, parameterSetIndex: 0, parameterSetPointerOut: nil,
                                                       parameterSetSizeOut: nil, parameterSetCountOut: &count, nalUnitHeaderLengthOut: &headerLength)
    let attachments = CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: false) as? [[CFString: Any]]
    if attachments?.first?[kCMSampleAttachmentKey_NotSync] as? Bool != true {
        for index in 0..<count {
            var pointer: UnsafePointer<UInt8>?
            var size = 0
            CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format, parameterSetIndex: index, parameterSetPointerOut: &pointer,
                                                               parameterSetSizeOut: &size, parameterSetCountOut: nil, nalUnitHeaderLengthOut: nil)
            if let pointer { unit += startCode + Data(bytes: pointer, count: size) }
        }
    }
    var data = Data(count: CMBlockBufferGetDataLength(block))
    data.withUnsafeMutableBytes { _ = CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: $0.count, destination: $0.baseAddress!) }
    var offset = 0
    let header = Int(headerLength)
    while offset + header <= data.count {
        let size = data[offset..<offset+header].reduce(0) { $0 << 8 | Int($1) }
        unit += startCode + data[offset+header..<min(offset+header+size, data.count)]
        offset += header + size
    }
    return unit
}

final class Capture: NSObject, SCStreamOutput, SCStreamDelegate {
    let options: Options
    let output = FileHandle.standardOutput
    var session: VTCompressionSession?
    var last: CVPixelBuffer?
    var sent = 0, fresh = 0, delays: [Double] = []
    var reportAt = DispatchTime.now().uptimeNanoseconds + 5_000_000_000
    var timebase = mach_timebase_info()

    init(_ options: Options) {
        self.options = options
        super.init()
        mach_timebase_info(&timebase)
        let spec = [kVTVideoEncoderSpecification_EnableLowLatencyRateControl: true] as CFDictionary
        let status = VTCompressionSessionCreate(allocator: nil, width: 1920, height: 1080, codecType: kCMVideoCodecType_H264,
                                                encoderSpecification: spec, imageBufferAttributes: nil, compressedDataAllocator: nil,
                                                outputCallback: nil, refcon: nil, compressionSessionOut: &session)
        guard status == noErr, let session else { fail("Cannot start the low-latency H.264 encoder: \(status)") }
        let properties: [CFString: Any] = [
            kVTCompressionPropertyKey_RealTime: true,
            kVTCompressionPropertyKey_AllowFrameReordering: false,
            kVTCompressionPropertyKey_ProfileLevel: options.profile == "high" ? kVTProfileLevel_H264_High_AutoLevel
                                                                            : kVTProfileLevel_H264_ConstrainedBaseline_AutoLevel,
            kVTCompressionPropertyKey_AverageBitRate: options.bitrate,
            kVTCompressionPropertyKey_ExpectedFrameRate: options.fps,
            kVTCompressionPropertyKey_MaxKeyFrameInterval: options.fps * options.keyframeSeconds,
            kVTCompressionPropertyKey_MaxKeyFrameIntervalDuration: options.keyframeSeconds,
        ]
        for (key, value) in properties where VTSessionSetProperty(session, key: key, value: value as CFTypeRef) != noErr {
            fail("Encoder rejected \(key)")
        }
        if options.format == "avi" { output.write(aviHeader()) }
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen,
              let info = (CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]])?.first,
              let raw = info[.status] as? Int, let status = SCFrameStatus(rawValue: raw) else { return }
        let displayTime = info[.displayTime] as? UInt64
        switch status {
        case .complete:
            last = CMSampleBufferGetImageBuffer(sample)
            encode(displayTime)
        case .idle:
            // repeat the last picture so a still screen keeps the goggles fed
            encode(nil)
        default:
            return
        }
    }

    func encode(_ displayTime: UInt64?) {
        guard let session, let image = last else { return }
        let now = CMClockGetTime(CMClockGetHostTimeClock())
        VTCompressionSessionEncodeFrame(session, imageBuffer: image, presentationTimeStamp: now, duration: .invalid,
                                        frameProperties: nil, infoFlagsOut: nil) { [self] status, _, sample in
            guard status == noErr, let sample else { fail("Encoding failed: \(status)") }
            let unit = annexB(sample)
            output.write(options.format == "avi" ? chunk("00dc", unit) : unit)
            sent += 1
            if let displayTime {
                fresh += 1
                // display time can lead the callback slightly, so subtract without trapping
                let ticks = Int64(bitPattern: mach_absolute_time() &- displayTime)
                delays.append(Double(ticks) * Double(timebase.numer) / Double(timebase.denom) / 1e6)
            }
            if options.frames > 0 && sent >= options.frames { exit(0) }
            report()
        }
    }

    func report() {
        let now = DispatchTime.now().uptimeNanoseconds
        guard now >= reportAt else { return }
        let sorted = delays.sorted()
        let pick = { (q: Double) in sorted.isEmpty ? 0 : sorted[Int(Double(sorted.count - 1) * q)] }
        FileHandle.standardError.write(Data(String(format: "sent %.1f fps, %.1f new | display-to-encoded min %.1f p50 %.1f p95 %.1f ms\n",
                                                   Double(sent) / 5, Double(fresh) / 5, pick(0), pick(0.5), pick(0.95)).utf8))
        sent = 0
        fresh = 0
        delays.removeAll(keepingCapacity: true)
        reportAt = now + 5_000_000_000
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fail("Screen capture stopped: \(error.localizedDescription)")
    }
}

let options = parseOptions()
var running: (Capture, SCStream)?
SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: true) { content, error in
    guard let content else {
        fail("Cannot capture the screen. In System Settings > Privacy & Security, allow screen recording for this terminal. (\(error?.localizedDescription ?? "no details"))")
    }
    // number displays like CGGetActiveDisplayList and FFmpeg's AVFoundation input, main display first
    var ids = [CGDirectDisplayID](repeating: 0, count: 16)
    var count: UInt32 = 0
    CGGetActiveDisplayList(16, &ids, &count)
    guard options.display < count, let display = content.displays.first(where: { $0.displayID == ids[options.display] }) else {
        fail("Display \(options.display) not found. \(count) display(s) connected")
    }
    let config = SCStreamConfiguration()
    config.width = 1920
    config.height = 1080
    let aspect = Double(display.width) / Double(display.height)
    let width = aspect >= 16.0 / 9 ? 1920 : Int(1080 * aspect) / 2 * 2
    let height = aspect >= 16.0 / 9 ? Int(1920 / aspect) / 2 * 2 : 1080
    config.destinationRect = CGRect(x: (1920 - width) / 2, y: (1080 - height) / 2, width: width, height: height)
    config.pixelFormat = kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
    config.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(options.captureFps))
    config.queueDepth = 4
    config.showsCursor = options.cursor
    let capture = Capture(options)
    let stream = SCStream(filter: SCContentFilter(display: display, excludingWindows: []), configuration: config, delegate: capture)
    do {
        try stream.addStreamOutput(capture, type: .screen, sampleHandlerQueue: DispatchQueue(label: "capture", qos: .userInteractive))
    } catch {
        fail("Cannot attach to the screen stream: \(error.localizedDescription)")
    }
    stream.startCapture { error in
        if let error { fail("Cannot start screen capture: \(error.localizedDescription)") }
    }
    running = (capture, stream)
}
dispatchMain()
