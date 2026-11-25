import AppKit
import CoreText
import PDFKit

private func makeBook(_ url: URL, _ pages: [String]) throws {
    var box = CGRect(x: 0, y: 0, width: 500, height: 320)
    guard let context = CGContext(url as CFURL, mediaBox: &box, nil) else { throw LibraryError("Fixture writer failed") }
    for line in pages {
        context.beginPDFPage(nil)
        context.textPosition = CGPoint(x: 35, y: 200)
        let text = NSAttributedString(string: line, attributes: [.font: NSFont.systemFont(ofSize: 18)])
        CTLineDraw(CTLineCreateWithAttributedString(text), context)
        context.endPDFPage()
    }
    context.closePDF()
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
        try makeBook(source, ["Café orchard", "城市图书馆", "Find \"literal\" words"])
        let before = try Data(contentsOf: source)
        let blank = books.appendingPathComponent("Blank.pdf")
        try makeBook(blank, [""])
        try FileManager.default.createSymbolicLink(at: books.appendingPathComponent("Duplicate.pdf"), withDestinationURL: source)
        let lib = try Library(folder: books, storage: temp.appendingPathComponent("Index"))
        let first = try lib.refresh()
        try expect("Discovery or text layer counts: \(first) \(try lib.overview())", first.updated == 2 && first.unsearchable == 1)
        try expect("Original modified", Data(contentsOf: source) == before)
        try expect("Case and accent folding", lib.search("CAFE").map(\.page) == [1])
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
        print("Passed PDF discovery, extraction, literal search, incremental updates, and offline retention.")
    }
}
