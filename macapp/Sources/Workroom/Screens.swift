import SwiftUI

// MARK: - 1 · Welcome

struct WelcomeScreen: View {
    @Environment(\.colorScheme) private var scheme
    let onNext: () -> Void
    @State private var breathing = false

    var body: some View {
        HStack(spacing: 64) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 10) {
                    Image(systemName: "square.on.square.dashed")
                        .font(.system(size: 18, weight: .light))
                        .foregroundStyle(Theme.accent(scheme))
                    Text("Workroom").font(Theme.ui(16, .semibold))
                        .foregroundStyle(Theme.ink(scheme))
                    Tag(text: "Local", color: Theme.ink3(scheme), filled: false)
                }
                .rise(0)
                .padding(.bottom, 34)

                Text("AI should be\nsimple.")
                    .font(Theme.display(72))
                    .foregroundStyle(Theme.ink(scheme))
                    .lineSpacing(-6)
                    .rise(1)
                    .padding(.bottom, 22)

                Text("One capable model, running on your own Mac. No account to make, no key to paste, no meter running while you think.")
                    .font(Theme.ui(17))
                    .foregroundStyle(Theme.ink2(scheme))
                    .lineSpacing(4)
                    .frame(maxWidth: 430, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .rise(2)
                    .padding(.bottom, 38)

                HStack(spacing: 18) {
                    PrimaryButton(title: "Get started", action: onNext)
                    Text("About two minutes")
                        .font(Theme.ui(14)).foregroundStyle(Theme.ink3(scheme))
                }
                .rise(3)
            }

            // A slow pulse standing in for the model resident in memory.
            ZStack {
                ForEach([0, 44, 88], id: \.self) { inset in
                    Circle()
                        .stroke(inset == 88 ? Theme.line2(scheme) : Theme.line(scheme), lineWidth: 1)
                        .padding(CGFloat(inset))
                }
                Circle()
                    .fill(Theme.accent(scheme).opacity(0.16))
                    .frame(width: 124, height: 124)
                    .scaleEffect(breathing ? 1.3 : 0.92)
                    .opacity(breathing ? 0 : 0.5)
                Circle()
                    .fill(Theme.accent(scheme))
                    .frame(width: 74, height: 74)
                    .scaleEffect(breathing ? 1.05 : 1)
                    .shadow(color: Theme.accent(scheme).opacity(0.34), radius: 18, y: 8)
                VStack {
                    Spacer()
                    Text("APPLE MLX · ON DEVICE")
                        .font(.system(size: 11)).tracking(1)
                        .foregroundStyle(Theme.ink3(scheme))
                }
            }
            .frame(width: 300, height: 300)
            .rise(2)
            .onAppear {
                withAnimation(.easeInOut(duration: 2.3).repeatForever(autoreverses: true)) {
                    breathing = true
                }
            }
        }
        .frame(maxHeight: .infinity)
        .padding(.bottom, 40)
    }
}

// MARK: - 2 · Why local

struct PromiseScreen: View {
    @Environment(\.colorScheme) private var scheme
    let hardware: Hardware

    private let beats: [(String, String, String)] = [
        ("lock.shield", "Everything stays here",
         "Screenshots, keystrokes and file contents are handled in memory on your Mac. There is no server to trust."),
        ("moon", "Awake when you aren't",
         "Hand it a long job before bed. It keeps a plain-text log of what it did and what it decided."),
        ("cube", "One model, not five",
         "The same model reads your screen and writes your code. Less to download, less to go wrong."),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Runs on your Mac.\nWorks all night.")
                .font(Theme.display(58))
                .foregroundStyle(Theme.ink(scheme))
                .lineSpacing(-4)
                .rise(0)
                .padding(.bottom, 18)

            Text("Workroom reads the screen, runs commands and edits files the way you would — except it does it at 3am, and nothing it sees ever leaves this machine.")
                .font(Theme.ui(16))
                .foregroundStyle(Theme.ink2(scheme))
                .lineSpacing(4)
                .frame(maxWidth: 520, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
                .rise(1)
                .padding(.bottom, 40)

            Divider().overlay(Theme.line(scheme))
            HStack(alignment: .top, spacing: 0) {
                ForEach(Array(beats.enumerated()), id: \.offset) { i, beat in
                    VStack(alignment: .leading, spacing: 0) {
                        Image(systemName: beat.0)
                            .font(.system(size: 18, weight: .light))
                            .foregroundStyle(Theme.accent(scheme))
                            .padding(.bottom, 14)
                        Text(beat.1).font(Theme.ui(16, .semibold))
                            .foregroundStyle(Theme.ink(scheme))
                            .padding(.bottom, 8)
                        Text(beat.2).font(Theme.ui(13.5))
                            .foregroundStyle(Theme.ink2(scheme))
                            .lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.trailing, i < 2 ? 30 : 0)
                    .padding(.leading, i > 0 ? 30 : 0)
                    .padding(.vertical, 24)
                    .overlay(alignment: .trailing) {
                        if i < 2 { Rectangle().fill(Theme.line(scheme)).frame(width: 1) }
                    }
                    .rise(2 + i)
                }
            }

            Spacer(minLength: 12)

            HStack {
                HStack(spacing: 13) {
                    Circle().fill(Theme.ok(scheme)).frame(width: 9, height: 9)
                    Text("This Mac can run it").font(Theme.ui(14, .medium))
                        .foregroundStyle(Theme.ink(scheme))
                }
                Spacer()
                Text(hardware.summary + " · MLX ready")
                    .font(Theme.mono(12.5))
                    .foregroundStyle(Theme.ink2(scheme))
            }
            .padding(.horizontal, 20).padding(.vertical, 16)
            .background(RoundedRectangle(cornerRadius: 13, style: .continuous)
                .fill(Theme.surf(scheme)))
            .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Theme.line(scheme), lineWidth: 1))
            .rise(5)
            .padding(.bottom, 22)
        }
    }
}

// MARK: - 3 · Text model

struct TextModelScreen: View {
    @Environment(\.colorScheme) private var scheme
    let survey: Survey
    @Binding var picked: String
    @Binding var gateway: String
    @State private var tab = "download"

    private var hint: String {
        switch tab {
        case "local":
            survey.local_models.isEmpty
                ? "Nothing found yet. Anything you pull with Ollama or download from Hugging Face shows up here."
                : "\(survey.local_models.count) already on this Mac. Workroom will use them where they are."
        case "gateway":
            "Gateways are reached over plain HTTP on localhost. Nothing leaves the machine."
        default:
            "From huggingface.co into ~/.cache/huggingface. The recommendation also brings a small summariser that keeps long sessions from filling up."
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .bottom) {
                Headline(title: "Choose a brain.",
                         subtitle: "Workroom needs one text model. If you have no idea what any of this means, take the recommendation — it is the right answer for this Mac.")
                Spacer(minLength: 24)
                Segmented(options: [("download", "Download"),
                                    ("local", "On this Mac"),
                                    ("gateway", "Gateway")],
                          selection: $tab)
            }
            .padding(.bottom, 22)

            VStack(spacing: 10) {
                switch tab {
                case "local":   localRows
                case "gateway": gatewayRows
                default:        downloadRows
                }
            }
            .animation(Theme.ease, value: tab)

            Hint(text: hint).padding(.top, 16)
            Spacer(minLength: 0)
        }
    }

    private var downloadRows: some View {
        ForEach(survey.brains) { m in
            PickerRow(title: m.label, meta: m.sizeText, blurb: m.runnable ? m.blurb : m.reason,
                      trailing: m.runnable ? m.tps : "Too large",
                      badge: m.recommended ? "Recommended" : nil,
                      selected: picked == m.key, enabled: m.runnable) {
                picked = m.key; gateway = ""
            }
        }
    }

    private var localRows: some View {
        Group {
            if survey.local_models.isEmpty {
                EmptyRow(text: "No models found on this Mac yet.")
            } else {
                ForEach(survey.local_models.prefix(4)) { m in
                    PickerRow(title: m.name,
                              meta: String(format: "%@  ·  %.1f GB", m.sourceLabel, m.gb),
                              blurb: m.vision == true
                                ? "Found on this Mac. Can read your screen as well as write text."
                                : "Found on this Mac. Text and tools; it cannot see your screen.",
                              trailing: "Installed",
                              selected: picked == m.id, enabled: true) {
                        picked = m.id; gateway = ""
                    }
                }
            }
        }
    }

    private var gatewayRows: some View {
        ForEach(survey.gateways) { g in
            PickerRow(title: g.label, meta: g.base_url,
                      blurb: g.reachable
                        ? "Answering right now. Workroom can borrow any model it has loaded."
                        : g.detail,
                      trailing: g.reachable ? "Connected" : "Not found",
                      selected: gateway == g.key, enabled: g.reachable,
                      trailingIsGood: g.reachable) {
                gateway = g.key
            }
        }
    }
}

struct EmptyRow: View {
    @Environment(\.colorScheme) private var scheme
    let text: String
    var body: some View {
        Text(text)
            .font(Theme.ui(13.5)).foregroundStyle(Theme.ink3(scheme))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
            .background(RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Theme.line(scheme), style: StrokeStyle(lineWidth: 1, dash: [4, 4])))
    }
}

// MARK: - 4 · Vision model

struct VisionScreen: View {
    let survey: Survey
    let brainLabel: String
    @Binding var vision: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Headline(title: "Give it eyes.",
                     subtitle: "Workroom only looks at the screen when it cannot work out the answer from the accessibility tree — a few times an hour, not a few times a second. The model you already picked can do this itself.")
                .padding(.bottom, 20)

            VStack(spacing: 10) {
                PickerRow(title: brainLabel, meta: "nothing to download",
                          blurb: "The model you just chose reads screenshots natively. This is the whole reason we picked it.",
                          trailing: "Recommended", chip: "Included",
                          selected: vision == "same", trailingIsGood: true) { vision = "same" }

                PickerRow(title: "Qwen3-VL-8B-Instruct", meta: "4-bit MLX  ·  4.2 GB",
                          blurb: "A dedicated pair of eyes. Sharper on dense interfaces, at the cost of memory it holds all day.",
                          trailing: "+4.2 GB", chip: "Download",
                          selected: vision == "vl") { vision = "vl" }

                if let gw = survey.liveGateways.first {
                    PickerRow(title: gw.label, meta: gw.base_url,
                              blurb: "Borrow a vision model from the gateway already running on this Mac. Costs you no extra memory.",
                              trailing: "Connected", chip: "Gateway",
                              selected: vision == "gateway", trailingIsGood: true) { vision = "gateway" }
                }
            }

            Hint(text: "A separate vision model is a second set of weights held in memory. Only worth it if the recommendation struggles.")
                .padding(.top, 16)
            Spacer(minLength: 0)
        }
    }
}
