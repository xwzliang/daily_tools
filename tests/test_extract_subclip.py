import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "extract_subclip"


class SubclipTests(unittest.TestCase):
    def test_missing_flag_value_terminates(self):
        for option in ("-s", "--start", "-e", "--end"):
            with self.subTest(option=option):
                result = subprocess.run([str(SCRIPT), "movie.mp4", option], capture_output=True, timeout=2)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"requires", result.stderr)

    def test_occupied_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "original.mp4", root / "review.mp4"
            source.write_bytes(b"original")
            output.write_bytes(b"existing export")
            for dest in (output, source):
                result = subprocess.run([str(SCRIPT), str(source), "0", "1", str(dest)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"existing export")
            self.assertEqual(source.read_bytes(), b"original")
            dangling = root / "broken.mp4"
            dangling.symlink_to("missing")
            result = subprocess.run([str(SCRIPT), str(source), "0", "1", str(dangling)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "missing").exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg")
    def test_clip_is_playable_and_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "sample clip.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=64x64:rate=10",
                            "-t", "2", "-c:v", "mpeg4", "-g", "1", str(source)], check=True)
            before = hashlib.sha256(source.read_bytes()).digest()
            subprocess.run([str(SCRIPT), str(source), "--start", "0.5", "--end", "1.5"], check=True, capture_output=True)
            output = source.with_name("sample clip_sub_0.5_1.5.mp4")
            duration = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                               "-of", "csv=p=0", str(output)], text=True)
            self.assertAlmostEqual(float(duration), 1, places=1)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)
