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

@main struct Capture {
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
            guard CommandLine.arguments.count == 2 else { throw CaptureError.message("Usage: capture DIRECTORY | --check") }
            let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            let parent = getppid()
            if FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop-requested").path) { return }
            guard await AVCaptureDevice.requestAccess(for: .audio) else { throw CaptureError.message("Microphone access denied. Enable Whisper Meetings or its launching app in System Settings > Privacy & Security > Microphone.") }
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
