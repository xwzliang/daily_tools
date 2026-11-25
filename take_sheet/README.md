# Take Sheet

A native Mac contact sheet for comparing local video takes. Build a new copy in your personal Applications folder with `./build.sh` on macOS 13 or later with Xcode command line tools.

Open a folder to see frames near 12%, 50% and 88% of each clip, with its duration, display dimensions and audio-track status. Click a frame to open the video paused at that point. Star preferred takes, switch to **Selects**, and use **Copy Selected Paths** to bring the shortlist into an editor or script.

The app reads the immediate children of the chosen folder, uses macOS media decoders, and applies the source display transform. Very short clips may yield fewer than three distinct frames. Unsupported clips stay visible with a status message. Audio status shows whether an audio track exists.

Selects are stored separately under `~/Library/Application Support/Take Sheet`. A replacement file with a different size or modification time gets a new identity. You can reopen a folder from Terminal with `open -a "Take Sheet" /path/to/renders`.

While reviewing a frame, choose **Mark Frame** to pause at the current playhead and attach a note. Click a saved timestamp to revisit it. **Edit** preserves its timestamp, and **Copy Notes** copies the clip name and ordered timecoded notes. Notes are stored per clip revision under the app’s Application Support folder.

**Export Chapters** turns saved notes into a WebVTT chapters track for a web player or an FFmpeg metadata file for a video container. Each chapter runs from its note to the next marker or the end of the clip. Notes at the same millisecond share a chapter title. The interval before the first note stays unmarked. The save panel flags any markers at the end of the clip. Exports create a separate file.
