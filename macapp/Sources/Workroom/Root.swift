import SwiftUI

@MainActor
final class Flow: ObservableObject {
    @Published var screen: Screen = .welcome
    @Published var survey: Survey?
    @Published var loadError: String?
    @Published var needsSetup = false
    @Published var missingUV = false

    @Published var brain = ""
    @Published var gateway = ""
    @Published var vision = "same"
    @Published var preset = ""

    @Published var pulls: [PullProgress] = []
    @Published var pullFailure: String?
    @Published var pullFinished = false

    let backend = Backend()

    var brainLabel: String {
        survey?.catalogue.first { $0.key == brain }?.label
            ?? survey?.local_models.first { $0.id == brain }?.name
            ?? "your model"
    }

    var chosenPreset: Preset? { survey?.presets.first { $0.key == preset } }

    /// Downloading only applies to catalogue models. Choosing something already
    /// on the Mac, or a running gateway, skips straight to the handoff.
    var needsDownload: Bool {
        guard gateway.isEmpty else { return false }
        return survey?.catalogue.contains { $0.key == brain } ?? false
    }

    func loadSurvey() async {
        // Resolve the runtime before anything else: a downloaded app has no
        // repo above it, and "choose your folder" is a far better first screen
        // than a stack trace.
        missingUV = !Backend.uvInstalled
        needsSetup = missingUV || Backend.findRepo() == nil
        if needsSetup { return }

        do {
            let s = try await backend.survey()
            survey = s
            if brain.isEmpty {
                brain = s.brains.first(where: \.recommended)?.key ?? s.brains.first?.key ?? ""
            }
            if preset.isEmpty { preset = s.presets.first?.key ?? "alongside" }
        } catch {
            loadError = error.localizedDescription
        }
    }

    func advance() {
        guard let next = Screen(rawValue: screen.rawValue + 1) else { return }
        if next == .downloading && !needsDownload {
            go(.launch); return
        }
        go(next)
        if next == .downloading { startPull() }
    }

    func back() {
        guard let prev = Screen(rawValue: screen.rawValue - 1) else { return }
        if prev == .downloading { go(.memory); return }
        go(prev)
    }

    private func go(_ s: Screen) {
        withAnimation(Theme.ease) { screen = s }
    }

    func persist() {
        Task {
            try? await backend.save(brain: brain, preset: preset,
                                    vision: vision, gateway: gateway)
        }
    }

    func startPull() {
        guard let survey, pulls.isEmpty else { return }
        var keys = [brain]
        if let c = survey.compressor { keys.append(c.key) }

        // Seed a queued row per model so the screen has its full shape before
        // the first byte arrives, rather than growing as rows appear.
        pulls = keys.compactMap { key in
            survey.catalogue.first { $0.key == key }.map {
                PullProgress(key: $0.key, label: $0.label, status: "queued",
                             pct: 0, downloaded_gb: 0, total_gb: $0.gb, detail: nil)
            }
        }

        Task {
            do {
                for try await row in backend.pull(keys: keys) {
                    if let i = pulls.firstIndex(where: { $0.key == row.key }) {
                        pulls[i] = row
                    } else {
                        pulls.append(row)
                    }
                }
                pullFinished = true
                try? await Task.sleep(for: .milliseconds(600))
                if screen == .downloading { go(.launch) }
            } catch {
                pullFailure = error.localizedDescription
            }
        }
    }
}

struct RootView: View {
    @Environment(\.colorScheme) private var scheme
    @StateObject private var flow = Flow()

    var body: some View {
        Group {
            if flow.needsSetup {
                SetupView(missingUV: flow.missingUV) {
                    flow.needsSetup = false
                    Task { await flow.loadSurvey() }
                }
            } else if let survey = flow.survey {
                Chrome(screen: flow.screen) {
                    content(survey)
                        .transition(.asymmetric(
                            insertion: .opacity.combined(with: .offset(y: 14)),
                            removal: .opacity))
                        .id(flow.screen)
                } footer: {
                    footer
                }
            } else if let err = flow.loadError {
                failure(err)
            } else {
                loading
            }
        }
        .frame(width: 1000, height: 700)
        .background(Theme.bg(scheme))
        .background(WindowConfigurator())
        .task { await flow.loadSurvey() }
    }

    @ViewBuilder
    private func content(_ survey: Survey) -> some View {
        switch flow.screen {
        case .welcome:
            WelcomeScreen { flow.advance() }
        case .promise:
            PromiseScreen(hardware: survey.hardware)
        case .textModel:
            TextModelScreen(survey: survey, picked: $flow.brain, gateway: $flow.gateway)
        case .visionModel:
            VisionScreen(survey: survey, brainLabel: flow.brainLabel, vision: $flow.vision)
        case .memory:
            MemoryScreen(survey: survey, preset: $flow.preset)
        case .downloading:
            DownloadScreen(rows: flow.pulls, failure: flow.pullFailure)
        case .launch:
            LaunchScreen(brainLabel: flow.brainLabel,
                         ceiling: flow.chosenPreset?.limit_gb ?? 12,
                         ctx: flow.chosenPreset?.ctx ?? 16384) {
                flow.backend.launchCLI()
                NSApp.terminate(nil)
            }
        }
    }

    @ViewBuilder
    private var footer: some View {
        if flow.screen.showsPager {
            HStack {
                SecondaryButton(title: "Back") { flow.back() }
                Spacer()
                Pager(index: flow.screen.pagerIndex)
                Spacer()
                PrimaryButton(title: flow.screen == .downloading ? "Please wait" : "Continue",
                              enabled: flow.screen != .downloading) {
                    if flow.screen == .memory { flow.persist() }
                    flow.advance()
                }
            }
        } else {
            EmptyView()
        }
    }

    private var loading: some View {
        VStack(spacing: 14) {
            ProgressView().controlSize(.small)
            Text("Looking at this Mac…")
                .font(Theme.ui(13)).foregroundStyle(Theme.ink3(scheme))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func failure(_ message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 28, weight: .light))
                .foregroundStyle(Theme.accent(scheme))
            Text("Workroom could not read this Mac")
                .font(Theme.display(28)).foregroundStyle(Theme.ink(scheme))
            Text(message)
                .font(Theme.mono(12)).foregroundStyle(Theme.ink2(scheme))
                .multilineTextAlignment(.center).frame(maxWidth: 520)
            Text("The app runs the Python runtime in the Workroom repo. Check that `uv sync` has been run there.")
                .font(Theme.ui(13)).foregroundStyle(Theme.ink3(scheme))
            SecondaryButton(title: "Choose a different folder") {
                flow.needsSetup = true
            }
            .padding(.top, 6)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }
}
