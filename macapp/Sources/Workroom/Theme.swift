import SwiftUI

/// The design system, lifted from `design/*.dc.html` so the app and the
/// artboards cannot drift apart. Every value here has a counterpart in the
/// `.workroom` / `.workroom.dark` custom-property blocks.
enum Theme {
    // Warm neutrals rather than pure greys: the whole palette sits slightly
    // to the red side of neutral so the ember accent belongs to it.
    static func bg(_ s: ColorScheme) -> Color      { s == .dark ? .hex(0x131211) : .hex(0xFBFAF8) }
    static func surf(_ s: ColorScheme) -> Color    { s == .dark ? .hex(0x1C1A18) : .hex(0xFFFFFF) }
    static func surf2(_ s: ColorScheme) -> Color   { s == .dark ? .hex(0x232120) : .hex(0xF4F1EC) }
    static func ink(_ s: ColorScheme) -> Color     { s == .dark ? .hex(0xF3EFE9) : .hex(0x1B1917) }
    static func ink2(_ s: ColorScheme) -> Color    { s == .dark ? .hex(0xB4ADA4) : .hex(0x56504A) }
    static func ink3(_ s: ColorScheme) -> Color    { s == .dark ? .hex(0x7E776E) : .hex(0x8C857D) }
    static func line(_ s: ColorScheme) -> Color    { s == .dark ? .hex(0x2C2927) : .hex(0xE7E2DA) }
    static func line2(_ s: ColorScheme) -> Color   { s == .dark ? .hex(0x3A3633) : .hex(0xD6CFC4) }
    static func accent(_ s: ColorScheme) -> Color  { s == .dark ? .hex(0xE08A5E) : .hex(0xC0603A) }
    static func accentSoft(_ s: ColorScheme) -> Color { s == .dark ? .hex(0x2A1E18) : .hex(0xFBEFE8) }
    static func ok(_ s: ColorScheme) -> Color      { s == .dark ? .hex(0x5FB98F) : .hex(0x2E7D5B) }

    /// New York stands in for Instrument Serif: the same editorial weight,
    /// and it ships with the OS so nothing has to be embedded.
    static func display(_ size: CGFloat) -> Font {
        .system(size: size, weight: .regular, design: .serif)
    }
    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight)
    }
    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }

    /// One curve for the whole flow. Apple-ish means *consistent*, not busy.
    static let ease = Animation.spring(response: 0.52, dampingFraction: 0.86)
    static let quick = Animation.spring(response: 0.34, dampingFraction: 0.82)
}

extension Color {
    static func hex(_ v: UInt32) -> Color {
        Color(.sRGB,
              red: Double((v >> 16) & 0xFF) / 255,
              green: Double((v >> 8) & 0xFF) / 255,
              blue: Double(v & 0xFF) / 255,
              opacity: 1)
    }
}

/// Text and controls rise a little as they arrive, staggered by index. This is
/// the only entrance animation in the app; everything else is a crossfade.
struct Rise: ViewModifier {
    let index: Int
    @State private var shown = false
    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown ? 0 : 12)
            .onAppear {
                withAnimation(Theme.ease.delay(Double(index) * 0.07)) { shown = true }
            }
    }
}

extension View {
    func rise(_ index: Int = 0) -> some View { modifier(Rise(index: index)) }
}
