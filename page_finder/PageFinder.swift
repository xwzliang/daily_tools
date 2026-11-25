import AppKit
import PDFKit
import SwiftUI

@MainActor
final class FinderModel: ObservableObject {
    @Published var library: Library?
    @Published var query = "" { didSet { search() } }
    @Published var hits: [PageHit] = []
    @Published var selected: PageHit.ID?
    @Published var scanning = false
    @Published var searching = false
    @Published var status = ""
    @Published var searchError = ""
    @Published var overview = ""
    @Published var issues: [String] = []
    private var scanTask: Task<Void, Never>?
    private var searchTask: Task<Void, Never>?
    private var scanID = UUID()
    private var searchID = UUID()

    func choose() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.prompt = "Index Folder"
        if panel.runModal() == .OK, let url = panel.url { open(url) }
    }

    func open(_ folder: URL) {
        guard (try? folder.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true else {
            status = "Choose a folder containing PDFs."
            return
        }
        do {
            let next = try Library(folder: folder)
            scanTask?.cancel()
            library = next
            hits = []; selected = nil; issues = []; overview = ""
            refresh()
            search()
        } catch { status = error.localizedDescription }
    }

    func refresh() {
        guard let library else { return }
        let ticket = UUID()
        scanID = ticket
        scanning = true
        status = "Looking for PDFs…"
        scanTask = Task.detached { [weak self] in
            do {
                let summary = try library.refresh { path, _ in
                    Task { @MainActor [weak self] in
                        guard let self, self.scanID == ticket, self.scanning else { return }
                        self.status = "Indexing " + path
                    }
                }
                let totals = try library.overview()
                await self?.finished(ticket, totals: totals, status: "\(summary.updated) updated · \(summary.reused) reused · \(summary.removed) removed from index" + (summary.skipped > 0 ? " · \(summary.skipped) skipped" : ""))
            } catch {
                let totals = try? library.overview()
                await self?.finished(ticket, totals: totals, status: error is CancellationError ? "Scan cancelled" : error.localizedDescription)
            }
        }
    }

    private func finished(_ ticket: UUID, totals: (books: Int, pages: Int, issues: [String])?, status: String) {
        guard ticket == scanID else { return }
        scanning = false
        self.status = status
        if let totals {
            overview = "\(totals.books) PDFs · \(totals.pages) searchable pages"
            issues = totals.issues
        }
        search()
    }

    func cancel() { scanTask?.cancel() }

    func search() {
        searchTask?.cancel()
        let ticket = UUID()
        searchID = ticket
        searchError = ""
        hits = []; selected = nil; searching = false
        let term = query
        guard let library, !Library.clean(term).isEmpty else { return }
        searching = true
        searchTask = Task.detached { [weak self] in
            do {
                try await Task.sleep(nanoseconds: 180_000_000)
                let results = try library.search(term)
                await self?.display(ticket, results)
            } catch {
                if !Task.isCancelled { await self?.display(ticket, [], error: error.localizedDescription) }
            }
        }
    }

    private func display(_ ticket: UUID, _ results: [PageHit], error: String = "") {
        guard ticket == searchID else { return }
        hits = results
        selected = results.first?.id
        searching = false
        searchError = error
    }
}

struct BookPage: NSViewRepresentable {
    let url: URL
    let page: Int
    let query: String

    func makeNSView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePage
        return view
    }
    func updateNSView(_ view: PDFView, context: Context) {
        if view.document?.documentURL?.standardizedFileURL != url.standardizedFileURL {
            view.document = PDFDocument(url: url)
        }
        guard let target = view.document?.page(at: page - 1) else { return }
        view.go(to: target)
        if let body = target.string, let range = body.range(of: query, options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive]),
           let selection = target.selection(for: NSRange(range, in: body)) {
            view.setCurrentSelection(selection, animate: false)
        } else { view.clearSelection() }
    }
}

struct FinderScreen: View {
    @ObservedObject var model: FinderModel
    @State private var issuesOpen = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                VStack(alignment: .leading) {
                    Text(model.library?.root.lastPathComponent ?? "PDF Library").font(.title2.bold())
                    if let path = model.library?.root.path { Text(path).font(.caption).foregroundStyle(.secondary).textSelection(.enabled) }
                }
                Spacer()
                Button("Choose Folder…") { model.choose() }.keyboardShortcut("o")
                if model.library != nil {
                    if model.scanning { Button("Cancel Scan") { model.cancel() } }
                    else { Button("Refresh") { model.refresh() }.keyboardShortcut("r") }
                }
            }.padding()
            Divider()
            HSplitView {
                VStack(alignment: .leading) {
                    TextField("Find a passage", text: $model.query).textFieldStyle(.roundedBorder).padding([.horizontal, .top])
                    if model.hits.isEmpty {
                        Text(emptyMessage).foregroundStyle(.secondary).padding()
                        Spacer()
                    } else {
                        Text(model.hits.count == 120 ? "First 120 matching pages" : "\(model.hits.count) matching pages")
                            .font(.caption).foregroundStyle(.secondary).padding(.horizontal)
                        List(model.hits, selection: $model.selected) { hit in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(hit.path + " · p. \(hit.page)").font(.headline).lineLimit(2)
                                Text(hit.clip).font(.callout).lineLimit(3)
                            }.padding(.vertical, 4).tag(hit.id)
                        }
                    }
                }.frame(minWidth: 240, idealWidth: 335, maxWidth: 500)
                if let hit = model.hits.first(where: { $0.id == model.selected }), let library = model.library {
                    let url = library.root.appendingPathComponent(hit.path)
                    VStack(alignment: .leading) {
                        HStack {
                            Text(url.lastPathComponent + " · p. \(hit.page)").lineLimit(1)
                            Spacer()
                            Button("Copy Passage") {
                                let pasteboard = NSPasteboard.general
                                pasteboard.clearContents()
                                pasteboard.setString(hit.clip + "\n" + hit.path + ", p. \(hit.page)", forType: .string)
                            }
                            Button("Reveal") { NSWorkspace.shared.activateFileViewerSelecting([url]) }
                        }.padding(.horizontal).padding(.top, 8)
                        if FileManager.default.isReadableFile(atPath: url.path) {
                            BookPage(url: url, page: hit.page, query: model.query)
                        } else { Text("This PDF has moved or is unavailable. Refresh the library to update its index.").padding(); Spacer() }
                    }.frame(minWidth: 380)
                } else {
                    Text("Select a matching page to read it here.").foregroundStyle(.secondary)
                        .frame(minWidth: 380, maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            Divider()
            HStack {
                if model.scanning { ProgressView().controlSize(.small) }
                Text(model.status).lineLimit(1).truncationMode(.middle)
                Spacer()
                Text(model.overview)
                if !model.issues.isEmpty {
                    Button("\(model.issues.count) unavailable") { issuesOpen.toggle() }
                        .popover(isPresented: $issuesOpen) { ScrollView { Text(model.issues.joined(separator: "\n")).textSelection(.enabled).padding() }.frame(width: 400, height: 200) }
                }
            }.font(.caption).foregroundStyle(.secondary).padding(10)
        }.frame(minWidth: 730, minHeight: 460)
    }

    var emptyMessage: String {
        if model.library == nil { return "Choose a folder to search the text of its PDFs." }
        if !model.searchError.isEmpty { return model.searchError }
        if model.searching { return "Searching…" }
        if Library.clean(model.query).isEmpty { return "Enter a word or phrase to find matching pages." }
        return model.scanning ? "Indexing the library…" : "No matching pages."
    }
}

@main
struct PageFinderApp: App {
    @StateObject private var model = FinderModel()
    var body: some Scene {
        Window("Page Finder", id: "library") {
            FinderScreen(model: model).onOpenURL { model.open($0) }
        }.defaultSize(width: 1080, height: 700)
    }
}
