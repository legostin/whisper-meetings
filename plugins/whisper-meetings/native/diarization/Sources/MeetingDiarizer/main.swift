import CoreML
import Darwin
import FluidAudio
import Foundation

// Load only supplied local assets. No ModelHub, prepareModels, downloader,
// speaker enrollment, or persistent voice database is used.
struct Turn: Codable {
    let start: Float
    let end: Float
    let speaker: String
}

@main
struct Main {
    nonisolated static func armWatchdog() -> DispatchSourceTimer {
        let parent = getppid()
        let watchdog = DispatchSource.makeTimerSource(queue: .global())
        watchdog.schedule(deadline: .now() + 1, repeating: 1)
        watchdog.setEventHandler { if getppid() != parent { exit(1) } }
        watchdog.resume()
        return watchdog
    }

    static func main() async {
        let watchdog = armWatchdog()
        defer { watchdog.cancel() }
        do {
            guard CommandLine.arguments.count == 4 else {
                throw NSError(domain: "MeetingDiarizer", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "Usage: meeting-diarizer MODELS AUDIO OUTPUT_JSON"])
            }
            let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            func load(_ name: String, cpuOnly: Bool = false) throws -> MLModel {
                let modelConfig = MLModelConfiguration()
                modelConfig.computeUnits = cpuOnly ? .cpuOnly : .all
                return try MLModel(contentsOf: root.appendingPathComponent(name + ".mlmodelc"), configuration: modelConfig)
            }
            let data = try Data(contentsOf: root.appendingPathComponent("plda-parameters.json"))
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            guard let tensors = json?["tensors"] as? [String: Any],
                  let psi = tensors["psi"] as? [String: Any],
                  let encoded = psi["data_base64"] as? String,
                  let bytes = Data(base64Encoded: encoded), bytes.count % 4 == 0 else {
                throw NSError(domain: "MeetingDiarizer", code: 2,
                              userInfo: [NSLocalizedDescriptionKey: "Invalid local PLDA parameters"])
            }
            let values: [Double] = stride(from: 0, to: bytes.count, by: 4).map { offset in
                Double(Float(bitPattern: UInt32(littleEndian: bytes.withUnsafeBytes {
                    $0.loadUnaligned(fromByteOffset: offset, as: UInt32.self)
                })))
            }
            let models = try OfflineDiarizerModels(
                segmentationModel: load("Segmentation"), fbankModel: load("FBank", cpuOnly: true),
                embeddingModel: load("Embedding"), pldaRhoModel: load("PldaRho"),
                pldaPsi: values, compilationDuration: 0)
            var settings = OfflineDiarizerConfig()
            // The default trims overlaps. Keep simultaneous speech intervals.
            settings.postProcessing.exclusiveSegments = false
            settings.export.embeddingsPath = nil
            let manager = OfflineDiarizerManager(config: settings)
            manager.initialize(models: models)
            let result = try await manager.process(URL(fileURLWithPath: CommandLine.arguments[2]))
            let turns = result.segments.map {
                Turn(start: $0.startTimeSeconds, end: $0.endTimeSeconds, speaker: $0.speakerId)
            }
            try JSONEncoder().encode(turns).write(to: URL(fileURLWithPath: CommandLine.arguments[3]), options: .atomic)
        } catch {
            FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
            exit(1)
        }
    }
}
