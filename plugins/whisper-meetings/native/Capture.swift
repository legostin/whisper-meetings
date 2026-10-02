import Foundation
import AVFoundation
import ScreenCaptureKit
import CoreMedia
import CoreGraphics
import Darwin

enum CaptureError: Error { case message(String) }

// All control and writer state is owned by the sink's serial queue.
final class CaptureTimeline {
    let directory: URL
    var anchor = CMClockGetTime(CMClockGetHostTimeClock()).seconds
    var paused = false
    var pauseStarted: Double = 0
    var pausedSeconds: Double = 0
    var acceptAfter: Double = -Double.infinity
    var testTime: Double?

    init(_ directory: URL) { self.directory = directory }
    var clock: Double { testTime ?? CMClockGetTime(CMClockGetHostTimeClock()).seconds }
    var live: Bool { FileManager.default.fileExists(atPath: directory.appendingPathComponent("live-enabled").path) }
    var elapsed: Double { max(0, (paused ? pauseStarted : clock) - anchor - pausedSeconds) }

    func observe() {
        let requested = FileManager.default.fileExists(atPath: directory.appendingPathComponent("pause-requested").path)
        if requested != paused {
            if requested { pauseStarted = clock }
            else { pausedSeconds += clock - pauseStarted; acceptAfter = clock }
            paused = requested
        }
    }

    func elapsed(at timestamp: Double) -> Double? {
        observe()
        guard !paused, timestamp >= acceptAfter else { return nil }
        let value = timestamp - anchor - pausedSeconds
        return value.isFinite && value >= -1 && value < 86400 ? max(0, value) : nil
    }

    func publish() throws {
        let payload: [String: Any] = ["paused": paused, "elapsed_seconds": elapsed]
        try JSONSerialization.data(withJSONObject: payload).write(to: directory.appendingPathComponent("capture-state.json"), options: .atomic)
    }
}

// Full WAV stays open; separate finalized WAV chunks are safe for live readers.
final class TrackWriter {
    let directory: URL
    let name: String
    let format: AVAudioFormat
    let chunkSeconds: Double
    var file: AVAudioFile?
    var chunk: AVAudioFile?
    var frames: Int64 = 0
    var sampleFrames: Int64 = 0
    var chunkStart: Int64 = 0
    var chunkFrames: Int64 = 0
    var chunkIndex: Int = 0

    init(_ directory: URL, name: String, format: AVAudioFormat, chunkSeconds: Double = 12) throws {
        self.directory = directory; self.name = name; self.format = format; self.chunkSeconds = chunkSeconds
        file = try AVAudioFile(forWriting: directory.appendingPathComponent("\(name).wav"), settings: format.settings,
                               commonFormat: format.commonFormat, interleaved: format.isInterleaved)
    }
    var chunkDirectory: URL { directory.appendingPathComponent("live-chunks", isDirectory: true) }
    var chunkBase: String { "\(name)-\(String(format: "%06d", chunkIndex))" }

    func finishChunk() throws {
        guard chunk != nil else { return }
        chunk = nil // finalize the header before publishing the manifest
        let partial = chunkDirectory.appendingPathComponent(chunkBase + ".partial.wav")
        let ready = chunkDirectory.appendingPathComponent(chunkBase + ".wav")
        try FileManager.default.moveItem(at: partial, to: ready)
        let metadata: [String: Any] = ["source": name, "start": Double(chunkStart) / format.sampleRate,
                                      "end": Double(chunkStart + chunkFrames) / format.sampleRate]
        try JSONSerialization.data(withJSONObject: metadata).write(to: chunkDirectory.appendingPathComponent(chunkBase + ".json"), options: .atomic)
        chunkIndex += 1; chunkFrames = 0
    }

    func write(_ buffer: AVAudioPCMBuffer, live: Bool, isSample: Bool = true) throws {
        if !live { try finishChunk() }
        try file?.write(from: buffer)
        if live {
            if chunk == nil {
                try FileManager.default.createDirectory(at: chunkDirectory, withIntermediateDirectories: true)
                chunkStart = frames
                chunk = try AVAudioFile(forWriting: chunkDirectory.appendingPathComponent(chunkBase + ".partial.wav"),
                                        settings: format.settings, commonFormat: format.commonFormat, interleaved: format.isInterleaved)
            }
            try chunk?.write(from: buffer)
            chunkFrames += Int64(buffer.frameLength)
        }
        frames += Int64(buffer.frameLength)
        if isSample { sampleFrames += Int64(buffer.frameLength) }
        if chunkFrames >= Int64(format.sampleRate * chunkSeconds) { try finishChunk() }
    }

    func consume(_ buffer: AVAudioPCMBuffer, elapsed: Double?, live: Bool) throws {
        if let elapsed {
            var gap = Int64(elapsed * format.sampleRate) - frames
            while gap > Int64(format.sampleRate * 0.02) {
                let length = AVAudioFrameCount(min(gap, Int64(format.sampleRate)))
                guard let silence = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: length) else { break }
                silence.frameLength = length
                for item in UnsafeMutableAudioBufferListPointer(silence.mutableAudioBufferList) {
                    if let data = item.mData { memset(data, 0, Int(item.mDataByteSize)) }
                }
                try write(silence, live: live, isSample: false)
                gap -= Int64(length)
            }
        }
        try write(buffer, live: live)
    }
    func finish() throws { try finishChunk(); file = nil }
}

final class AudioSink: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    let directory: URL
    let queue = DispatchQueue(label: "in.legost.whisper-meetings.audio")
    let timeline: CaptureTimeline
    var writers: [String: TrackWriter] = [:]
    var failure: String?

    init(_ directory: URL) { self.directory = directory; timeline = CaptureTimeline(directory) }
    func stream(_ stream: SCStream, didStopWithError error: Error) { queue.async { self.failure = error.localizedDescription } }

    func consume(_ buffer: AVAudioPCMBuffer, source: String, timestamp: Double) throws {
        guard let elapsed = timeline.elapsed(at: timestamp) else { return }
        if writers[source] == nil { writers[source] = try TrackWriter(directory, name: source, format: buffer.format) }
        try writers[source]?.consume(buffer, elapsed: elapsed, live: timeline.live)
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio || type == .microphone, sample.isValid,
              let description = sample.formatDescription,
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(description),
              let format = AVAudioFormat(streamDescription: asbd) else { return }
        let count = CMSampleBufferGetNumSamples(sample)
        guard count > 0, let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(count)) else { return }
        buffer.frameLength = AVAudioFrameCount(count)
        let result = CMSampleBufferCopyPCMDataIntoAudioBufferList(sample, at: 0, frameCount: Int32(count), into: buffer.mutableAudioBufferList)
        guard result == noErr else { failure = "PCM copy failed: \(result)"; return }
        do { try consume(buffer, source: type == .microphone ? "microphone" : "system", timestamp: sample.presentationTimeStamp.seconds) }
        catch { failure = String(describing: error) }
    }

    func tick() throws {
        try queue.sync {
            timeline.observe()
            if timeline.paused || !timeline.live { for writer in writers.values { try writer.finishChunk() } }
            try timeline.publish()
            if let failure { throw CaptureError.message(failure) }
        }
    }

    func finish() throws {
        try queue.sync {
            for writer in writers.values { try writer.finish() }
            try timeline.publish()
            if let failure { throw CaptureError.message(failure) }
            let counts = writers.mapValues { $0.sampleFrames }
            try JSONSerialization.data(withJSONObject: counts, options: [.sortedKeys])
                .write(to: directory.appendingPathComponent("capture-stats.json"), options: .atomic)
            guard counts["microphone", default: 0] > 0, counts["system", default: 0] > 0 else {
                throw CaptureError.message("One audio source produced no samples. Check permissions; the available track is preserved.")
            }
        }
    }
}

// Microphone-only mode never creates an SCStream or requests screen access.
final class MicrophoneSink: @unchecked Sendable {
    let queue = DispatchQueue(label: "in.legost.whisper-meetings.microphone")
    let directory: URL
    let timeline: CaptureTimeline
    var writer: TrackWriter?
    var failure: String?
    init(_ directory: URL) { self.directory = directory; timeline = CaptureTimeline(directory) }

    func consume(_ buffer: AVAudioPCMBuffer, timestamp: Double? = nil) {
        guard let copy = AVAudioPCMBuffer(pcmFormat: buffer.format, frameCapacity: buffer.frameLength) else { return }
        copy.frameLength = buffer.frameLength
        let source = UnsafeMutableAudioBufferListPointer(buffer.mutableAudioBufferList)
        let target = UnsafeMutableAudioBufferListPointer(copy.mutableAudioBufferList)
        for index in source.indices {
            guard let input = source[index].mData, let output = target[index].mData else { return }
            memcpy(output, input, Int(source[index].mDataByteSize))
        }
        queue.async {
            do {
                self.timeline.observe()
                guard !self.timeline.paused else { return }
                let elapsed = timestamp.flatMap { self.timeline.elapsed(at: $0) }
                if timestamp != nil && elapsed == nil { return }
                if self.writer == nil { self.writer = try TrackWriter(self.directory, name: "microphone", format: copy.format) }
                try self.writer?.consume(copy, elapsed: elapsed, live: self.timeline.live)
            } catch { self.failure = error.localizedDescription }
        }
    }

    func tick() throws {
        try queue.sync {
            timeline.observe()
            if timeline.paused || !timeline.live { try writer?.finishChunk() }
            try timeline.publish()
            if let failure { throw CaptureError.message(failure) }
        }
    }
    func finish() throws {
        try queue.sync {
            try writer?.finish()
            try timeline.publish()
            if let failure { throw CaptureError.message(failure) }
            let count = writer?.sampleFrames ?? 0
            try JSONSerialization.data(withJSONObject: ["microphone": count])
                .write(to: directory.appendingPathComponent("capture-stats.json"), options: .atomic)
            guard count > 0 else { throw CaptureError.message("Microphone produced no samples. Check the input device and permission.") }
        }
    }
}

@main struct Capture {
    static func microphoneOnly(_ directory: URL, parent: pid_t) async throws {
        let engine = AVAudioEngine()
        let sink = MicrophoneSink(directory)
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else { throw CaptureError.message("No microphone input available") }
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, when in
            sink.consume(buffer, timestamp: when.isHostTimeValid ? AVAudioTime.seconds(forHostTime: when.hostTime) : nil)
        }
        var tapped = true
        defer { engine.stop(); if tapped { input.removeTap(onBus: 0) } }
        engine.prepare()
        try engine.start()
        try Data("ready".utf8).write(to: directory.appendingPathComponent("capture-ready"), options: .atomic)
        let deadline = Date().addingTimeInterval(12 * 3600)
        while !FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path),
              Date() < deadline, getppid() == parent {
            try sink.tick()
            try await Task.sleep(for: .milliseconds(200))
        }
        engine.stop()
        input.removeTap(onBus: 0)
        tapped = false
        try sink.finish()
    }

    static func main() async {
        do {
            guard #available(macOS 15.0, *) else { throw CaptureError.message("macOS 15 or newer is required") }
            if CommandLine.arguments.contains("--check") {
                let microphone: String
                switch AVCaptureDevice.authorizationStatus(for: .audio) {
                case .authorized: microphone = "authorized"
                case .notDetermined: microphone = "not_determined"
                case .denied: microphone = "denied"
                case .restricted: microphone = "restricted"
                @unknown default: microphone = "unknown"
                }
                let data = try JSONSerialization.data(withJSONObject: ["screen_audio": CGPreflightScreenCaptureAccess(), "microphone": microphone, "pause_resume": true, "live_chunks": true])
                print(String(decoding: data, as: UTF8.self)); return
            }
            // Exercises the real PCM writer with generated samples, no devices.
            if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--test-microphone-sink" {
                let directory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
                let format = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 1)!
                let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4800)!
                buffer.frameLength = 4800
                for i in 0..<4800 { buffer.floatChannelData![0][i] = sin(Float(i) * 0.1) * 0.25 }
                let sink = MicrophoneSink(directory)
                sink.consume(buffer)
                try sink.finish()
                return
            }
            if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--test-streaming-sinks" {
                let directory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
                let format = AVAudioFormat(standardFormatWithSampleRate: 16000, channels: 1)!
                let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 16000)!
                buffer.frameLength = 16000
                let sink = AudioSink(directory)
                sink.timeline.anchor = 0
                try Data().write(to: directory.appendingPathComponent("live-enabled"))
                for tick in 0..<30 {
                    if tick == 12 { try Data().write(to: directory.appendingPathComponent("pause-requested")) }
                    if tick == 17 { try FileManager.default.removeItem(at: directory.appendingPathComponent("pause-requested")) }
                    sink.queue.sync { sink.timeline.testTime = Double(tick) }
                    try sink.tick()
                    for i in 0..<16000 { buffer.floatChannelData![0][i] = tick >= 12 && tick < 17 ? 0.9 : 0.1 }
                    try sink.queue.sync {
                        try sink.consume(buffer, source: "microphone", timestamp: Double(tick))
                        try sink.consume(buffer, source: "system", timestamp: Double(tick))
                    }
                }
                // Also exercise pause/continue through the async microphone tap path.
                let micDirectory = directory.appendingPathComponent("mic-only")
                try FileManager.default.createDirectory(at: micDirectory, withIntermediateDirectories: true)
                let mic = MicrophoneSink(micDirectory)
                mic.consume(buffer)
                try mic.tick()
                try Data().write(to: micDirectory.appendingPathComponent("pause-requested"))
                try mic.tick()
                mic.consume(buffer) // discarded
                try mic.tick()
                try FileManager.default.removeItem(at: micDirectory.appendingPathComponent("pause-requested"))
                try mic.tick()
                mic.consume(buffer)
                try mic.finish()
                sink.queue.sync { sink.timeline.testTime = 30 }
                try sink.finish()
                return
            }
            guard CommandLine.arguments.count == 2 || (CommandLine.arguments.count == 3 && CommandLine.arguments[2] == "--microphone-only") else { throw CaptureError.message("Usage: capture DIRECTORY [--microphone-only] | --check") }
            let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            let parent = getppid()
            if FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path) { return }
            guard await AVCaptureDevice.requestAccess(for: .audio) else { throw CaptureError.message("Microphone access denied. Enable Whisper Meetings or its launching app in System Settings > Privacy & Security > Microphone.") }
            if FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path) { return }
            if CommandLine.arguments.contains("--microphone-only") {
                try await microphoneOnly(directory, parent: parent)
                return
            }
            guard CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess() else {
                throw CaptureError.message("System audio access denied. Enable the recorder in System Settings > Privacy & Security > Screen & System Audio Recording, then retry.")
            }
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            if FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path) { return }
            guard let display = content.displays.first else { throw CaptureError.message("No display available") }
            let filter = SCContentFilter(display: display, excludingWindows: [])
            let config = SCStreamConfiguration()
            config.width = 2; config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
            config.capturesAudio = true
            config.captureMicrophone = true
            config.sampleRate = 48000
            config.channelCount = 1
            config.excludesCurrentProcessAudio = true
            let sink = AudioSink(directory)
            let stream = SCStream(filter: filter, configuration: config, delegate: sink)
            // No screen output is attached: no video or screenshots are saved.
            try stream.addStreamOutput(sink, type: .audio, sampleHandlerQueue: sink.queue)
            try stream.addStreamOutput(sink, type: .microphone, sampleHandlerQueue: sink.queue)
            sink.timeline.anchor = CMClockGetTime(CMClockGetHostTimeClock()).seconds
            try await stream.startCapture()
            try Data("ready".utf8).write(to: directory.appendingPathComponent("capture-ready"), options: .atomic)
            let deadline = Date().addingTimeInterval(12 * 3600)
            while !FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path), Date() < deadline, getppid() == parent {
                try sink.tick()
                try await Task.sleep(for: .milliseconds(200))
            }
            try await stream.stopCapture()
            try sink.finish()
        } catch {
            FileHandle.standardError.write(Data("\(error)\n".utf8))
            exit(1)
        }
    }
}
