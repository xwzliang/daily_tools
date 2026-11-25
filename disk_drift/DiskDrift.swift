import SwiftUI
import AppKit

@main
struct DiskDriftApp: App {
    var body: some Scene {
        Window("Disk Drift", id: "main") { Inspector().frame(minWidth: 680, minHeight: 440) }
        .defaultSize(width: 820, height: 560)
    }
}

private enum Order: String, CaseIterable { case size = "Size", growth = "Growth" }

private struct Inspector: View {
    @State private var document: Snapshot?
    @State private var baseline: Snapshot?
    @State private var selected: String?
    @State private var work: Task<Snapshot, Error>?
    @State private var ticket = UUID()
    @State private var requested: URL?
    @State private var problem: String?
    @State private var order: Order = .size
    @State private var search = ""

    private var rows: [Change] {
        guard let document else { return [] }
        return Scan.changes(document, from: baseline)
            .filter { search.isEmpty || $0.name.localizedStandardContains(search) }
            .sorted {
                let left = order == .growth && baseline != nil ? $0.delta ?? Int64.min : $0.bytes
                let right = order == .growth && baseline != nil ? $1.delta ?? Int64.min : $1.bytes
                return left == right ? $0.name.localizedStandardCompare($1.name) == .orderedAscending : left > right
            }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Image(systemName: "externaldrive").font(.title2).foregroundStyle(.teal)
                VStack(alignment: .leading) {
                    Text(requested?.lastPathComponent ?? "Disk Drift").font(.title2.bold())
                    Text(requested?.path ?? "Choose a folder to measure its contents.")
                        .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                }
                Spacer()
                Button("Choose Folder…", action: choose).keyboardShortcut("o")
            }.padding()
            Divider()
            if let problem {
                Label(problem, systemImage: "exclamationmark.circle").foregroundStyle(.orange).padding(.horizontal).padding(.top, 8)
            }
            if let document {
                HStack {
                    TextField("Find an item", text: $search).textFieldStyle(.roundedBorder)
                    Picker("Sort by", selection: $order) {
                        ForEach(Order.allCases, id: \.self) { Text($0.rawValue) }
                    }.fixedSize()
                }.padding(.horizontal).padding(.vertical, 8)
                Table(rows, selection: $selected) {
                    TableColumn("Item") { row in
                        Label(row.name, systemImage: row.incomplete ? "exclamationmark.circle" : row.current == nil ? "minus.circle" :
                            row.current?.directory == true ? "folder" : "doc")
                    }
                    TableColumn("On disk") { row in
                        Text(row.current == nil ? (row.incomplete ? "Unavailable" : "Gone") : (row.incomplete ? "≥ " : "") + size(row.bytes)).monospacedDigit()
                    }.width(min: 80, ideal: 105, max: 135)
                    TableColumn("Change") { row in
                        Text(row.delta.map { ($0 > 0 ? "+" : "") + size($0) } ?? "—")
                            .monospacedDigit().foregroundStyle((row.delta ?? 0) > 0 ? .orange : .secondary)
                    }.width(min: 80, ideal: 105, max: 135)
                }
                HStack {
                    Button("Inspect Folder") {
                        if let selected { scan(URL(fileURLWithPath: document.root).appendingPathComponent(selected)) }
                    }.disabled(selected.flatMap { document.items[$0] }?.directory != true || work != nil)
                    Button("Reveal in Finder") {
                        if let selected { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: document.root).appendingPathComponent(selected)]) }
                    }.disabled(selected.flatMap { document.items[$0] } == nil)
                    Spacer()
                    Button("Save Baseline") { saveBaseline(document) }.disabled(document.skipped != 0 || work != nil)
                    Button("Rescan") { scan(URL(fileURLWithPath: document.root)) }.keyboardShortcut("r").disabled(work != nil)
                }.padding(.horizontal).padding(.vertical, 8)
            } else {
                Spacer()
                HStack { Spacer(); Image(systemName: "externaldrive.badge.magnifyingglass").font(.system(size: 52)).foregroundStyle(.secondary); Spacer() }
                Spacer()
            }
            Divider()
            HStack {
                if work != nil {
                    ProgressView().controlSize(.small)
                    Text("Measuring folder…")
                    Spacer()
                    Button("Cancel") { cancel() }
                } else if let document {
                    Text("\(document.items.count) items" + (document.skipped > 0 ? " · \(document.skipped) skipped" : ""))
                    Spacer()
                    if let baseline { Text("Baseline " + baseline.date.formatted()) } else { Text("No saved baseline") }
                } else { Text("Local folder sizes and changes since your saved baseline") }
            }.font(.caption).foregroundStyle(.secondary).padding(10)
        }
        .onOpenURL { url in
            if url.isFileURL && (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true {
                scan(url)
            }
        }
        .onDisappear { cancel() }
    }

    private func size(_ bytes: Int64) -> String { ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file) }
    private func choose() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { scan(url) }
    }
    private func cancel() {
        ticket = UUID()
        work?.cancel()
        work = nil
        requested = document.map { URL(fileURLWithPath: $0.root) }
    }
    private func saveBaseline(_ snapshot: Snapshot) {
        do { try Baselines().save(snapshot); baseline = snapshot; order = .growth; problem = nil }
        catch { problem = error.localizedDescription }
    }
    private func scan(_ root: URL) {
        cancel()
        if root.path != document?.root { document = nil; baseline = nil; search = ""; selected = nil }
        requested = root
        problem = nil
        let id = ticket
        let task = Task.detached(priority: .utility) { try Scan.read(root) }
        work = task
        Task { @MainActor in
            do {
                let result = try await task.value
                guard ticket == id else { return }
                document = result
                baseline = nil
                baseline = try Baselines().load(result.root)
                order = baseline == nil ? .size : .growth
                if result.skipped > 0 { problem = "Some items could not be measured. Sizes are partial." }
            } catch {
                guard ticket == id else { return }
                problem = error.localizedDescription
            }
            work = nil
        }
    }
}
