import SwiftUI
import AVKit

@main
struct TakeSheetApp: App {
    var body: some Scene {
        Window("Take Sheet", id: "takes") {
            TakeBrowser().frame(minWidth: 720, minHeight: 440)
        }.defaultSize(width: 960, height: 680)
    }
}

private struct Playback: Identifiable {
    let id = UUID()
    let url: URL
    let start: Double
}

private struct Screening: View {
    let playback: Playback
    @State private var player: AVPlayer?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(playback.url.lastPathComponent).lineLimit(1)
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.cancelAction)
            }.padding()
            VideoPlayer(player: player)
        }.frame(minWidth: 640, minHeight: 400)
        .onAppear {
            let video = AVPlayer(url: playback.url)
            player = video
            video.seek(to: CMTime(seconds: playback.start, preferredTimescale: 600),
                       toleranceBefore: .zero, toleranceAfter: .zero)
        }.onDisappear { player?.pause(); player = nil }
    }
}

private struct TakeBrowser: View {
    @State private var folder: URL?
    @State private var takes: [Take] = []
    @State private var selected = Set<String>()
    @State private var selectsOnly = false
    @State private var query = ""
    @State private var task: Task<Void, Never>?
    @State private var ticket = UUID()
    @State private var scanned = 0
    @State private var store: Selects?
    @State private var error: String?
    @State private var playback: Playback?

    private var visible: [Take] {
        takes.filter { (!selectsOnly || selected.contains($0.revision)) &&
            (query.isEmpty || $0.url.lastPathComponent.localizedStandardContains(query)) }
    }
    private var selectedTakes: [Take] { takes.filter { selected.contains($0.revision) } }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Image(systemName: "film.stack").font(.title2).foregroundStyle(.indigo)
                VStack(alignment: .leading) {
                    Text(folder?.lastPathComponent ?? "Take Sheet").font(.title2.bold())
                    Text(folder?.path ?? "Open a folder of video takes to compare frames.")
                        .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                }
                Spacer()
                Button("Open Folder…", action: choose).keyboardShortcut("o")
            }.padding()
            if let error { Text(error).font(.callout).foregroundStyle(.orange).padding(.horizontal) }
            Divider()
            if folder != nil {
                HStack {
                    TextField("Find a clip", text: $query).textFieldStyle(.roundedBorder)
                    Picker("Show", selection: $selectsOnly) {
                        Text("All takes").tag(false); Text("Selects").tag(true)
                    }.pickerStyle(.segmented).frame(width: 180)
                }.padding(.horizontal).padding(.vertical, 8)
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(visible) { take in
                            row(take)
                            Divider()
                        }
                        if visible.isEmpty && task == nil {
                            Text(takes.isEmpty ? "No video clips in this folder." : "No matching takes.")
                                .foregroundStyle(.secondary).padding()
                        }
                    }
                }
            } else { Spacer() }
            Divider()
            HStack {
                if task != nil {
                    ProgressView().controlSize(.small)
                    Text("Reading \(scanned) of \(takes.count)")
                } else { Text("\(takes.count) clips") }
                Spacer()
                Text("\(selectedTakes.count) selected")
                Button("Copy Selected Paths") {
                    let paths = selectedTakes.map { $0.url.path }.joined(separator: "\n")
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(paths, forType: .string)
                }.disabled(selectedTakes.isEmpty)
            }.font(.caption).padding(10)
        }
        .onOpenURL { url in
            if url.isFileURL && (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true { open(url) }
        }
        .onDisappear { ticket = UUID(); task?.cancel(); task = nil }
        .sheet(item: $playback) { Screening(playback: $0) }
    }

    private func row(_ take: Take) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Button { mark(take) } label: {
                    Image(systemName: selected.contains(take.revision) ? "star.fill" : "star")
                        .foregroundStyle(selected.contains(take.revision) ? .orange : .secondary)
                }.buttonStyle(.plain).accessibilityLabel(selected.contains(take.revision) ? "Remove from selects" : "Mark as select")
                    .disabled(store == nil)
                Text(take.url.lastPathComponent).font(.headline).lineLimit(1)
                Spacer()
                Text([take.duration.map(Media.timecode), take.dimensions,
                      take.hasAudio.map { $0 ? "Audio" : "Silent" }].compactMap { $0 }.joined(separator: " · "))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            }
            if !take.frames.isEmpty {
                HStack(spacing: 6) {
                    ForEach(take.frames) { frame in
                        Button {
                            playback = Playback(url: take.url, start: frame.time)
                        } label: {
                            ZStack(alignment: .bottomLeading) {
                                Color.black
                                if let image = NSImage(data: frame.jpeg) {
                                    Image(nsImage: image).resizable().aspectRatio(contentMode: .fit).frame(maxWidth: .infinity)
                                }
                                Text(Media.timecode(frame.time)).font(.caption2.monospacedDigit())
                                    .padding(3).background(.black.opacity(0.65)).foregroundStyle(.white)
                            }.frame(height: 112).clipShape(RoundedRectangle(cornerRadius: 4))
                        }.buttonStyle(.plain).accessibilityLabel("Open at " + Media.timecode(frame.time))
                    }
                }
            } else if let issue = take.issue { Text(issue).foregroundStyle(.secondary) }
        }.padding(.horizontal).padding(.vertical, 10)
    }

    private func choose() {
        let picker = NSOpenPanel()
        picker.canChooseDirectories = true
        picker.canChooseFiles = false
        picker.allowsMultipleSelection = false
        if picker.runModal() == .OK, let url = picker.url { open(url) }
    }
    private func mark(_ take: Take) {
        guard let store else { return }
        var next = selected
        if !next.insert(take.revision).inserted { next.remove(take.revision) }
        do { try store.write(next); selected = next; error = nil }
        catch let problem { error = problem.localizedDescription }
    }
    private func open(_ url: URL) {
        task?.cancel()
        let id = UUID()
        ticket = id
        folder = url
        takes = []; selected = []; store = nil; error = nil; query = ""; selectsOnly = false; scanned = 0
        task = Task { @MainActor in
            defer { if ticket == id { task = nil } }
            do {
                let files = try await Task.detached(priority: .utility) { try Media.files(in: url) }.value
                guard ticket == id else { return }
                takes = files
                do {
                    let marks = try Selects(folder: url)
                    selected = try marks.read()
                    store = marks
                } catch let problem { error = problem.localizedDescription }
                for index in files.indices {
                    try Task.checkCancellation()
                    let ready = try await Media.preview(files[index])
                    guard ticket == id else { return }
                    takes[index] = ready
                    scanned += 1
                }
            } catch is CancellationError { }
            catch let problem { if ticket == id { error = problem.localizedDescription } }
        }
    }
}
