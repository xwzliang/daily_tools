import SwiftUI
import AVKit
import UniformTypeIdentifiers

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
    let duration: Double?
    let revision: String
}

private struct ClipPlayerView: NSViewRepresentable {
    let player: AVPlayer?

    func makeNSView(context: Context) -> AVPlayerView {
        let view = AVPlayerView()
        view.controlsStyle = .inline
        view.videoGravity = .resizeAspect
        return view
    }

    func updateNSView(_ view: AVPlayerView, context: Context) {
        if view.player !== player { view.player = player }
    }

    static func dismantleNSView(_ view: AVPlayerView, coordinator: ()) {
        view.player = nil
    }
}

private struct Screening: View {
    let playback: Playback
    @State private var player: AVPlayer?
    @State private var store: ClipNotes?
    @State private var notes: [ReviewNote] = []
    @State private var draft: ReviewNote?
    @State private var text = ""
    @State private var problem: String?
    @FocusState private var typing: Bool
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(playback.url.lastPathComponent).lineLimit(1)
                Spacer()
                Button("Done") { dismiss() }.disabled(draft != nil)
            }.padding()
            ClipPlayerView(player: player).frame(minHeight: 240)
            Divider()
            HStack {
                Button("Mark Frame", action: beginNote).disabled(store == nil || draft != nil)
                Spacer()
                Button("Copy Notes") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(ClipNotes.text(for: playback.url, notes: notes), forType: .string)
                }.disabled(notes.isEmpty)
                Menu("Export Chapters") {
                    Button("WebVTT Chapter Track…") { exportChapters(.webVTT) }
                    Button("FFmpeg Chapter Metadata…") { exportChapters(.ffmetadata) }
                }.fixedSize().disabled(notes.isEmpty || playback.duration == nil || draft != nil)
            }.padding(.horizontal).padding(.vertical, 8)
            if let draft {
                HStack {
                    Text(Media.timecode(draft.seconds)).monospacedDigit()
                    TextField("Review note", text: $text).focused($typing).onSubmit(save)
                    Button("Cancel") { self.draft = nil; text = "" }
                    Button("Save Note", action: save).disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }.padding(.horizontal).padding(.bottom, 8)
            }
            if !notes.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(notes) { note in
                            HStack(alignment: .firstTextBaseline) {
                                Button(Media.timecode(note.seconds)) { seek(note.seconds) }.monospacedDigit()
                                Text(note.text).textSelection(.enabled)
                                Spacer()
                                Button("Edit") { edit(note) }.disabled(draft != nil)
                            }
                        }
                    }.padding(.horizontal).padding(.vertical, 4)
                }.frame(maxHeight: 130)
            }
            if let problem { Text(problem).foregroundStyle(.orange).padding(.horizontal) }
        }.frame(minWidth: 640, minHeight: 460)
        .interactiveDismissDisabled(draft != nil)
        .onAppear {
            let video = AVPlayer(url: playback.url)
            player = video
            do {
                let storage = try ClipNotes(folder: playback.url.deletingLastPathComponent(), revision: playback.revision)
                notes = try storage.fetch()
                store = storage
            } catch { problem = error.localizedDescription }
            video.seek(to: CMTime(seconds: playback.start, preferredTimescale: 600),
                       toleranceBefore: .zero, toleranceAfter: .zero)
        }.onDisappear { player?.pause(); player = nil }
    }

    private func exportChapters(_ format: ChapterTrack.Format) {
        guard let duration = playback.duration else { return }
        do {
            let track = try ChapterTrack(notes: notes, duration: duration)
            let panel = NSSavePanel()
            panel.title = "Export Chapters"
            panel.directoryURL = playback.url.deletingLastPathComponent()
            if track.endMarkers > 0 {
                panel.message = "Markers at the end of the clip are omitted (\(track.endMarkers))."
            }
            panel.allowedContentTypes = [UTType(filenameExtension: format.suffix) ?? .plainText]
            panel.isExtensionHidden = false
            panel.nameFieldStringValue = playback.url.deletingPathExtension().lastPathComponent + ".chapters." + format.suffix
            guard panel.runModal() == .OK, let destination = panel.url else { return }
            try track.encoded(format).write(to: destination, atomically: true, encoding: .utf8)
            problem = nil
        } catch { problem = error.localizedDescription }
    }

    private func seek(_ time: Double) {
        player?.pause()
        player?.seek(to: CMTime(seconds: time, preferredTimescale: 600), toleranceBefore: .zero, toleranceAfter: .zero)
    }

    private func beginNote() {
        guard let player, player.currentTime().seconds.isFinite else { return }
        player.pause()
        draft = ReviewNote(id: UUID(), seconds: max(0, player.currentTime().seconds), text: "")
        text = ""
        typing = true
    }

    private func edit(_ note: ReviewNote) {
        seek(note.seconds)
        draft = note
        text = note.text
        typing = true
    }

    private func save() {
        guard let store, let draft else { return }
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        do {
            try store.save(ReviewNote(id: draft.id, seconds: draft.seconds, text: value))
            notes = try store.fetch()
            self.draft = nil
            text = ""
            problem = nil
        } catch { problem = error.localizedDescription }
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
                            playback = Playback(url: take.url, start: frame.time, duration: take.duration, revision: take.revision)
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
