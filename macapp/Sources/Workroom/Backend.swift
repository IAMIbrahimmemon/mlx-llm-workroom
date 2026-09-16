import Foundation

/// Talks to the Python runtime that does the real work.
///
/// The app never downloads, probes or writes config itself -- it shells out to
/// the same entry points the CLI uses, so there is one implementation of each.
@MainActor
final class Backend: ObservableObject {
    enum Failure: LocalizedError {
        case missingUV
        case missingRepo
        case failed(String, String)

        var errorDescription: String? {
            switch self {
            case .missingUV:
                "The `uv` command is not installed."
            case .missingRepo:
                "Could not find the Workroom runtime on this Mac."
            case .failed(let what, let why):
                "\(what) failed: \(why)"
            }
        }
    }

    /// Where the Python runtime lives.
    ///
    /// A downloaded `.app` sitting in /Applications has no repo above it, so
    /// this checks, in order: a folder the user already picked, the usual
    /// clone locations, then the path above the executable (which is what
    /// `swift run` and a build-tree bundle want). Returns nil rather than
    /// guessing, so the UI can ask instead of failing silently.
    static let repoDefaultsKey = "WorkroomRepoPath"

    static func findRepo() -> URL? {
        let fm = FileManager.default
        func isRepo(_ url: URL) -> Bool {
            fm.fileExists(atPath: url.appendingPathComponent("agent/bridge.py").path)
        }

        if let saved = UserDefaults.standard.string(forKey: repoDefaultsKey) {
            let url = URL(fileURLWithPath: saved)
            if isRepo(url) { return url }
        }

        var dir = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath()
        for _ in 0..<8 {
            dir.deleteLastPathComponent()
            if isRepo(dir) { return dir }
        }

        let home = URL(fileURLWithPath: NSHomeDirectory())
        let guesses = ["mlx-llm-workroom", "Developer/mlx-llm-workroom",
                       "Documents/mlx-llm-workroom", "Documents/GitHub/mlx-llm-workroom",
                       "src/mlx-llm-workroom", "code/mlx-llm-workroom"]
        for g in guesses {
            let url = home.appendingPathComponent(g)
            if isRepo(url) { return url }
        }
        return nil
    }

    static func remember(repo: URL) {
        UserDefaults.standard.set(repo.path, forKey: repoDefaultsKey)
    }

    static var uvInstalled: Bool { uv() != nil }

    private static func uv() -> String? {
        let candidates = ["/opt/homebrew/bin/uv", "/usr/local/bin/uv",
                          NSHomeDirectory() + "/.local/bin/uv"]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private static func launch(_ args: [String]) throws -> Process {
        guard let uv = uv() else { throw Failure.missingUV }
        guard let repo = findRepo() else { throw Failure.missingRepo }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: uv)
        p.arguments = args
        p.currentDirectoryURL = repo
        return p
    }

    // MARK: - survey

    func survey() async throws -> Survey {
        let p = try Self.launch(["run", "python", "-m", "agent.bridge", "survey"])
        let out = Pipe(), err = Pipe()
        p.standardOutput = out; p.standardError = err
        try p.run()

        let data = out.fileHandleForReading.readDataToEndOfFile()
        let errText = String(data: err.fileHandleForReading.readDataToEndOfFile(),
                             encoding: .utf8) ?? ""
        p.waitUntilExit()
        guard p.terminationStatus == 0 else {
            throw Failure.failed("Reading this Mac", errText.isEmpty ? "exit \(p.terminationStatus)" : errText)
        }
        return try JSONDecoder().decode(Survey.self, from: data)
    }

    // MARK: - save

    @discardableResult
    func save(brain: String, preset: String, vision: String = "", gateway: String = "") async throws -> Bool {
        var args = ["run", "python", "-m", "agent.bridge", "save",
                    "--brain", brain, "--preset", preset]
        if !vision.isEmpty { args += ["--vision", vision] }
        if !gateway.isEmpty { args += ["--gateway", gateway] }
        let p = try Self.launch(args)
        p.standardOutput = Pipe(); p.standardError = Pipe()
        try p.run()
        p.waitUntilExit()
        return p.terminationStatus == 0
    }

    // MARK: - download

    /// Streams one `PullProgress` per line as the download runs.
    func pull(keys: [String]) -> AsyncThrowingStream<PullProgress, Error> {
        AsyncThrowingStream { continuation in
            var args = ["run", "python", "scripts/pull_models.py", "--json"]
            for k in keys { args += ["--only", k] }

            let process: Process
            do { process = try Self.launch(args) } catch {
                continuation.finish(throwing: error); return
            }
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = Pipe()

            let handle = pipe.fileHandleForReading
            // readabilityHandler fires on an arbitrary queue, so the partial
            // line has to live somewhere both Sendable and synchronised.
            let buffer = LineBuffer()
            handle.readabilityHandler = { fh in
                // The writer flushes one whole JSON object per line, so a
                // partial tail is normal and is kept for the next chunk.
                for line in buffer.take(fh.availableData) {
                    if let row = try? JSONDecoder().decode(PullProgress.self, from: line) {
                        continuation.yield(row)
                    }
                }
            }
            process.terminationHandler = { proc in
                handle.readabilityHandler = nil
                if proc.terminationStatus == 0 { continuation.finish() }
                else { continuation.finish(throwing: Failure.failed("The download", "exit \(proc.terminationStatus)")) }
            }
            do { try process.run() } catch { continuation.finish(throwing: error) }
            continuation.onTermination = { _ in
                if process.isRunning { process.terminate() }
            }
        }
    }

    // MARK: - handoff

    /// Opens Terminal on the repo and starts the REPL.
    func launchCLI() {
        guard let repo = Self.findRepo() else { return }
        let script = """
        tell application "Terminal"
            activate
            do script "cd \(repo.path) && uv run workroom"
        end tell
        """
        if let apple = NSAppleScript(source: script) {
            var err: NSDictionary?
            apple.executeAndReturnError(&err)
        }
    }
}


/// Accumulates bytes from a pipe and hands back whole lines.
private final class LineBuffer: @unchecked Sendable {
    private let lock = NSLock()
    private var data = Data()

    func take(_ chunk: Data) -> [Data] {
        lock.lock()
        defer { lock.unlock() }
        data.append(chunk)
        var lines: [Data] = []
        while let nl = data.firstIndex(of: 0x0A) {
            lines.append(Data(data[data.startIndex..<nl]))
            data.removeSubrange(data.startIndex...nl)
        }
        return lines
    }
}
