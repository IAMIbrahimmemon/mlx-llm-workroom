import SwiftUI

// MARK: - 5 · Memory ceiling

struct MemoryScreen: View {
    @Environment(\.colorScheme) private var scheme
    let survey: Survey
    @Binding var preset: String

    private var current: Preset? {
        survey.presets.first { $0.key == preset } ?? survey.presets.first
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Headline(title: "How much of this Mac gets to think?",
                     subtitle: "MLX keeps the model in unified memory, which your apps share. Setting a ceiling is how you decide who wins when both want it at once.")
                .padding(.bottom, 24)

            if let c = current { splitBar(c) }

            HStack(spacing: 14) {
                ForEach(survey.presets) { p in
                    presetCard(p)
                }
            }

            Spacer(minLength: 12)
            if let c = current { sysctlNote(c) }
        }
    }

    /// The whole point of the screen: you can see what you are giving away.
    private func splitBar(_ c: Preset) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            GeometryReader { geo in
                let frac = Double(c.limit_gb) / Double(max(c.total_gb, 1))
                HStack(spacing: 0) {
                    HStack {
                        Text("Workroom  ·  \(c.limit_gb) GB")
                            .font(Theme.ui(13, .semibold)).foregroundStyle(.white)
                            .padding(.leading, 16)
                        Spacer(minLength: 0)
                    }
                    .frame(width: max(120, geo.size.width * frac), height: geo.size.height)
                    .background(Theme.accent(scheme))

                    HStack {
                        Spacer(minLength: 0)
                        Text("\(c.total_gb - c.limit_gb) GB for macOS and your apps")
                            .font(Theme.ui(13, .medium))
                            .foregroundStyle(Theme.ink2(scheme))
                            .padding(.trailing, 16)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Theme.surf2(scheme))
                }
                .animation(Theme.ease, value: c.limit_gb)
            }
            .frame(height: 46)
            .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 11, style: .continuous)
                .stroke(Theme.line(scheme), lineWidth: 1))

            HStack {
                Text("0")
                Spacer()
                Text("\(c.total_gb) GB")
            }
            .font(Theme.mono(11.5)).foregroundStyle(Theme.ink3(scheme))
        }
        .padding(.bottom, 26)
    }

    private func presetCard(_ p: Preset) -> some View {
        let selected = preset == p.key
        return Button {
            withAnimation(Theme.ease) { preset = p.key }
        } label: {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 11) {
                    Radio(selected: selected)
                    Text(p.title).font(Theme.ui(16, .semibold))
                        .foregroundStyle(Theme.ink(scheme))
                    if !p.needs_sysctl {
                        Tag(text: "Recommended", color: Theme.accent(scheme), filled: false)
                    }
                }
                .padding(.bottom, 12)

                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("\(p.limit_gb)").font(Theme.ui(34, .semibold))
                    Text("GB ceiling").font(Theme.ui(16, .medium))
                        .foregroundStyle(Theme.ink3(scheme))
                }
                .foregroundStyle(Theme.ink(scheme))
                .padding(.bottom, 12)

                Text(p.desc)
                    .font(Theme.ui(13.5)).foregroundStyle(Theme.ink2(scheme))
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.bottom, 14)

                Divider().overlay(selected ? Theme.accent(scheme).opacity(0.22) : Theme.line(scheme))
                HStack(spacing: 16) {
                    Text(p.tps); Text(p.ctxText)
                }
                .font(Theme.mono(12)).foregroundStyle(Theme.ink3(scheme))
                .padding(.top, 13)
            }
            .padding(22)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(selected ? Theme.accentSoft(scheme) : Theme.surf(scheme)))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(selected ? Theme.accent(scheme) : Theme.line(scheme), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    /// Only one of the presets crosses what macOS hands a single process, so
    /// only one of them ever mentions a password.
    private func sysctlNote(_ c: Preset) -> some View {
        HStack(spacing: 12) {
            Image(systemName: c.needs_sysctl ? "terminal" : "checkmark.circle")
                .font(.system(size: 13))
                .foregroundStyle(c.needs_sysctl ? Theme.ink3(scheme) : Theme.ok(scheme))
            Text(c.needs_sysctl ? c.sysctl_command : "no system change needed")
                .font(Theme.mono(12.5))
                .foregroundStyle(c.needs_sysctl ? Theme.ink2(scheme) : Theme.ok(scheme))
            Spacer()
            Text(c.needs_sysctl
                 ? "Asks for your admin password once per boot"
                 : "macOS already allows this much. Nothing to approve.")
                .font(Theme.ui(12.5))
                .foregroundStyle(c.needs_sysctl ? Theme.ink3(scheme) : Theme.ok(scheme))
        }
        .padding(.horizontal, 18).padding(.vertical, 14)
        .background(RoundedRectangle(cornerRadius: 11, style: .continuous)
            .fill(Theme.surf2(scheme)))
        .padding(.bottom, 22)
        .animation(Theme.quick, value: c.needs_sysctl)
    }
}

// MARK: - 6 · Downloading

struct DownloadScreen: View {
    @Environment(\.colorScheme) private var scheme
    let rows: [PullProgress]
    let failure: String?

    private var totalGB: Double { rows.reduce(0) { $0 + $1.total_gb } }
    private var gotGB: Double { rows.reduce(0) { $0 + $1.downloaded_gb } }
    private var doneCount: Int { rows.filter(\.isDone).count }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Headline(title: "Getting things ready.",
                     subtitle: "You can leave this running. Downloads carry on and pick up where they stopped if the connection drops.")
                .padding(.bottom, 26)

            VStack(alignment: .leading, spacing: 11) {
                HStack {
                    Text("\(doneCount) of \(rows.count) complete").font(Theme.ui(14, .medium))
                        .foregroundStyle(Theme.ink(scheme))
                    Spacer()
                    Text(String(format: "%.2f GB of %.2f GB", gotGB, totalGB))
                        .font(Theme.mono(13)).foregroundStyle(Theme.ink3(scheme))
                }
                Track(fraction: totalGB > 0 ? gotGB / totalGB : 0, color: Theme.accent(scheme))
            }
            .padding(.bottom, 30)

            VStack(spacing: 12) {
                ForEach(rows, id: \.key) { row in
                    DownloadRow(row: row)
                }
            }

            if let failure {
                Hint(text: failure).padding(.top, 16)
            }
            Spacer(minLength: 0)
        }
    }
}

struct Track: View {
    @Environment(\.colorScheme) private var scheme
    let fraction: Double
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.surf2(scheme))
                Capsule().fill(color)
                    .frame(width: max(0, geo.size.width * min(1, max(0, fraction))))
                    .animation(Theme.ease, value: fraction)
            }
        }
        .frame(height: 4)
    }
}

struct DownloadRow: View {
    @Environment(\.colorScheme) private var scheme
    let row: PullProgress
    @State private var pulsing = false

    var body: some View {
        HStack(spacing: 15) {
            icon
            VStack(alignment: .leading, spacing: 9) {
                HStack(spacing: 9) {
                    Text(row.label).font(Theme.ui(15, .semibold))
                        .foregroundStyle(Theme.ink(scheme))
                    Text(String(format: "%.2f GB", row.total_gb))
                        .font(Theme.mono(12)).foregroundStyle(Theme.ink3(scheme))
                }
                Track(fraction: row.isDone ? 1 : row.pct / 100,
                      color: row.isDone ? Theme.ok(scheme) : Theme.accent(scheme))
            }
            Text(status)
                .font(Theme.mono(12.5, .medium))
                .foregroundStyle(row.isDone ? Theme.ok(scheme)
                                 : row.isError ? .red : Theme.ink2(scheme))
                .frame(width: 130, alignment: .trailing)
        }
        .padding(.horizontal, 20).padding(.vertical, 16)
        .background(RoundedRectangle(cornerRadius: 13, style: .continuous)
            .fill(active ? Theme.accentSoft(scheme) : Theme.surf(scheme)))
        .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous)
            .stroke(active ? Theme.accent(scheme) : Theme.line(scheme), lineWidth: 1))
        .opacity(row.status == "queued" ? 0.6 : 1)
    }

    private var active: Bool { row.status == "downloading" }

    private var status: String {
        if row.isDone { return "Ready" }
        if row.isError { return "Failed" }
        if row.status == "queued" { return "Queued" }
        return String(format: "%.0f%%", row.pct)
    }

    @ViewBuilder private var icon: some View {
        if row.isDone {
            Image(systemName: "checkmark.circle").font(.system(size: 18))
                .foregroundStyle(Theme.ok(scheme))
        } else if row.isError {
            Image(systemName: "exclamationmark.circle").font(.system(size: 18))
                .foregroundStyle(.red)
        } else if active {
            Circle().fill(Theme.accent(scheme)).frame(width: 9, height: 9)
                .scaleEffect(pulsing ? 1.35 : 0.85)
                .frame(width: 20)
                .onAppear {
                    withAnimation(.easeInOut(duration: 1.1).repeatForever(autoreverses: true)) {
                        pulsing = true
                    }
                }
        } else {
            Image(systemName: "clock").font(.system(size: 17))
                .foregroundStyle(Theme.ink3(scheme))
        }
    }
}

// MARK: - 7 · Launch

struct LaunchScreen: View {
    @Environment(\.colorScheme) private var scheme
    let brainLabel: String
    let ceiling: Int
    let ctx: Int
    let onLaunch: () -> Void
    @State private var caret = true

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            ZStack {
                Circle().fill(Theme.ok(scheme).opacity(0.14)).frame(width: 54, height: 54)
                Circle().stroke(Theme.ok(scheme), lineWidth: 1).frame(width: 38, height: 38)
                Image(systemName: "checkmark").font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Theme.ok(scheme))
            }
            .rise(0)
            .padding(.bottom, 26)

            Text("You're set.")
                .font(Theme.display(52)).foregroundStyle(Theme.ink(scheme))
                .rise(1).padding(.bottom, 12)

            Text("Workroom lives in your terminal from here. Ask it for something in plain English and watch what it does.")
                .font(Theme.ui(16)).foregroundStyle(Theme.ink2(scheme))
                .multilineTextAlignment(.center).lineSpacing(4)
                .frame(maxWidth: 470)
                .rise(2).padding(.bottom, 26)

            HStack(spacing: 9) {
                ForEach(["Accessibility", "Screen Recording", "\(ceiling) GB reserved"], id: \.self) { t in
                    HStack(spacing: 7) {
                        Image(systemName: "checkmark").font(.system(size: 10, weight: .bold))
                            .foregroundStyle(Theme.ok(scheme))
                        Text(t).font(Theme.ui(12.5, .medium)).foregroundStyle(Theme.ink(scheme))
                    }
                    .padding(.horizontal, 13).padding(.vertical, 6)
                    .background(Capsule().fill(Theme.surf(scheme)))
                    .overlay(Capsule().stroke(Theme.line(scheme), lineWidth: 1))
                }
            }
            .rise(3).padding(.bottom, 28)

            terminal.rise(4).padding(.bottom, 28)

            HStack(spacing: 14) {
                PrimaryButton(title: "Open Workroom in Terminal", action: onLaunch)
                SecondaryButton(title: "Show me around first") {}
            }
            .rise(5)

            Text("Sessions and notes are written to ~/.workroom as plain markdown. Yours to read or delete.")
                .font(Theme.ui(12.5)).foregroundStyle(Theme.ink3(scheme))
                .rise(6).padding(.top, 22)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 30)
    }

    private var terminal: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 7) {
                ForEach(0..<3, id: \.self) { _ in
                    Circle().fill(Color.hex(0x3A3630)).frame(width: 9, height: 9)
                }
            }
            .padding(.bottom, 12)

            line("$ ", "workroom", Color.hex(0x8C857A), Color.hex(0xE8E3DA))
            Text("workroom 1.0 · \(brainLabel) 4-bit MLX · \(ceiling) GB ceiling · \(ctx / 1024)k ctx")
                .foregroundStyle(Color.hex(0xE08A5E))
            Text("screen and accessibility granted")
                .foregroundStyle(Color.hex(0x5FB98F))
            Spacer().frame(height: 10)
            HStack(spacing: 0) {
                Text("› ").foregroundStyle(Color.hex(0xE08A5E))
                Text("tidy up ~/Downloads and leave me a one-page summary")
                    .foregroundStyle(Color.hex(0xE8E3DA))
                Rectangle().fill(Color.hex(0xE8E3DA))
                    .frame(width: 8, height: 15).opacity(caret ? 1 : 0)
                    .padding(.leading, 3)
            }
        }
        .font(Theme.mono(13))
        .frame(maxWidth: 660, alignment: .leading)
        .padding(.horizontal, 22).padding(.vertical, 20)
        .background(RoundedRectangle(cornerRadius: 14, style: .continuous)
            .fill(Color.hex(0x14130F)))
        .shadow(color: .black.opacity(0.28), radius: 20, y: 12)
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.55, repeats: true) { _ in
                Task { @MainActor in caret.toggle() }
            }
        }
    }

    private func line(_ a: String, _ b: String, _ ca: Color, _ cb: Color) -> some View {
        HStack(spacing: 0) {
            Text(a).foregroundStyle(ca)
            Text(b).foregroundStyle(cb)
        }
    }
}
