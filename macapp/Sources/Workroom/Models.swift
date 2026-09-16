import Foundation

// Mirrors `python -m agent.bridge survey`. The Python side owns the
// catalogue; this file only has to decode it.

struct Hardware: Codable, Sendable {
    var chip: String
    var total_ram_gb: Int
    var macos: String
    var arch: String
    var apple_silicon: Bool

    var summary: String { "\(chip) · \(total_ram_gb) GB unified · macOS \(macos)" }
}

struct ModelRow: Codable, Identifiable, Sendable {
    var key: String
    var repo: String
    var label: String
    var gb: Double
    var vision: Bool
    var role: String
    var blurb: String
    var needs_ram_gb: Int
    var tps: String
    var recommended: Bool
    var runnable: Bool
    var reason: String

    var id: String { key }
    var sizeText: String { String(format: "4-bit MLX  ·  %.2f GB", gb) }
}

struct Preset: Codable, Identifiable, Sendable {
    var key: String
    var title: String
    var desc: String
    var tps: String
    var ctx: Int
    var limit_gb: Int
    var limit_mb: Int
    var total_gb: Int
    var recommended_gb: Double
    var needs_sysctl: Bool
    var sysctl_command: String

    var id: String { key }
    var ctxText: String { "\(ctx / 1024)k context" }
}

struct LocalModel: Codable, Identifiable, Sendable {
    var name: String
    var source: String
    var gb: Double
    var path: String?
    var vision: Bool?

    var id: String { "\(source):\(name)" }
    var sourceLabel: String { source == "ollama" ? "Ollama" : "Hugging Face" }
}

struct GatewayRow: Codable, Identifiable, Sendable {
    var key: String
    var label: String
    var base_url: String
    var docs: String
    var reachable: Bool
    var models: [String]
    var detail: String

    var id: String { key }
}

struct Survey: Codable, Sendable {
    var hardware: Hardware
    var catalogue: [ModelRow]
    var presets: [Preset]
    var local_models: [LocalModel]
    var gateways: [GatewayRow]
    var current_sysctl_mb: Int

    var brains: [ModelRow] { catalogue.filter { $0.role == "brain" } }
    var compressor: ModelRow? { catalogue.first { $0.role == "compressor" } }
    var liveGateways: [GatewayRow] { gateways.filter(\.reachable) }
}

/// One line of `scripts/pull_models.py --json`.
struct PullProgress: Codable, Sendable {
    var key: String
    var label: String
    var status: String        // downloading | done | error
    var pct: Double
    var downloaded_gb: Double
    var total_gb: Double
    var detail: String?

    var isDone: Bool { status == "done" }
    var isError: Bool { status == "error" }
}

/// Where the user is in the flow. Raw values order the progress dots.
enum Screen: Int, CaseIterable, Sendable {
    case welcome, promise, textModel, visionModel, memory, downloading, launch

    /// Only the middle screens carry the dot pager; the bookends are chromeless.
    var showsPager: Bool { self != .welcome && self != .launch }
    var pagerIndex: Int { rawValue - 1 }
    static var pagerCount: Int { 5 }
}
