// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "MeetingDiarizer",
    platforms: [.macOS(.v15)],
    products: [.executable(name: "meeting-diarizer", targets: ["MeetingDiarizer"])],
    dependencies: [.package(url: "https://github.com/FluidInference/FluidAudio.git",
                            revision: "c388107348134698135cfd34f3f59dc823b6e7ce", traits: [])],
    targets: [.executableTarget(name: "MeetingDiarizer",
                               dependencies: [.product(name: "FluidAudio", package: "FluidAudio")])]
)
