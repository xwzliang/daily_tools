import CryptoKit
import Foundation

struct ReviewNote: Codable, Identifiable, Equatable {
    let id: UUID
    let seconds: Double
    let text: String
}

struct ClipNotes {
    private let directory: URL

    init(folder: URL, revision: String, storage: URL? = nil) throws {
        let support = try storage ?? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true).appendingPathComponent("Take Sheet")
        let identity = [folder.standardizedFileURL.resolvingSymlinksInPath().path, revision]
        let hash = SHA256.hash(data: try JSONEncoder().encode(identity))
        directory = support.appendingPathComponent("Review Notes").appendingPathComponent(hash.map { String(format: "%02x", $0) }.joined())
    }

    func fetch() throws -> [ReviewNote] {
        guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
        let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
        return try files.filter { $0.pathExtension == "json" }.map {
            try JSONDecoder().decode(ReviewNote.self, from: Data(contentsOf: $0))
        }.sorted { $0.seconds == $1.seconds ? $0.id.uuidString < $1.id.uuidString : $0.seconds < $1.seconds }
    }

    func save(_ note: ReviewNote) throws {
        guard note.seconds.isFinite, note.seconds >= 0, !note.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw CocoaError(.validationMissingMandatoryProperty)
        }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let file = directory.appendingPathComponent(note.id.uuidString + ".json")
        try JSONEncoder().encode(note).write(to: file, options: .atomic)
    }

    static func text(for file: URL, notes: [ReviewNote]) -> String {
        ([file.lastPathComponent] + notes.map { Media.timecode($0.seconds) + "  " + $0.text }).joined(separator: "\n")
    }
}
