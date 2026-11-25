import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class ConvertMediaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.env = os.environ.copy()

    def run_tool(self, name, *args):
        return subprocess.run([str(REPO / name), *args], cwd=self.folder,
                              env=self.env, capture_output=True, text=True)

    def fake_encoder(self, code):
        path = self.folder / "ffmpeg"
        path.write_text("#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n" + code)
        path.chmod(0o700)
        self.env["PATH"] = str(self.folder) + os.pathsep + self.env["PATH"]

    def test_partial_failure_continues_batch(self):
        for name in ["first.MKV", "second.mkv"]:
            (self.folder / name).write_bytes(b"source")
        self.fake_encoder('Path(sys.argv[-1]).write_bytes(b"encoded")\n'
                          'sys.exit(1 if Path(sys.argv[sys.argv.index("-i")+1]).stem == "first" else 0)\n')
        result = self.run_tool("to_mp4", "mkv")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder / "first.mp4").exists())
        self.assertEqual((self.folder / "second.mp4").read_bytes(), b"encoded")
        self.assertNotIn("first", result.stdout)
        self.assertEqual(list(self.folder.glob(".media-convert-*")), [])

    def test_concurrent_output_survives(self):
        self.fake_encoder('Path(sys.argv[-1]).write_bytes(b"late")\nPath("out.mp3").write_bytes(b"winner")\n')
        result = self.run_tool("to_mp3", "sample.mov", "out.mp3")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.folder / "out.mp3").read_bytes(), b"winner")

    def test_occupied_output_and_empty_batch(self):
        (self.folder / "sample.mp3").symlink_to("missing-target")
        self.assertNotEqual(self.run_tool("to_mp3", "sample.mov").returncode, 0)
        self.assertFalse((self.folder / "missing-target").exists())
        self.assertNotEqual(self.run_tool("to_mp4", "avi").returncode, 0)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg")
    def test_real_audio_and_video(self):
        source = self.folder / "示例 clip.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=64x64:rate=10",
                        "-f", "lavfi", "-i", "sine=frequency=220", "-t", "0.5", str(source)], check=True)
        original = source.read_bytes()
        for command, args, extension, codec in [
            ("to_mp3", [source.name], ".mp3", "mp3"),
            ("to_mp4", ["mkv"], ".mp4", "h264"),
        ]:
            result = self.run_tool(command, *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            codecs = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
                                              "-of", "csv=p=0", str(source.with_suffix(extension))], text=True)
            self.assertIn(codec, codecs.splitlines())
        self.assertEqual(source.read_bytes(), original)
