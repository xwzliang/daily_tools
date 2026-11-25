import Foundation

struct ChapterTrack {
    enum Format {
        case webVTT, ffmetadata
        var suffix: String { self == .webVTT ? "vtt" : "ffmeta" }
    }

    struct Chapter {
        let start: Int
        let end: Int
        let title: String
    }

    let chapters: [Chapter]
    let endMarkers: Int

    init(notes: [ReviewNote], duration: Double) throws {
        guard duration.isFinite, duration > 0, duration * 1000 < Double(Int.max) else {
            throw ChapterError("The clip has no usable duration.")
        }
        let end = Int((duration * 1000).rounded())
        var titles = [Int: [String]]()
        var omitted = 0
        for note in notes {
            guard note.seconds.isFinite, note.seconds >= 0 else {
                throw ChapterError("A marker has an invalid timestamp.")
            }
            guard note.seconds < duration, (note.seconds * 1000).rounded() < Double(end) else {
                omitted += 1
                continue
            }
            let start = Int((note.seconds * 1000).rounded())
            let title = note.text.split(whereSeparator: { $0.isNewline }).joined(separator: " ")
            titles[start, default: []].append(title)
        }
        endMarkers = omitted
        let starts = titles.keys.sorted()
        guard !starts.isEmpty else { throw ChapterError("Add a marker before the end of the clip to create a chapter.") }
        chapters = zip(starts, starts.dropFirst() + [end]).map { start, finish in
            Chapter(start: start, end: finish, title: titles[start, default: []].joined(separator: " / "))
        }
    }

    func encoded(_ format: Format) -> String {
        switch format {
        case .ffmetadata:
            return ";FFMETADATA1\n" + chapters.map { chapter in
                var title = ""
                for character in chapter.title {
                    if "\\=;#".contains(character) { title.append("\\") }
                    title.append(character)
                }
                return "[CHAPTER]\nTIMEBASE=1/1000\nSTART=\(chapter.start)\nEND=\(chapter.end)\ntitle=\(title)\n"
            }.joined()
        case .webVTT:
            return "WEBVTT\n\n" + chapters.map { chapter in
                let title = chapter.title.replacingOccurrences(of: "&", with: "&amp;")
                    .replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
                return Self.clock(chapter.start) + " --> " + Self.clock(chapter.end) + "\n" + title + "\n"
            }.joined(separator: "\n")
        }
    }

    private static func clock(_ ms: Int) -> String {
        String(format: "%02lld:%02lld:%02lld.%03lld", Int64(ms / 3_600_000), Int64(ms / 60_000 % 60),
               Int64(ms / 1000 % 60), Int64(ms % 1000))
    }
}

private struct ChapterError: LocalizedError {
    let errorDescription: String?
    init(_ description: String) { errorDescription = description }
}
