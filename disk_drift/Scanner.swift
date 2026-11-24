import Foundation
import Darwin
import CryptoKit

struct Entry: Codable {
    let bytes: Int64
    let directory: Bool
}

struct Snapshot: Codable {
    let root: String
    let date: Date
    let items: [String: Entry]
    let skipped: Int
}

struct Change: Identifiable {
    let name: String
    let current: Entry?
    let previous: Entry?
    var id: String { name }
    var bytes: Int64 { current?.bytes ?? 0 }
    var delta: Int64 { bytes - (previous?.bytes ?? 0) }
}

enum Scan {
    static func read(_ directory: URL) throws -> Snapshot {
        let root = directory.standardizedFileURL.resolvingSymlinksInPath()
        let fm = FileManager.default
        let children = try fm.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)
        var rootInfo = stat()
        guard lstat(root.path, &rootInfo) == 0 else { throw POSIXError(.EACCES) }
        var skipped = 0
        var items: [String: Entry] = [:]
        for child in children {
            try Task.checkCancellation()
            var info = stat()
            guard lstat(child.path, &info) == 0, info.st_dev == rootInfo.st_dev else { skipped += 1; continue }
            let isDirectory = (info.st_mode & S_IFMT) == S_IFDIR
            var bytes = Int64(info.st_blocks) * 512
            // Each top-level item's footprint is independent. Deduplicate hard
            // links within it, as two references there share the same blocks.
            var seen = Set<ino_t>()
            if isDirectory {
                guard let walk = fm.enumerator(at: child, includingPropertiesForKeys: [],
                    options: [], errorHandler: { _, _ in skipped += 1; return true }) else {
                    skipped += 1
                    continue
                }
                for case let file as URL in walk {
                    try Task.checkCancellation()
                    var statInfo = stat()
                    guard lstat(file.path, &statInfo) == 0 else { skipped += 1; walk.skipDescendants(); continue }
                    guard statInfo.st_dev == rootInfo.st_dev else { skipped += 1; walk.skipDescendants(); continue }
                    let kind = statInfo.st_mode & S_IFMT
                    if kind == S_IFLNK { walk.skipDescendants() }
                    if kind == S_IFREG && statInfo.st_nlink > 1 && !seen.insert(statInfo.st_ino).inserted { continue }
                    bytes += Int64(statInfo.st_blocks) * 512
                }
            }
            items[child.lastPathComponent] = Entry(bytes: bytes, directory: isDirectory)
        }
        return Snapshot(root: root.path, date: Date(), items: items, skipped: skipped)
    }

    static func changes(_ current: Snapshot, from baseline: Snapshot?) -> [Change] {
        let prior = baseline?.items ?? [:]
        return Set(current.items.keys).union(prior.keys).map {
            Change(name: $0, current: current.items[$0], previous: prior[$0])
        }
    }
}

struct Baselines {
    let folder: URL
    init() throws {
        folder = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true).appendingPathComponent("Disk Drift/Baselines", isDirectory: true)
    }
    private func file(_ root: String) -> URL {
        let key = SHA256.hash(data: Data(root.utf8)).map { String(format: "%02x", $0) }.joined()
        return folder.appendingPathComponent(key + ".json")
    }
    func load(_ root: String) throws -> Snapshot? {
        let url = file(root)
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let snapshot = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: url))
        guard snapshot.root == root else { throw CocoaError(.fileReadCorruptFile) }
        return snapshot
    }
    func save(_ snapshot: Snapshot) throws {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try JSONEncoder().encode(snapshot).write(to: file(snapshot.root), options: .atomic)
    }
}
