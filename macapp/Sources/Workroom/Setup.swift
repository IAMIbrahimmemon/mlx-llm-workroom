import SwiftUI
import AppKit

/// Shown when the app cannot reach the Python runtime.
///
/// A downloaded `.app` in /Applications has no repo above it, so this is the
/// normal first-run state for anyone who took the release rather than cloning.
/// It has to be actionable, not an error message.
struct SetupView: View {
    @Environment(\.colorScheme) private var scheme
    let missingUV: Bool
    let onResolved: () -> Void

    @State private var copied = false

    private var cloneCommand: String {
        "git clone https://github.com/IAMIbrahimmemon/mlx-llm-workroom"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "square.on.square.dashed")
                    .font(.system(size: 18, weight: .light))
                    .foregroundStyle(Theme.accent(scheme))
                Text("Workroom").font(Theme.ui(16, .semibold))
                    .foregroundStyle(Theme.ink(scheme))
            }
            .rise(0)
            .padding(.bottom, 30)

            Text(missingUV ? "One thing first." : "Where did you put it?")
                .font(Theme.display(52))
                .foregroundStyle(Theme.ink(scheme))
                .rise(1)
                .padding(.bottom, 14)

            Text(missingUV
                 ? "Workroom runs its model through a Python runtime managed by uv. It is a single command to install, and nothing else is needed."
                 : "The app is the front door; the model and tools live in the Workroom repo. Point it at your copy, or clone one.")
                .font(Theme.ui(16))
                .foregroundStyle(Theme.ink2(scheme))
                .lineSpacing(4)
                .frame(maxWidth: 520, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
                .rise(2)
                .padding(.bottom, 30)

            CommandBox(text: missingUV
                       ? "curl -LsSf https://astral.sh/uv/install.sh | sh"
                       : cloneCommand,
                       copied: $copied)
                .rise(3)
                .padding(.bottom, 26)

            HStack(spacing: 14) {
                if !missingUV {
                    PrimaryButton(title: "Choose the folder…") { pick() }
                }
                SecondaryButton(title: missingUV ? "I've installed it" : "Try again") {
                    onResolved()
                }
            }
            .rise(4)

            Text(missingUV
                 ? "Already have uv? Make sure it is in /opt/homebrew/bin, /usr/local/bin or ~/.local/bin."
                 : "Looks for agent/bridge.py inside the folder you pick. Remembered after the first time.")
                .font(Theme.ui(12.5))
                .foregroundStyle(Theme.ink3(scheme))
                .rise(5)
                .padding(.top, 20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .padding(.horizontal, 72)
        .padding(.top, 46)
        .padding(.bottom, 40)
        .background(Theme.bg(scheme))
    }

    private func pick() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Use this folder"
        panel.message = "Select your mlx-llm-workroom folder"
        guard panel.runModal() == .OK, let url = panel.url else { return }

        // Accept the repo itself, or a parent that contains it.
        let candidates = [url, url.appendingPathComponent("mlx-llm-workroom")]
        for c in candidates
        where FileManager.default.fileExists(atPath: c.appendingPathComponent("agent/bridge.py").path) {
            Backend.remember(repo: c)
            onResolved()
            return
        }
        let alert = NSAlert()
        alert.messageText = "That folder does not look like Workroom"
        alert.informativeText = "Pick the folder containing agent/bridge.py — the one you cloned."
        alert.runModal()
    }
}

struct CommandBox: View {
    @Environment(\.colorScheme) private var scheme
    let text: String
    @Binding var copied: Bool

    var body: some View {
        HStack(spacing: 12) {
            Text("$").foregroundStyle(Color.hex(0x8C857A))
            Text(text)
                .foregroundStyle(Color.hex(0xE8E3DA))
                .textSelection(.enabled)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Spacer(minLength: 12)
            Button {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(text, forType: .string)
                withAnimation(Theme.quick) { copied = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
                    withAnimation(Theme.quick) { copied = false }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: copied ? "checkmark" : "doc.on.doc")
                        .font(.system(size: 11, weight: .semibold))
                    Text(copied ? "Copied" : "Copy").font(Theme.ui(12, .medium))
                }
                .foregroundStyle(copied ? Color.hex(0x5FB98F) : Color.hex(0xB4ADA4))
            }
            .buttonStyle(.plain)
        }
        .font(Theme.mono(13))
        .padding(.horizontal, 20).padding(.vertical, 17)
        .frame(maxWidth: 620, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 13, style: .continuous)
            .fill(Color.hex(0x14130F)))
    }
}
