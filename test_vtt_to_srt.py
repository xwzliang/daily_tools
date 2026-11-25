import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("vtt_to_srt")
convert = runpy.run_path(str(SCRIPT))["vtt_to_srt"]


class WebVTTTests(unittest.TestCase):
    def test_header_notes_ids_and_hour_boundary(self):
        source = """WEBVTT bilingual captions
Kind: captions

NOTE producer comment
00:00.000 --> 00:02.000
sample only

scene-17
59:59.950   -->\t01:00:01.030 align:start position:40%
<v Speaker>Hello, <i>world</i>.</v>
你好，世界。

00:05.000 --> 00:06.030
Second <00:05.500>word
"""
        expected = """1
00:59:59,950 --> 01:00:01,030
Hello, <i>world</i>.
你好，世界。

2
00:00:05,000 --> 00:00:06,030
Second word
"""
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=newline):
                self.assertEqual(convert("\ufeff" + source.replace("\n", newline)), expected)

    def test_color_spans_keep_surrounding_words_and_nested_formatting(self):
        source = """WEBVTT

STYLE
::cue(.red) { color: #f00; }
::cue(.green) {
  color: green;
}

00:01.000 --> 00:02.000
before <c.red><b>赤</b> <c.unstyled>い</c></c> and <c.green>緑</c> after
<c.Japanese>終わり</c.Japanese>"""
        self.assertIn('before <font color="#f00"><b>赤</b> い</font> and <font color="green">緑</font> after\n終わり', convert(source))

    def test_failed_parse_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "broken.vtt").write_text("WEBVTT\n\n00:79.100 --> 00:80.000\nInvalid")
            previous = root / "broken.srt"
            previous.write_bytes(b"previous good subtitles")
            result = subprocess.run([sys.executable, str(SCRIPT), "-i", folder, "-o", folder], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(previous.read_bytes(), b"previous good subtitles")


if __name__ == "__main__":
    unittest.main()
