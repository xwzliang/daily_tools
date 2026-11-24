import AppKit
import AVFoundation
import CryptoKit

struct Frame: Identifiable {
    let time: Double
    let jpeg: Data
    var id: Double { time }
}

struct Take: Identifiable {
    let url: URL
    let revision: String
    var duration: Double?
    var dimensions: String?
    var hasAudio: Bool?
    var frames = [Frame]()
    var issue: String?
    var id: URL { url }
}

enum Media {
    private static let extensions = Set(["mov", "mp4", "m4v", "avi", "mkv", "webm", "mpg", "mpeg", "mts", "m2ts"])

    static func files(in folder: URL) throws -> [Take] {
        let keys: Set<URLResourceKey> = [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey, .contentModificationDateKey]
        let urls = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: Array(keys), options: [.skipsHiddenFiles])
        return try urls.filter { extensions.contains($0.pathExtension.lowercased()) }.compactMap { url in
            let info = try url.resourceValues(forKeys: keys)
            guard info.isRegularFile == true && info.isSymbolicLink != true else { return nil }
            let stamp = info.contentModificationDate?.timeIntervalSinceReferenceDate ?? 0
            let revision = "\(url.lastPathComponent)/\(info.fileSize ?? -1)/\(stamp)"
            return Take(url: url, revision: revision)
        }.sorted { $0.url.lastPathComponent.localizedStandardCompare($1.url.lastPathComponent) == .orderedAscending }
    }

    static func preview(_ input: Take) async throws -> Take {
        var take = input
        let asset = AVURLAsset(url: take.url)
        do {
            let duration = try await asset.load(.duration).seconds
            guard duration.isFinite, duration > 0,
                  let track = try await asset.loadTracks(withMediaType: .video).first else {
                throw CocoaError(.fileReadCorruptFile)
            }
            take.duration = duration
            let natural = try await track.load(.naturalSize)
            let transform = try await track.load(.preferredTransform)
            let bounds = CGRect(origin: .zero, size: natural).applying(transform)
            take.dimensions = "\(Int(abs(bounds.width).rounded())) × \(Int(abs(bounds.height).rounded()))"
            take.hasAudio = try await !asset.loadTracks(withMediaType: .audio).isEmpty
            let generator = AVAssetImageGenerator(asset: asset)
            generator.appliesPreferredTrackTransform = true
            generator.maximumSize = CGSize(width: 360, height: 220)
            generator.requestedTimeToleranceAfter = .zero
            generator.requestedTimeToleranceBefore = CMTime(seconds: min(0.2, duration * 0.1), preferredTimescale: 600)
            for fraction in [0.12, 0.5, 0.88] {
                try Task.checkCancellation()
                let time = CMTime(seconds: duration * fraction, preferredTimescale: 600)
                do {
                    let frame = try await generator.image(at: time)
                    let bitmap = NSBitmapImageRep(cgImage: frame.image)
                    if let data = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.77]),
                       !take.frames.contains(where: { $0.time == frame.actualTime.seconds }) {
                        take.frames.append(Frame(time: frame.actualTime.seconds, jpeg: data))
                    }
                } catch { try Task.checkCancellation() }
            }
            if take.frames.isEmpty { take.issue = "No preview frames available" }
        } catch {
            try Task.checkCancellation()
            take.issue = "macOS could not read this clip"
        }
        return take
    }

    static func timecode(_ time: Double) -> String {
        let tenths = Int((max(0, time) * 10).rounded())
        return String(format: "%d:%02d.%d", tenths / 600, (tenths / 10) % 60, tenths % 10)
    }
}

struct Selects {
    private let file: URL
    init(folder: URL, storage: URL? = nil) throws {
        let home = try storage ?? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true).appendingPathComponent("Take Sheet", isDirectory: true)
        let hash = SHA256.hash(data: Data(folder.standardizedFileURL.resolvingSymlinksInPath().path.utf8))
        file = home.appendingPathComponent(hash.map { String(format: "%02x", $0) }.joined() + ".json")
    }
    func read() throws -> Set<String> {
        guard FileManager.default.fileExists(atPath: file.path) else { return [] }
        return try JSONDecoder().decode(Set<String>.self, from: Data(contentsOf: file))
    }
    func write(_ marks: Set<String>) throws {
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try JSONEncoder().encode(marks.sorted()).write(to: file, options: .atomic)
    }
}
