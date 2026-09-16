import SwiftUI

// Shared chrome. Every onboarding screen is built from these so spacing and
// weight stay identical across the flow.

struct Chrome<Content: View, Footer: View>: View {
    @Environment(\.colorScheme) private var scheme
    let screen: Screen
    @ViewBuilder var content: Content
    @ViewBuilder var footer: Footer

    var body: some View {
        VStack(spacing: 0) {
            content
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(.horizontal, 72)
                // The window hides its titlebar, so the traffic-light buttons
                // float over the content. This is the room they need.
                .padding(.top, 46)

            if screen.showsPager {
                Divider().overlay(Theme.line(scheme))
                footer.padding(.horizontal, 72).padding(.vertical, 18)
            } else {
                footer
            }
        }
        .background(Theme.bg(scheme))
    }
}

struct Pager: View {
    @Environment(\.colorScheme) private var scheme
    let index: Int

    var body: some View {
        HStack(spacing: 7) {
            ForEach(0..<Screen.pagerCount, id: \.self) { i in
                Circle()
                    .fill(i == index ? Theme.accent(scheme) : Theme.line2(scheme))
                    .frame(width: 6, height: 6)
                    .scaleEffect(i == index ? 1.15 : 1)
                    .animation(Theme.quick, value: index)
            }
        }
    }
}

struct PrimaryButton: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    var enabled = true
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(Theme.ui(14, .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 24)
                .frame(height: 42)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(Theme.accent(scheme).opacity(enabled ? (hovering ? 0.9 : 1) : 0.35))
                )
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .onHover { hovering = $0 }
        .animation(Theme.quick, value: hovering)
    }
}

struct SecondaryButton: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(Theme.ui(14, .medium))
                .foregroundStyle(Theme.ink2(scheme))
                .padding(.horizontal, 18)
                .frame(height: 42)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(Theme.line2(scheme), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}

struct Headline: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    let subtitle: String
    var size: CGFloat = 44

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(title)
                .font(Theme.display(size))
                .foregroundStyle(Theme.ink(scheme))
                .fixedSize(horizontal: false, vertical: true)
            Text(subtitle)
                .font(Theme.ui(15))
                .foregroundStyle(Theme.ink2(scheme))
                .lineSpacing(3)
                .frame(maxWidth: 560, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// The selectable row used by both model pickers. `trailing` carries the
/// short right-aligned status: a size, "Connected", "Needs 32 GB".
struct PickerRow: View {
    @Environment(\.colorScheme) private var scheme
    let title: String
    let meta: String
    let blurb: String
    let trailing: String
    var badge: String? = nil
    var chip: String? = nil
    var selected = false
    var enabled = true
    var trailingIsGood = false
    let action: () -> Void

    var body: some View {
        Button(action: { if enabled { action() } }) {
            HStack(alignment: .top, spacing: 15) {
                Radio(selected: selected)
                    .padding(.top, 2)

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 9) {
                        Text(title).font(Theme.ui(15.5, .semibold))
                            .foregroundStyle(Theme.ink(scheme))
                        if let badge {
                            Tag(text: badge, color: Theme.accent(scheme), filled: false)
                        }
                        if let chip {
                            Tag(text: chip,
                                color: selected ? Theme.accent(scheme) : Theme.ink3(scheme),
                                filled: false)
                        }
                        Text(meta).font(Theme.mono(12.5))
                            .foregroundStyle(Theme.ink3(scheme))
                    }
                    Text(blurb)
                        .font(Theme.ui(13.5))
                        .foregroundStyle(Theme.ink2(scheme))
                        .lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Text(trailing)
                    .font(Theme.mono(12.5, .medium))
                    .foregroundStyle(trailingIsGood ? Theme.ok(scheme) : Theme.ink3(scheme))
                    .padding(.top, 3)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: 13, style: .continuous)
                    .fill(selected ? Theme.accentSoft(scheme) : Theme.surf(scheme))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 13, style: .continuous)
                    .stroke(selected ? Theme.accent(scheme) : Theme.line(scheme), lineWidth: 1)
            )
            .opacity(enabled ? 1 : 0.45)
        }
        .buttonStyle(.plain)
        .animation(Theme.quick, value: selected)
    }
}

struct Radio: View {
    @Environment(\.colorScheme) private var scheme
    let selected: Bool

    var body: some View {
        ZStack {
            Circle()
                .stroke(selected ? Theme.accent(scheme) : Theme.line2(scheme), lineWidth: 1.5)
                .frame(width: 19, height: 19)
            if selected {
                Circle().fill(Theme.accent(scheme)).frame(width: 19, height: 19)
                Circle().fill(.white).frame(width: 7, height: 7)
            }
        }
        .animation(Theme.quick, value: selected)
    }
}

struct Tag: View {
    @Environment(\.colorScheme) private var scheme
    let text: String
    let color: Color
    var filled: Bool

    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(filled ? .white : color)
            .padding(.horizontal, 7).padding(.vertical, 2)
            .background(
                Capsule().fill(filled ? color : .clear)
            )
            .overlay(Capsule().stroke(color, lineWidth: filled ? 0 : 1))
    }
}

/// The segmented control on the text-model screen: Download / On this Mac /
/// Gateway. The selection indicator slides rather than blinking.
struct Segmented: View {
    @Environment(\.colorScheme) private var scheme
    let options: [(id: String, label: String)]
    @Binding var selection: String
    @Namespace private var ns

    var body: some View {
        HStack(spacing: 2) {
            ForEach(options, id: \.id) { opt in
                Button {
                    withAnimation(Theme.quick) { selection = opt.id }
                } label: {
                    Text(opt.label)
                        .font(Theme.ui(13, .medium))
                        .foregroundStyle(selection == opt.id ? Theme.ink(scheme) : Theme.ink3(scheme))
                        .padding(.horizontal, 15)
                        .frame(height: 32)
                        .background {
                            if selection == opt.id {
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(Theme.surf(scheme))
                                    .shadow(color: .black.opacity(0.12), radius: 2, y: 1)
                                    .matchedGeometryEffect(id: "seg", in: ns)
                            }
                        }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(RoundedRectangle(cornerRadius: 10, style: .continuous)
            .fill(Theme.surf2(scheme)))
    }
}

struct Hint: View {
    @Environment(\.colorScheme) private var scheme
    let text: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "info.circle")
                .font(.system(size: 12))
            Text(text).font(Theme.ui(12.5))
        }
        .foregroundStyle(Theme.ink3(scheme))
        .fixedSize(horizontal: false, vertical: true)
    }
}
