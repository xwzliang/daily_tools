import AppKit
import PDFKit
import Vision

struct PageOCR {
    private let languages: [String]

    init() throws {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        let supported = try request.supportedRecognitionLanguages()
        languages = ["en-US", "zh-Hans", "zh-Hant"].filter(supported.contains)
    }

    func read(_ page: PDFPage) throws -> String {
        try Task.checkCancellation()
        let bounds = page.bounds(for: .cropBox)
        guard bounds.width > 0, bounds.height > 0 else { return "" }
        let scale = min(3, 2800 / max(bounds.width, bounds.height))
        let size = CGSize(width: ceil(bounds.width * scale), height: ceil(bounds.height * scale))
        let image = page.thumbnail(of: size, for: .cropBox)
        guard let bitmap = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            throw LibraryError("Could not render a PDF page for text recognition.")
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = languages
        request.usesLanguageCorrection = true
        try VNImageRequestHandler(cgImage: bitmap).perform([request])
        try Task.checkCancellation()
        return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
    }
}
