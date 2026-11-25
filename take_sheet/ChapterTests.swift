import Foundation

@main struct ChapterTests {
    static func main() throws {
        func note(_ seconds: Double, _ text: String) -> ReviewNote {
            ReviewNote(id: UUID(), seconds: seconds, text: text)
        }
        let notes = [note(2.125, "中文 #2; a=b\\c"), note(0.25, "<Opening> & start"),
                     note(2.1251, "Second\nline"), note(4, "At the end")]
        let track = try ChapterTrack(notes: notes, duration: 4)
        precondition(track.chapters.count == 2 && track.endMarkers == 1)
        precondition(track.chapters[0].start == 250 && track.chapters[0].end == 2125)
        precondition(track.chapters[1].end == 4000 && track.chapters[1].title == "中文 #2; a=b\\c / Second line")
        let folder = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let vtt = track.encoded(.webVTT)
        precondition(vtt.contains("00:00:00.250 --> 00:00:02.125\n&lt;Opening&gt; &amp; start"))
        try vtt.write(to: folder.appendingPathComponent("test.vtt"), atomically: true, encoding: .utf8)
        try track.encoded(.ffmetadata).write(to: folder.appendingPathComponent("test.ffmeta"), atomically: true, encoding: .utf8)
        precondition((try? ChapterTrack(notes: [note(4, "End")], duration: 4)) == nil)
        print("Chapter intervals, coincident markers, escaping, and end markers verified.")
    }
}
