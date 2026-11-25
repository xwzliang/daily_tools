import AppKit
import CoreText
import PDFKit

private func makeBook(_ url: URL, _ pages: [String]) throws {
    var box = CGRect(x: 0, y: 0, width: 500, height: 320)
    guard let context = CGContext(url as CFURL, mediaBox: &box, nil) else { throw LibraryError("Fixture writer failed") }
    for content in pages {
        context.beginPDFPage(nil)
        for (row, line) in content.components(separatedBy: "\n").enumerated() {
            context.textPosition = CGPoint(x: 35, y: 200 - row * 28)
            let text = NSAttributedString(string: line, attributes: [.font: NSFont.systemFont(ofSize: 18)])
            CTLineDraw(CTLineCreateWithAttributedString(text), context)
        }
        context.endPDFPage()
    }
    context.closePDF()
}

private func makeScan(_ url: URL) throws {
    let width = 1200, height = 400
    guard let image = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                                bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                                bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { throw LibraryError("Image fixture failed") }
    let bounds = CGRect(x: 0, y: 0, width: width, height: height)
    image.setFillColor(gray: 1, alpha: 1)
    image.fill(bounds)
    image.textPosition = CGPoint(x: 50, y: 215)
    let line = NSAttributedString(string: "The winter orchard is blooming", attributes: [
        .font: NSFont.systemFont(ofSize: 55), .foregroundColor: NSColor.black
    ])
    CTLineDraw(CTLineCreateWithAttributedString(line), image)
    var page = bounds
    guard let raster = image.makeImage(), let pdf = CGContext(url as CFURL, mediaBox: &page, nil) else {
        throw LibraryError("Scanned PDF fixture failed")
    }
    pdf.beginPDFPage(nil)
    pdf.draw(raster, in: bounds)
    pdf.endPDFPage()
    pdf.closePDF()
}

@main struct LibraryTests {
    static func expect(_ message: String, _ predicate: @autoclosure () throws -> Bool) throws {
        guard try predicate() else { throw LibraryError(message) }
    }

    static func main() throws {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let books = temp.appendingPathComponent("Books")
        try FileManager.default.createDirectory(at: books, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temp) }
        let source = books.appendingPathComponent("Field guide.pdf")
        try makeBook(source, ["Café\norchard", "城市图书馆", "Find \"literal\" words"])
        let before = try Data(contentsOf: source)
        let blank = books.appendingPathComponent("Blank.pdf")
        try makeBook(blank, [""])
        try FileManager.default.createSymbolicLink(at: books.appendingPathComponent("Duplicate.pdf"), withDestinationURL: source)
        let lib = try Library(folder: books, storage: temp.appendingPathComponent("Index"))
        let first = try lib.refresh()
        try expect("Discovery or text layer counts: \(first) \(try lib.overview())", first.updated == 2 && first.unsearchable == 1)
        // Recreate the public 1.0 schema around actual indexed documents.
        do {
            let old = try Database(lib.index)
            try old.execute("ALTER TABLE documents DROP COLUMN ocr_checked; ALTER TABLE pages DROP COLUMN recognized; PRAGMA user_version=1;")
        }
        try expect("Upgrade retained old books", lib.refresh().reused == 2)
        try expect("Original modified", Data(contentsOf: source) == before)
        try expect("Case and accent folding", lib.search("CAFE").map(\.page) == [1])
        let phrase = "CAFE  orchard"
        try expect("Index can find a line-wrapped phrase", lib.search(phrase).map(\.page) == [1])
        let document = PDFDocument(url: source)
        guard let page = document?.page(at: 0), let body = page.string else { throw LibraryError("Fixture has no page text") }
        guard
              body.contains("\n"), let range = Library.selectionRange(for: phrase, in: body),
              let selected = page.selection(for: range)?.string else { throw LibraryError("Missing PDF selection for " + body.debugDescription) }
        try expect("Selection spans the original lines", Library.key(selected) == Library.key(phrase))
        let unicode = "📖 before ﬃ\t\nＦＯＯ after"
        let mapped = Library.selectionRange(for: "ffi foo", in: unicode)
        try expect("Expanded ligatures and UTF-16 offsets", mapped.map { (unicode as NSString).substring(with: $0) } == "ﬃ\t\nＦＯＯ")
        try expect("Short CJK query", lib.search("图书").map(\.page) == [2])
        try expect("Indexed CJK query", lib.search("图书馆").map(\.page) == [2])
        try expect("Literal syntax", lib.search("\"literal\"").map(\.page) == [3])
        try expect("Unchanged books should be reused", lib.refresh().reused == 2)
        let totals = try lib.overview()
        try expect("Totals and issues", totals.books == 2 && totals.pages == 3 && totals.issues == ["Blank.pdf — No text layer"])
        try makeBook(source, ["Different text, next revision"])
        try expect("Refresh updated changed book", lib.refresh().updated == 1)
        try expect("Removed old search entry", lib.search("orchard").isEmpty)
        try expect("Added new search entry", lib.search("revision").map(\.page) == [1])
        try FileManager.default.removeItem(at: blank)
        try expect("Removed missing book", lib.refresh().removed == 1)
        try FileManager.default.moveItem(at: books, to: temp.appendingPathComponent("Moved"))
        do { _ = try lib.refresh(); throw LibraryError("Missing library accepted") }
        catch let error as LibraryError where error.errorDescription == "The library folder is unavailable." {}
        try expect("Offline folder retained its index", lib.search("revision").count == 1)
        try FileManager.default.createDirectory(at: books, withIntermediateDirectories: true)
        let scan = books.appendingPathComponent("Scan.pdf")
        try makeScan(scan)
        let imageSource = try Data(contentsOf: scan)
        _ = try lib.refresh()
        try expect("OCR must be explicitly enabled", lib.search("winter orchard").isEmpty)
        try expect("OCR processed the image-only book", lib.refresh(recognizeScans: true).updated == 1)
        let matches = try lib.search("winter orchard")
        try expect("Recognized page and provenance", matches.count == 1 && matches[0].page == 1 && matches[0].recognized)
        try expect("OCR cache reused", lib.refresh(recognizeScans: true).reused == 1)
        try expect("Normal refresh retains recognition", lib.refresh().reused == 1 && lib.search("winter orchard").count == 1)
        try expect("Scanned original unmodified", Data(contentsOf: scan) == imageSource)
        print("Passed PDF discovery, extraction, literal search, incremental updates, offline retention, schema migration, and image-only OCR.")
    }
}
