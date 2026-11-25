import Foundation

@main struct ScanTests {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let hidden = root.appendingPathComponent("Book/Scans")
        let manager = FileManager.default
        try manager.createDirectory(at: hidden, withIntermediateDirectories: true)
        defer {
            try? manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: hidden.path)
            try? manager.removeItem(at: root)
        }
        try Data(repeating: 42, count: 256_000).write(to: hidden.appendingPathComponent("clip"))
        let obsolete = root.appendingPathComponent("Old")
        try Data(repeating: 1, count: 16_000).write(to: obsolete)
        let baseline = try Scan.read(root)
        precondition(baseline.skipped == 0)
        try manager.removeItem(at: obsolete)
        try Data(repeating: 9, count: 32_000).write(to: root.appendingPathComponent("New"))
        try manager.setAttributes([.posixPermissions: 0], ofItemAtPath: hidden.path)
        let partial = try Scan.read(root)
        precondition(partial.skipped > 0 && partial.incompleteItems == ["Book"])
        let rows = Dictionary(uniqueKeysWithValues: Scan.changes(partial, from: baseline).map { ($0.name, $0) })
        precondition(rows["Book"]?.incomplete == true && rows["Book"]?.delta == nil)
        precondition((rows["Old"]?.delta ?? 0) < 0 && (rows["New"]?.delta ?? 0) > 0)
        let oldData = try JSONSerialization.jsonObject(with: JSONEncoder().encode(baseline)) as! [String: Any]
        let legacy = try JSONSerialization.data(withJSONObject: oldData.filter { $0.key != "incompleteItems" })
        let decoded = try JSONDecoder().decode(Snapshot.self, from: legacy)
        precondition(Scan.changes(baseline, from: decoded).allSatisfy { $0.delta == 0 })
        print("Verified a real permission-denied subtree, measurable siblings, removal, and legacy baseline.")
    }
}
