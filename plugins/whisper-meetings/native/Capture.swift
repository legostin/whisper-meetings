import Foundation
import AVFoundation
import ScreenCaptureKit
import CoreMedia
import CoreGraphics
import Darwin

enum CaptureError: Error { case message(String) }

// One serial queue owns both writers. PCM is written incrementally to disk.
final class AudioSink: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    let directory: URL
    let queue = DispatchQueue(label: "in.legost.whisper-meetings.audio")
    var files: [SCStreamOutputType: AVAudioFile] = [:]
    var frames: [SCStreamOutputType: Int64] = [:]
    var sampleFrames: [String: Int64] = [:]
    var anchor = CMClockGetTime(CMClockGetHostTimeClock()).seconds
    var failure: String?

    init(_ directory: URL) { self.directory = directory }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        queue.async { self.failure = error.localizedDescription }
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
        let name = type == .microphone ? "microphone" : "system"
        do {
            if files[type] == nil {
                files[type] = try AVAudioFile(forWriting: directory.appendingPathComponent("\(name).wav"), settings: format.settings,
                                             commonFormat: format.commonFormat, interleaved: format.isInterleaved)
                frames[type] = 0
            }
            guard let file = files[type] else { return }
            // Shared host-clock timestamps preserve the alignment of the two tracks,
            // including leading silence and gaps caused by muted input.
            let elapsed = sample.presentationTimeStamp.seconds - anchor
            guard elapsed.isFinite, elapsed >= -1, elapsed < 86400 else {
                throw CaptureError.message("Unexpected audio clock; cannot align tracks")
            }
            let expected = Int64(max(0, elapsed) * format.sampleRate)
            var gap = expected - (frames[type] ?? 0)
            while gap > Int64(format.sampleRate * 0.02) {
                let length = AVAudioFrameCount(min(gap, Int64(format.sampleRate)))
                guard let silence = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: length) else { break }
                silence.frameLength = length
                for item in UnsafeMutableAudioBufferListPointer(silence.mutableAudioBufferList) {
                    if let data = item.mData { memset(data, 0, Int(item.mDataByteSize)) }
                }
                try file.write(from: silence)
                frames[type, default: 0] += Int64(length)
                gap -= Int64(length)
            }
            try file.write(from: buffer)
            frames[type, default: 0] += Int64(count)
            sampleFrames[name, default: 0] += Int64(count)
        } catch { failure = String(describing: error) }
    }

    func finish() throws {
        try queue.sync {
            files.removeAll() // close and finalize WAV headers before transcription
            if let failure { throw CaptureError.message(failure) }
            let data = try JSONSerialization.data(withJSONObject: sampleFrames, options: [.sortedKeys])
            try data.write(to: directory.appendingPathComponent("capture-stats.json"), options: .atomic)
            guard sampleFrames["microphone", default: 0] > 0, sampleFrames["system", default: 0] > 0 else {
                throw CaptureError.message("One audio source produced no samples. Check microphone and system-audio permissions; the available track is preserved.")
            }
        }
    }
}

// Microphone-only mode never creates an SCStream or requests screen access.
final class MicrophoneSink: @unchecked Sendable {
    let queue = DispatchQueue(label: "in.legost.whisper-meetings.microphone")
    let directory: URL
    var file: AVAudioFile?
    var frames: Int64 = 0
    var failure: String?

    init(_ directory: URL) { self.directory = directory }

    func consume(_ buffer: AVAudioPCMBuffer) {
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
                if self.file == nil {
                    self.file = try AVAudioFile(forWriting: self.directory.appendingPathComponent("microphone.wav"),
                                               settings: copy.format.settings, commonFormat: copy.format.commonFormat,
                                               interleaved: copy.format.isInterleaved)
                }
                try self.file?.write(from: copy)
                self.frames += Int64(copy.frameLength)
            } catch { self.failure = error.localizedDescription }
        }
    }

    func finish() throws {
        try queue.sync {
            file = nil
            if let failure { throw CaptureError.message(failure) }
            try JSONSerialization.data(withJSONObject: ["microphone": frames])
                .write(to: directory.appendingPathComponent("capture-stats.json"), options: .atomic)
            guard frames > 0 else { throw CaptureError.message("Microphone produced no samples. Check the input device and permission.") }
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
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, _ in sink.consume(buffer) }
        var tapped = true
        defer { engine.stop(); if tapped { input.removeTap(onBus: 0) } }
        engine.prepare()
        try engine.start()
        try Data("ready".utf8).write(to: directory.appendingPathComponent("capture-ready"), options: .atomic)
        let deadline = Date().addingTimeInterval(12 * 3600)
        while !FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path),
              Date() < deadline, getppid() == parent {
            if let failure = sink.queue.sync(execute: { sink.failure }) { throw CaptureError.message(failure) }
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
                let data = try JSONSerialization.data(withJSONObject: ["screen_audio": CGPreflightScreenCaptureAccess(), "microphone": microphone])
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
            sink.anchor = CMClockGetTime(CMClockGetHostTimeClock()).seconds
            try await stream.startCapture()
            try Data("ready".utf8).write(to: directory.appendingPathComponent("capture-ready"), options: .atomic)
            let deadline = Date().addingTimeInterval(12 * 3600)
            while !FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path), Date() < deadline, getppid() == parent {
                if let failure = sink.queue.sync(execute: { sink.failure }) { throw CaptureError.message(failure) }
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
