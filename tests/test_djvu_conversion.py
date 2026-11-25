from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from djvu_2_pdf import convert


class ConversionTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.source = Path(folder.name) / "读书 notes.v2.DJVU"
        self.source.write_bytes(b"source")

    def test_decoder_failure_never_starts_ocr(self):
        with patch("djvu_2_pdf.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ddjvu")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                convert(self.source)
        run.assert_called_once()
        self.assertEqual(list(self.source.parent.iterdir()), [self.source])

    def test_ocr_failure_keeps_original_and_allows_retry(self):
        def fail_ocr(command, check):
            if command[0] == "ddjvu":
                Path(command[-1]).write_bytes(b"%PDF-decoded")
                return
            Path(command[-1]).write_bytes(b"partial")
            raise subprocess.CalledProcessError(4, "ocrmypdf")

        with patch("djvu_2_pdf.subprocess.run", side_effect=fail_ocr):
            with self.assertRaises(subprocess.CalledProcessError):
                convert(self.source)
            self.assertEqual(list(self.source.parent.iterdir()), [self.source])
            outputs = convert(self.source, ocr=False)
        self.assertEqual(outputs, [self.source.with_suffix(".pdf")])
        self.assertEqual(outputs[0].read_bytes(), b"%PDF-decoded")
        self.assertEqual(self.source.read_bytes(), b"source")

    def test_existing_ocr_output_refused_before_decoding(self):
        existing = self.source.with_suffix(".ocr.pdf")
        existing.write_bytes(b"keep")
        with patch("djvu_2_pdf.subprocess.run") as run, self.assertRaises(FileExistsError):
            convert(self.source)
        run.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"keep")
