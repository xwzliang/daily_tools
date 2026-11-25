import CryptoKit
import Darwin
import Foundation
import PDFKit

struct ScanSummary {
    var discovered = 0
    var updated = 0
    var reused = 0
    var removed = 0
    var skipped = 0
    var unsearchable = 0
}

struct PageHit: Identifiable {
    let path: String
    let page: Int
    let clip: String
    let recognized: Bool
    var id: String { "\(page):" + path }
}

struct Library {
    let root: URL
    let index: URL

    init(folder: URL, storage: URL? = nil) throws {
        root = folder.standardizedFileURL.resolvingSymlinksInPath()
        let home = try storage ?? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true).appendingPathComponent("Page Finder/Indexes", isDirectory: true)
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let key = SHA256.hash(data: Data(root.path.utf8)).map { String(format: "%02x", $0) }.joined()
        index = home.appendingPathComponent(key + ".sqlite")
    }

    static func clean(_ text: String) -> String {
        text.split(whereSeparator: { $0.isWhitespace || $0 == "\0" }).joined(separator: " ")
    }
    static func key(_ text: String) -> String {
        clean(text.precomposedStringWithCompatibilityMapping)
            .folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "en_US_POSIX"))
    }

    private func stamp(_ url: URL) throws -> (size: Int64, modified: Int64) {
        var info = stat()
        guard lstat(url.path, &info) == 0, info.st_mode & S_IFMT == S_IFREG else { throw LibraryError("Cannot read " + url.lastPathComponent) }
        return (Int64(info.st_size), Int64(info.st_mtimespec.tv_sec) * 1_000_000_000 + Int64(info.st_mtimespec.tv_nsec))
    }

    func refresh(recognizeScans: Bool = false, progress: (String, ScanSummary) -> Void = { _, _ in }) throws -> ScanSummary {
        let lock = open(index.path + ".lock", O_CREAT | O_WRONLY, 0o600)
        guard lock >= 0 else { throw LibraryError("Could not open the index lock.") }
        defer { close(lock) }
        guard flock(lock, LOCK_EX | LOCK_NB) == 0 else { throw LibraryError("Another scan is updating this library.") }
        let db = try Database(index)
        var summary = ScanSummary()
        var seen = Set<String>()
        var complete = true
        var rootInfo = stat()
        guard lstat(root.path, &rootInfo) == 0, rootInfo.st_mode & S_IFMT == S_IFDIR else { throw LibraryError("The library folder is unavailable.") }
        guard let walk = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles, .skipsPackageDescendants], errorHandler: { _, _ in
                complete = false; summary.skipped += 1; return true
            }) else { throw LibraryError("Could not scan the selected folder.") }

        let recognizer = try recognizeScans ? PageOCR() : nil
        let lookup = try db.statement("SELECT size, modified, issue, ocr_checked, pages, extracted FROM documents WHERE path=?")
        let base = root.path.hasSuffix("/") ? root.path : root.path + "/"
        for case let url as URL in walk {
            try Task.checkCancellation()
            var info = stat()
            guard lstat(url.path, &info) == 0 else { complete = false; summary.skipped += 1; continue }
            if info.st_dev != rootInfo.st_dev || info.st_mode & S_IFMT == S_IFLNK {
                walk.skipDescendants(); continue
            }
            guard url.pathExtension.lowercased() == "pdf", info.st_mode & S_IFMT == S_IFREG else { continue }
            let path = url.standardizedFileURL.path
            guard path.hasPrefix(base) else { complete = false; summary.skipped += 1; continue }
            let relative = String(path.dropFirst(base.count))
            seen.insert(relative)
            summary.discovered += 1
            let current = try stamp(url)
            try lookup.bind([.text(relative)])
            if try lookup.next(), lookup.integer(0) == current.size, lookup.integer(1) == current.modified,
               !recognizeScans || lookup.integer(3) != 0 || lookup.integer(4) == lookup.integer(5) {
                summary.reused += 1
                if !lookup.text(2).isEmpty { summary.unsearchable += 1 }
                continue
            }
            progress(relative, summary)
            let issue = try autoreleasepool {
                var lastReport = ProcessInfo.processInfo.systemUptime
                return try indexDocument(url, relative: relative, before: current, db: db, recognizer: recognizer) { page, total in
                    let now = ProcessInfo.processInfo.systemUptime
                    if now - lastReport >= 1 {
                        progress(relative + " · page " + String(page) + " of " + String(total), summary)
                        lastReport = now
                    }
                }
            }
            if !issue.isEmpty { summary.unsearchable += 1 }
            summary.updated += 1
        }
        try Task.checkCancellation()
        if complete {
            let all = try db.statement("SELECT path FROM documents")
            var absent = [String]()
            while try all.next() {
                let path = all.text(0)
                if !seen.contains(path) { absent.append(path) }
            }
            let remove = try db.statement("DELETE FROM documents WHERE path=?")
            try db.transaction {
                for path in absent { try remove.bind([.text(path)]); try remove.next() }
            }
            summary.removed = absent.count
        }
        return summary
    }

    private func indexDocument(_ url: URL, relative: String, before: (size: Int64, modified: Int64), db: Database, recognizer: PageOCR?, pageProgress: (Int, Int) -> Void) throws -> String {
        let pdf = PDFDocument(url: url)
        var issue = ""
        if pdf == nil { issue = "Unreadable PDF" }
        else if pdf?.isLocked == true { issue = "Password protected" }
        let count = issue.isEmpty ? (pdf?.pageCount ?? 0) : 0
        var extracted = 0
        try db.transaction {
            let replace = try db.statement("DELETE FROM documents WHERE path=?")
            try replace.bind([.text(relative)]); try replace.next()
            let add = try db.statement("INSERT INTO documents(path,size,modified,pages) VALUES(?,?,?,?) RETURNING id")
            try add.bind([.text(relative), .integer(before.size), .integer(before.modified), .integer(Int64(count))])
            guard try add.next() else { throw LibraryError("Could not add the book.") }
            let id = add.integer(0)
            try add.next()
            let page = try db.statement("INSERT INTO pages(document, number, body, normalized, recognized) VALUES(?,?,?,?,?)")
            for number in 0..<count {
                try Task.checkCancellation()
                pageProgress(number + 1, count)
                try autoreleasepool {
                    guard let source = pdf?.page(at: number) else { return }
                    var text = Self.clean(source.string ?? "")
                    let needsRecognition = text.isEmpty && recognizer != nil
                    if needsRecognition, let recognizer {
                        text = Self.clean(try recognizer.read(source))
                    }
                    if !text.isEmpty {
                        try page.bind([.integer(id), .integer(Int64(number + 1)), .text(text), .text(Self.key(text)), .integer(needsRecognition ? 1 : 0)])
                        try page.next()
                        extracted += 1
                    }
                }
            }
            if issue.isEmpty && extracted == 0 { issue = recognizer == nil ? "No text layer" : "No text recognized" }
            let status = try db.statement("UPDATE documents SET extracted=?, issue=?, ocr_checked=? WHERE id=?")
            try status.bind([.integer(Int64(extracted)), .text(issue), .integer(recognizer == nil ? 0 : 1), .integer(id)]); try status.next()
            guard try stamp(url) == before else { throw LibraryError("The book changed during scanning. Refresh to retry.") }
        }
        return issue
    }

    func search(_ text: String, limit: Int = 120) throws -> [PageHit] {
        let needle = Self.key(text)
        guard !needle.isEmpty, FileManager.default.fileExists(atPath: index.path) else { return [] }
        let db = try Database(index, readOnly: true)
        let query: Statement
        if needle.unicodeScalars.count >= 3 {
            query = try db.statement("""
                SELECT d.path, p.number, p.body, p.recognized FROM words JOIN pages p ON p.id=words.rowid
                JOIN documents d ON d.id=p.document WHERE words MATCH ?
                ORDER BY rank, d.path, p.number LIMIT ?
                """)
            let literal = "\"" + needle.replacingOccurrences(of: "\"", with: "\"\"") + "\""
            try query.bind([.text(literal), .integer(Int64(limit))])
        } else {
            query = try db.statement("""
                SELECT d.path, p.number, p.body, p.recognized FROM pages p JOIN documents d ON p.document=d.id
                WHERE instr(p.normalized,?)>0 ORDER BY d.path,p.number LIMIT ?
                """)
            try query.bind([.text(needle), .integer(Int64(limit))])
        }
        var hits = [PageHit]()
        while try query.next() {
            try Task.checkCancellation()
            let body = query.text(2)
            let found = body.range(of: Self.clean(text), options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive])
            let position = found?.lowerBound ?? body.startIndex
            let start = body.index(position, offsetBy: -52, limitedBy: body.startIndex) ?? body.startIndex
            let end = body.index(start, offsetBy: 210, limitedBy: body.endIndex) ?? body.endIndex
            let snippet = (start == body.startIndex ? "" : "…") + body[start..<end] + (end == body.endIndex ? "" : "…")
            hits.append(PageHit(path: query.text(0), page: Int(query.integer(1)), clip: String(snippet), recognized: query.integer(3) != 0))
        }
        return hits
    }

    func overview() throws -> (books: Int, pages: Int, issues: [String]) {
        guard FileManager.default.fileExists(atPath: index.path) else { return (0, 0, []) }
        let db = try Database(index, readOnly: true)
        let totals = try db.statement("SELECT count(*),coalesce(sum(extracted),0) FROM documents")
        try totals.next()
        let issues = try db.statement("SELECT path,issue FROM documents WHERE issue!='' ORDER BY path")
        var problems = [String]()
        while try issues.next() { problems.append(issues.text(0) + " — " + issues.text(1)) }
        return (Int(totals.integer(0)), Int(totals.integer(1)), problems)
    }
}
