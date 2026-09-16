// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Workroom",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Workroom",
            path: "Sources/Workroom",
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
