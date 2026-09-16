import SwiftUI
import AppKit

/// Renders every onboarding screen to a PNG and exits.
///
/// The app draws its own pixels, so this needs no Screen Recording grant and
/// runs headless. Used to review the design against `design/*.dc.html`.
@MainActor
enum Snapshotter {
    static func run(into directory: String) {
        let dir = URL(fileURLWithPath: directory)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        let survey = (try? loadSurvey()) ?? nil
        guard let survey else {
            FileHandle.standardError.write(Data("snapshot: could not read the survey\n".utf8))
            exit(2)
        }

        for screen in Screen.allCases {
            for scheme in [ColorScheme.light, .dark] {
                let name = "\(screen.rawValue)-\(String(describing: screen))"
                    + (scheme == .dark ? "-dark" : "")
                render(screen: screen, survey: survey, scheme: scheme,
                       to: dir.appendingPathComponent("\(name).png"))
            }
        }
        print("wrote \(Screen.allCases.count * 2) screens to \(dir.path)")
        exit(0)
    }

    private static func loadSurvey() throws -> Survey? {
        // Reuse the same entry point the app uses, synchronously.
        let sem = DispatchSemaphore(value: 0)
        nonisolated(unsafe) var result: Survey?
        Task { @MainActor in
            result = try? await Backend().survey()
            sem.signal()
        }
        // Pump the main runloop so the Task can finish while we wait.
        while sem.wait(timeout: .now() + 0.05) == .timedOut {
            RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        return result
    }

    private static func render(screen: Screen, survey: Survey,
                               scheme: ColorScheme, to url: URL) {
        let view = SnapshotFrame(screen: screen, survey: survey)
            .environment(\.colorScheme, scheme)
            .frame(width: 1000, height: 700)

        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        guard let cg = renderer.cgImage else { return }
        let rep = NSBitmapImageRep(cgImage: cg)
        rep.size = NSSize(width: 1000, height: 700)
        guard let data = rep.representation(using: .png, properties: [:]) else { return }
        try? data.write(to: url)
    }
}

/// One screen with its chrome, wired to fixed state so it renders standalone.
private struct SnapshotFrame: View {
    @Environment(\.colorScheme) private var scheme
    let screen: Screen
    let survey: Survey

    @State private var brain = ""
    @State private var gateway = ""
    @State private var vision = "same"
    @State private var preset = ""

    private var pulls: [PullProgress] {
        let brainModel = survey.brains.first(where: \.recommended)
        return [
            PullProgress(key: "runtime", label: "MLX runtime and Metal kernels",
                         status: "done", pct: 100, downloaded_gb: 0.24,
                         total_gb: 0.24, detail: nil),
            PullProgress(key: brainModel?.key ?? "brain", label: brainModel?.label ?? "Brain",
                         status: "downloading", pct: 68,
                         downloaded_gb: (brainModel?.gb ?? 6) * 0.68,
                         total_gb: brainModel?.gb ?? 6, detail: nil),
            PullProgress(key: survey.compressor?.key ?? "c",
                         label: survey.compressor?.label ?? "Summariser",
                         status: "queued", pct: 0, downloaded_gb: 0,
                         total_gb: survey.compressor?.gb ?? 1.5, detail: nil),
        ]
    }

    var body: some View {
        Chrome(screen: screen) {
            body(for: screen)
        } footer: {
            if screen.showsPager {
                HStack {
                    SecondaryButton(title: "Back") {}
                    Spacer()
                    Pager(index: screen.pagerIndex)
                    Spacer()
                    PrimaryButton(title: screen == .downloading ? "Please wait" : "Continue",
                                  enabled: screen != .downloading) {}
                }
            }
        }
        .onAppear {
            brain = survey.brains.first(where: \.recommended)?.key ?? ""
            preset = survey.presets.first?.key ?? "alongside"
        }
    }

    @ViewBuilder
    private func body(for screen: Screen) -> some View {
        switch screen {
        case .welcome:      WelcomeScreen {}
        case .promise:      PromiseScreen(hardware: survey.hardware)
        case .textModel:
            TextModelScreen(survey: survey,
                            picked: .constant(survey.brains.first(where: \.recommended)?.key ?? ""),
                            gateway: .constant(""))
        case .visionModel:
            VisionScreen(survey: survey,
                         brainLabel: survey.brains.first(where: \.recommended)?.label ?? "",
                         vision: .constant("same"))
        case .memory:
            MemoryScreen(survey: survey,
                         preset: .constant(survey.presets.first?.key ?? "alongside"))
        case .downloading:  DownloadScreen(rows: pulls, failure: nil)
        case .launch:
            LaunchScreen(brainLabel: survey.brains.first(where: \.recommended)?.label ?? "",
                         ceiling: survey.presets.first?.limit_gb ?? 12,
                         ctx: survey.presets.first?.ctx ?? 16384) {}
        }
    }
}
