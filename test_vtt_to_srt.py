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


class TimedXMLTests(unittest.TestCase):
    convert_xml = staticmethod(runpy.run_path(str(SCRIPT))["xml_to_srt"])

    def test_multiline_namespaces_and_simultaneous_translations(self):
        source = """<t:tt xmlns:t="http://www.w3.org/ns/ttml" xmlns:s="http://www.w3.org/ns/ttml#styling">
          <t:head><t:styling><t:style xml:id="em" s:fontStyle="italic"/></t:styling>
          <t:layout><t:region xml:id="top" s:displayAlign="before"/></t:layout></t:head>
          <t:body><t:div begin="2s"><t:p end="1.5s" region="top" begin="0s">
            A <t:span style="em">red</t:span> apple<t:br/>A &amp; B
          </t:p><t:p begin="0s" dur="1500ms">红苹果</t:p>
          <t:p begin="2s" end="4s">Next</t:p></t:div></t:body></t:tt>"""
        self.assertEqual(self.convert_xml(source),
                         "1\n00:00:02,000 --> 00:00:03,500\n{\\an8}A <i>red</i> apple\nA &amp; B\n红苹果\n\n"
                         "2\n00:00:04,000 --> 00:00:06,000\nNext\n")

    def test_fractional_frames_ticks_and_sequential_container(self):
        source = """<tt xmlns:p="http://www.w3.org/ns/ttml#parameter" p:frameRate="30"
                        p:frameRateMultiplier="1000 1001" p:tickRate="1000">
                    <body><div timeContainer="seq">
                    <p begin="00:00:00:15" dur="30f">frames</p>
                    <p begin="500t" dur="1000ms">ticks</p>
                    </div></body></tt>"""
        self.assertEqual(self.convert_xml(source),
                         "1\n00:00:00,500 --> 00:00:01,501\nframes\n\n"
                         "2\n00:00:02,001 --> 00:00:03,001\nticks\n")

    def test_legacy_tick_units_and_empty_document(self):
        self.assertEqual(self.convert_xml("<tt><body><p begin='0' end='5000000'>First</p></body></tt>"),
                         "1\n00:00:00,000 --> 00:00:00,500\nFirst\n")
        self.assertEqual(self.convert_xml("<tt><body/></tt>"), "")

    def test_clips_duration_to_parent_boundary(self):
        source = "<tt><body begin='2s' end='4s'><p begin='1s' dur='5s'>X</p></body></tt>"
        self.assertIn("00:00:03,000 --> 00:00:04,000", self.convert_xml(source))


if __name__ == "__main__":
    unittest.main()
