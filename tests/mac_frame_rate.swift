import CoreMedia

@main
struct FrameRateTests {
    static func main() {
        for target in [60, 75, 90, 100] {
            for source in [30, 60, 120, 144, 240] {
                var limiter = FrameRateLimiter()
                var accepted = 0
                for frame in 0..<source * 10 {
                    let time = CMTime(value: Int64(frame), timescale: CMTimeScale(source))
                    if limiter.accepts(time, fps: target) { accepted += 1 }
                    assert(!limiter.accepts(time, fps: target), "duplicate callback was encoded")
                }
                assert(accepted == min(source, target) * 10, "wrong rate for \(source) -> \(target): \(accepted)")
            }
        }
        var limiter = FrameRateLimiter()
        assert(limiter.accepts(CMTime(value: 1_000_000, timescale: 1), fps: 100))
        assert(limiter.accepts(CMTime(value: 1_000_100, timescale: 1), fps: 100))
        assert(!limiter.accepts(CMTime(value: 1_000_100, timescale: 1), fps: 100))
    }
}
