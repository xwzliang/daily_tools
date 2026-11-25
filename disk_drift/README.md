# Disk Drift

A native Mac app for finding which items in a folder use space and which have grown. Requires macOS 13 or newer and the Swift compiler from Xcode or its command line tools.

Run `./build.sh` from this directory to install a new copy in your personal Applications folder. You can pass an unused output path to build elsewhere.

1. Open **Disk Drift**, choose a folder and inspect the size of each immediate child, including hidden items.
2. Click **Save Baseline**. Later, **Rescan** to see changes, including items that appeared or disappeared. Selecting another folder retrieves its own baseline.
3. Select a folder and click **Inspect Folder** to go deeper, or use **Reveal in Finder** to locate an item. You can also open a folder with `open -a "Disk Drift" /path/to/folder`.

The scanner reads file metadata. Only an explicit baseline save writes a snapshot under `~/Library/Application Support/Disk Drift/Baselines`. Measurements use allocated disk blocks, skip other mounted volumes, and do not follow symlinks encountered in the tree. Hard-linked files count once within each top-level item. APFS clones can share physical storage, so the reported sizes do not predict how much space deleting an item would free. A partial scan marks affected items, shows measured bytes as a lower bound, and omits their change figures. Fully measured siblings still show their changes. Saving a baseline requires a complete scan.
