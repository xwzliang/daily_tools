import codecs
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shift_ass import shift_ass_file


class ShiftAssTests(unittest.TestCase):
    def test_declared_fields_and_encodings(self):
        source = (
            "[Script Info]\r\nComment: 1,0:00:02.00,0:00:04.00,s,n,0,0,0,,unchanged\r\n"
            "[Events]\r\nFormat: End, Actor, Start, Text\r\n"
            "Dialogue: 0:00:04.00 ,人, 0:00:02.00,Hello, world\n"
            "Comment: 0:00:03.00 ,人, 0:00:01.00,Overlapping\r"
            "Format: Missing, Text\nDialogue: unchanged,Hello"
        )
        expected = source.replace("Dialogue: 0:00:04.00 ,人, 0:00:02.00", "Dialogue: 0:00:02.00 ,人, 0:00:00.00")
        expected = expected.replace("Comment: 0:00:03.00 ,人, 0:00:01.00", "Comment: 0:00:01.00 ,人, 0:00:00.00")
        for bom, encoding in [(b"", "utf-8"), (codecs.BOM_UTF8, "utf-8"),
                              (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")]:
            with self.subTest(encoding=encoding, bom=bom), TemporaryDirectory() as tmp:
                path = Path(tmp) / "sub.ass"
                path.write_bytes(bom + source.encode(encoding))
                shift_ass_file(path, path, "0:00:03.00", -2, "overlap_after")
                self.assertEqual(path.read_bytes(), bom + expected.encode(encoding))

    def test_default_layout_and_start_cutoff(self):
        before = "Dialogue: 0,0:00:01.00,0:00:05.00,s,n,0,0,0,,unchanged\n"
        after = "Comment: 0,0:00:03.00,0:00:05.00,s,n,0,0,0,,shifted"
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "snippet.ass"
            path.write_bytes((before + after).encode())
            shift_ass_file(path, path, "0:00:03.00", 1)
            self.assertEqual(path.read_bytes(), (before + after.replace("03.00", "04.00").replace("05.00", "06.00")).encode())
