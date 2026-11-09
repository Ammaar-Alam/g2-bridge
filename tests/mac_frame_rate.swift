import CoreMedia
import Foundation

@main
struct FrameRateTests {
    static func main() {
        var jitterCounts: [Int] = []
        for target in [60, 75, 90, 100] {
            var limiter = FrameRateLimiter()
            var accepted = 0
            for frame in 0..<600 {
                let time = CMTimeAdd(CMTime(value: Int64(frame), timescale: CMTimeScale(target)),
                                     CMTime(value: frame % 2 == 0 ? 1 : -1, timescale: 2000))
                if limiter.accepts(time, fps: target) { accepted += 1 }
            }
            jitterCounts.append(accepted)
            FileHandle.standardError.write(Data("\(target) fps with +/-0.5 ms jitter: \(accepted)/600 frames\n".utf8))
        }
        assert(jitterCounts.allSatisfy { $0 == 600 }, "timestamp jitter discarded distinct frames")

        for target in [60, 75, 90, 100] {
            for source in [30, 60, 120, 144, 240] {
                var limiter = FrameRateLimiter()
                var accepted = 0
                for frame in 0..<source * 10 {
                    let time = CMTime(value: Int64(frame), timescale: CMTimeScale(source))
                    if limiter.accepts(time, fps: target) { accepted += 1 }
                    assert(!limiter.accepts(time, fps: target), "duplicate callback was encoded")
                }
                let expected = min(source, target) * 10
                assert((expected...(expected + (source > target ? 1 : 0))).contains(accepted),
                       "wrong rate for \(source) -> \(target): \(accepted)")
            }

            // Near-target rates, jitter phases, and stalls must not halve the frame rate
            // or accumulate timing credit that creates a burst after capture resumes.
            for sourceTenths in [300, target * 10 - 1, target * 10, target * 10 + 1, 1200, 1440, 2400] {
                for phase in [-1, 0, 1] {
                    for gapMillis in [0, 20, 200] {
                        var limiter = FrameRateLimiter()
                        var accepted = 0
                        var first: CMTime?
                        for frame in 0..<600 {
                            let regular = CMTime(value: Int64(frame * 10), timescale: CMTimeScale(sourceTenths))
                            let jitter = CMTime(value: Int64(phase * (frame % 2 == 0 ? 1 : -1)), timescale: 2000)
                            let gap = CMTime(value: Int64(frame >= 300 ? gapMillis : 0), timescale: 1000)
                            let time = CMTimeAdd(CMTimeAdd(regular, jitter), gap)
                            if first == nil { first = time }
                            let selected = limiter.accepts(time, fps: target)
                            if selected { accepted += 1 }
                            assert(!limiter.accepts(time, fps: target), "duplicate callback was encoded")
                            if sourceTenths <= target * 10 {
                                assert(selected, "lost a frame at or below the target rate")
                            }
                            if frame == 300 && gapMillis > 0 {
                                assert(selected, "first frame after a gap was discarded")
                            }
                            let elapsed = CMTimeSubtract(time, first!)
                            let slots = CMTimeConvertScale(elapsed, timescale: CMTimeScale(target), method: .roundTowardZero).value
                            assert(Int64(accepted) <= slots + 2, "capture exceeded one frame of burst allowance")
                        }
                    }
                }
            }
        }

        // Subtract host timestamps before comparing with exact frame intervals: adding
        // a rounded 1/fps to a nanosecond deadline on every frame can drift over time.
        for target in [60, 75, 90, 100] {
            var limiter = FrameRateLimiter()
            let base = CMTime(value: 1_000_000_000_000_000, timescale: 1_000_000_000)
            for frame in 0..<60_000 {
                let offset = CMTimeConvertScale(CMTime(value: Int64(frame), timescale: CMTimeScale(target)),
                                                timescale: base.timescale, method: .roundTowardZero)
                let time = CMTimeAdd(base, offset)
                assert(limiter.accepts(time, fps: target), "host timestamp rounding discarded a frame")
                assert(!limiter.accepts(time, fps: target), "duplicate callback was encoded")
            }
        }

        var limiter = FrameRateLimiter()
        for time in [CMTime.invalid, .indefinite, .positiveInfinity, .negativeInfinity] {
            assert(!limiter.accepts(time, fps: 100), "invalid host timestamp was accepted")
        }
        assert(limiter.accepts(CMTime(value: 1_000_000, timescale: 1), fps: 100))
        assert(limiter.accepts(CMTime(value: 1_000_100, timescale: 1), fps: 100))
        assert(!limiter.accepts(CMTime(value: 1_000_100, timescale: 1), fps: 100))
        assert(!limiter.accepts(CMTime(value: 1_000_099, timescale: 1), fps: 100), "backward timestamp was accepted")
        assert(limiter.accepts(CMTime(value: 100_010_001, timescale: 100), fps: 100))
    }
}
