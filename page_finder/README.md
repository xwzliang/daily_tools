# Page Finder

Search a folder of PDFs on macOS 13 or later. Choose a folder or open it with Page Finder in Finder, then type a passage. Select a result to jump to its page, copy the excerpt with its citation, or reveal the original PDF.

Search handles case, accents, and short Chinese phrases. Results show up to 120 matching pages. Refresh picks up new and changed PDFs. Cancelling keeps previously indexed books and rolls back the book in progress. Password-protected PDFs appear in the unavailable list. For books with scanned pages, choose **Scan Options → Recognize Text on Scanned Pages**. Recognition runs on your Mac using Apple Vision with English and Chinese language support. The app tries pages with no embedded text and labels their results OCR. Refresh reuses those results while the original file is unchanged. Recognition accuracy depends on the scan. Match highlighting requires an embedded text layer.

Extracted text stays in a per-folder SQLite database under `~/Library/Application Support/Page Finder/Indexes/`. The app reads the original PDFs and skips symbolic links and hidden entries.

Build with the Xcode command line tools:

```sh
./page_finder/build.sh
```

The default destination is `~/Applications/Page Finder.app`. You can pass an unused output path as the first argument.

Run the generated PDF regression fixtures:

```sh
./page_finder/test.sh
```
