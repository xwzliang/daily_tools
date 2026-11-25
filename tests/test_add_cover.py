import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None

from add_cover_image_to_pdf import add_cover


@unittest.skipUnless(pymupdf, "cover conversion requires PyMuPDF")
class CoverTests(unittest.TestCase):
    def test_cover_preserves_inputs_content_and_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / "笔记 author's book.v2.PDF"
            image = folder / "cover & art.png"
            with pymupdf.open() as fixture:
                page = fixture.new_page(width=150, height=180)
                page.insert_text((15, 60), "Cover artwork")
                page.get_pixmap().save(image)
                page.insert_text((15, 100), "Chapter one")
                fixture.set_toc([[1, "Opening chapter", 1]])
                fixture.set_metadata({"title": "Reading notes"})
                fixture.save(pdf)
            originals = [p.read_bytes() for p in (image, pdf)]
            output = add_cover(image, pdf)
            with pymupdf.open(output) as result:
                self.assertEqual(len(result), 2)
                self.assertTrue(result[0].get_images())
                self.assertIn("Chapter one", result[1].get_text())
                self.assertEqual(result.get_toc(), [[1, "Opening chapter", 2]])
                self.assertEqual(result.metadata["title"], "Reading notes")
            saved = output.read_bytes()
            with self.assertRaises(FileExistsError):
                add_cover(image, pdf)
            self.assertEqual(saved, output.read_bytes())
            self.assertEqual(originals, [p.read_bytes() for p in (image, pdf)])

    def test_invalid_cover_leaves_only_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / "book.pdf"
            image = folder / "bad.png"
            with pymupdf.open() as book:
                book.new_page()
                book.save(pdf)
            image.write_bytes(b"invalid")
            with self.assertRaises((RuntimeError, ValueError, pymupdf.mupdf.FzErrorBase)):
                add_cover(image, pdf)
            self.assertEqual(set(folder.iterdir()), {pdf, image})
