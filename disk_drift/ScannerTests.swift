import Foundation
import Darwin

// Run with swiftc -parse-as-library Scanner.swift ScannerTests.swift -o /tmp/disk-drift-tests.
@main
struct ScannerTests {
    static func main() throws {
        let fm = FileManager.default
        let fixture = fm.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try fm.createDirectory(at: fixture, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: fixture) }
        let inside = fixture.appendingPathComponent("root")
        let group = inside.appendingPathComponent("group")
        try fm.createDirectory(at: group, withIntermediateDirectories: true)
        let first = group.appendingPathComponent("file")
        try Data(repeating: 42, count: 65536).write(to: first)
        let link = group.appendingPathComponent("second reference")
        try fm.linkItem(at: first, to: link)
        let outside = fixture.appendingPathComponent("outside")
        try Data(repeating: 43, count: 1048576).write(to: outside)
        let shortcut = inside.appendingPathComponent("shortcut")
        try fm.createSymbolicLink(at: shortcut, withDestinationURL: outside)
        let hidden = inside.appendingPathComponent(".hidden")
        try Data([0]).write(to: hidden)
        let before = try Scan.read(inside)
        precondition(before.skipped == 0 && before.items.count == 3)
        precondition(before.items["group"]?.bytes == allocated(group) + allocated(first))
        precondition(before.items["shortcut"]?.bytes == allocated(shortcut))
        precondition(before.items["shortcut"]?.directory == false)
        try fm.removeItem(at: hidden)
        let fresh = inside.appendingPathComponent("new")
        try Data(repeating: 17, count: 131072).write(to: fresh)
        let after = try Scan.read(inside)
        let changes = Dictionary(uniqueKeysWithValues: Scan.changes(after, from: before).map { ($0.name, $0) })
        precondition(changes[".hidden"]?.current == nil && changes[".hidden"]?.previous != nil)
        precondition(changes["new"]?.delta == allocated(fresh))
        precondition(changes["group"]?.delta == 0)
        let restored = try JSONDecoder().decode(Snapshot.self, from: JSONEncoder().encode(before))
        precondition(restored.root == before.root && restored.items["group"]?.bytes == before.items["group"]?.bytes)
        print("Passed block accounting, hard-link, symlink, hidden file, growth, removal and snapshot round-trip checks")
    }
    private static func allocated(_ url: URL) -> Int64 {
        var info = stat()
        precondition(lstat(url.path, &info) == 0)
        return Int64(info.st_blocks) * 512
    }
}
