import SwiftUI

@main
struct WorkroomApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    init() {
        // `Workroom --snapshot <dir>` renders every screen to PNG and exits. The app
        // draws itself, so this needs no Screen Recording permission and works
        // in CI -- which `screencapture` does not.
        if let i = CommandLine.arguments.firstIndex(of: "--snapshot"),
           i + 1 < CommandLine.arguments.count {
            Snapshotter.run(into: CommandLine.arguments[i + 1])
        }
    }

    var body: some Scene {
        Window("Workroom", id: "onboarding") {
            RootView()
        }
        .windowResizability(.contentSize)
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1000, height: 700)
        .commands { CommandGroup(replacing: .newItem) {} }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }
}


/// Reaches the real `NSWindow` once SwiftUI has built it.
///
/// `.defaultSize` is only a hint -- the window manager will shrink the window
/// to fit whichever display it restores onto, and the onboarding is laid out
/// for exactly 1000x700. Doing this from `applicationDidFinishLaunching`
/// instead does not work: at that point `NSApp.windows.first` is not yet the
/// scene's window.
struct WindowConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        configure(view, attempt: 0)
        return view
    }

    /// The window is not attached on the first runloop turn, and SwiftUI may
    /// resize it again after the scene settles, so this retries a few times.
    private func configure(_ view: NSView, attempt: Int) {
        DispatchQueue.main.asyncAfter(deadline: .now() + (attempt == 0 ? 0 : 0.12)) {
            guard let window = view.window else {
                if attempt < 20 { configure(view, attempt: attempt + 1) }
                return
            }
            let target = NSSize(width: 1000, height: 700)
            if window.contentLayoutRect.size != target {
                window.setContentSize(target)
                window.center()
            }
            window.isMovableByWindowBackground = true
            window.titlebarAppearsTransparent = true
            // SwiftUI can resize the scene again just after it settles, so
            // hold the size for a few more turns rather than only once.
            if attempt < 6 { configure(view, attempt: attempt + 1) }
        }
    }

    func updateNSView(_ nsView: NSView, context: Context) {}
}
