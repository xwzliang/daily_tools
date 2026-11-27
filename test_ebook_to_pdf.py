import tempfile
import unittest
import zipfile
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from ebook_to_pdf import BookInbox, epub_toc_options, convert_book, heading_toc_options, render_pdf, spine_headings


class TocFallbackTests(unittest.TestCase):
    def options(self, labels=(), nav=False, broken=False, absent=False, documents=()):
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory) / 'book.epub'
            with zipfile.ZipFile(book, 'w') as archive:
                archive.writestr('META-INF/container.xml', '''<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>''')
                item = '<item id="toc" href="toc.xml" ' + ('properties="nav"' if nav else 'media-type="application/x-dtbncx+xml"') + '/>'
                if absent:
                    item = ''
                spine = ''
                for index, body in enumerate(documents):
                    name = f'chapter{index}.xhtml'
                    item += f'<item id="chapter{index}" href="{name}" media-type="application/xhtml+xml"/>'
                    spine += f'<itemref idref="chapter{index}"/>'
                    archive.writestr('OEBPS/' + name, self.xhtml(body))
                archive.writestr('OEBPS/content.opf', '<package xmlns="http://www.idpf.org/2007/opf"><manifest>' + item + '</manifest><spine toc="toc">' + spine + '</spine></package>')
                if not broken:
                    entries = [(label, 'chapter.xhtml') if isinstance(label, str) else label
                               for label in labels]
                    if nav:
                        text = '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><nav epub:type="toc"><ol>' + ''.join(f'<li><a href="{href}">{label}</a></li>' for label, href in entries) + '</ol></nav><nav epub:type="landmarks"><a href="cover.xhtml">Cover</a></nav></html>'
                    else:
                        text = '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>' + ''.join(f'<navPoint><navLabel><text>{label}</text></navLabel><content src="{href}"/></navPoint>' for label, href in entries) + '</navMap></ncx>'
                    archive.writestr('OEBPS/toc.xml', text)
            return epub_toc_options(str(book))

    @staticmethod
    def xhtml(body):
        return '<html xmlns="http://www.w3.org/1999/xhtml">' + body + '</html>'

    def heading_options(self, documents):
        ns = {"h": "http://www.w3.org/1999/xhtml"}
        data = io.BytesIO()
        items = []
        spine = ET.Element("spine")
        with zipfile.ZipFile(data, "w") as archive:
            for index, body in enumerate(documents):
                name = f"{index}.xhtml"
                archive.writestr(name, self.xhtml(body))
                items.append(ET.Element("item", id=str(index), href=name))
                ET.SubElement(spine, "itemref", idref=str(index))
            return heading_toc_options(spine_headings(archive, "content.opf", items, spine, ns))

    def test_parts_chapters_and_front_matter_across_files(self):
        options = self.heading_options([
            '<h3>Subtitle</h3><h3>Author</h3>',
            '<h2>Part One</h2><h3>1 Chapter</h3>',
            '<h3>2 Chapter</h3><h2>Part Two</h2><h3>3 Chapter</h3>',
        ])
        self.assertEqual(len(options), 3)
        self.assertTrue(options[1].startswith('--level1-toc=//h:h2'))
        self.assertTrue(options[2].startswith('--level2-toc=//h:h3'))
        self.assertIn("[normalize-space(.) != 'Subtitle'][normalize-space(.) != 'Author']", options[2])

    def test_single_rank_and_three_ranks(self):
        single = self.heading_options(['<h3>Chapter</h3>'])
        self.assertEqual(len(single), 2)
        self.assertTrue(single[1].startswith('--level1-toc=//h:h3'))
        nested = self.heading_options(['<h1>Part</h1><h2>Chapter</h2><h3>Section</h3>'])
        self.assertEqual(len(nested), 4)
        for rank in (1, 2, 3):
            self.assertTrue(nested[rank].startswith(f'--level{rank}-toc=//h:h{rank}'))

    def test_detects_missing_chapter_even_with_later_bookmarks(self):
        documents = [
            '<h1>Title Page</h1>',
            '<h1 id="one">Chapter One</h1><h2>Optional subsection</h2>',
            '<h1 id="two">Chapter Two</h1><h1 id="three">Chapter Three</h1>',
            '<h1>Appendix</h1>',
        ]
        entries = [
            ('First', 'chapter1.xhtml#one'),
            ('Second', 'chapter2.xhtml'),
            ('Appendix', 'chapter3.xhtml'),
        ]
        for nav in (False, True):
            with self.subTest(nav=nav):
                self.assertIn('--use-auto-toc', self.options(entries[:-1], nav, documents=documents))
                self.assertIn('--use-auto-toc', self.options(entries, nav, documents=documents))
                complete = entries + [('Third', 'chapter2.xhtml#three')]
                self.assertEqual([], self.options(complete, nav, documents=documents))

    def test_missing_empty_and_start_navigation(self):
        for nav in (False, True):
            for labels in ((), ('Start',), (' start ',)):
                with self.subTest(nav=nav, labels=labels):
                    self.assertIn('--use-auto-toc', self.options(labels, nav))
            self.assertIn('--use-auto-toc', self.options(nav=nav, broken=True))

    def test_no_navigation_manifest_item(self):
        self.assertIn('--use-auto-toc', self.options(absent=True))

    def test_preserves_valid_navigation(self):
        for nav in (False, True):
            for labels in (('Chapter One',), ('Start', 'Chapter One')):
                with self.subTest(nav=nav, labels=labels):
                    self.assertEqual([], self.options(labels, nav))

    def test_non_epub_and_unreadable_input(self):
        self.assertEqual([], epub_toc_options('book.mobi'))
        self.assertEqual([], epub_toc_options('/nonexistent/book.epub'))

    @patch('ebook_to_pdf.epub_toc_options', return_value=['--use-auto-toc'])
    @patch('ebook_to_pdf.subprocess.run')
    def test_conversion_passes_fallback_options(self, run, options):
        render_pdf('book.epub', 'book.pdf')
        self.assertIn('--use-auto-toc', run.call_args.args[0])
        self.assertTrue(run.call_args.kwargs['check'])



class SafeConversionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.source = self.folder / "第一 章.epub"
        self.source.write_bytes(b"source fixture")

    def test_preview_creates_no_directory(self):
        destination = self.folder / "new"
        convert_book(self.source, destination, dry_run=True)
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), b"source fixture")

    def test_output_directory_preserves_original_and_unicode(self):
        destination = self.folder / "out"
        with patch("ebook_to_pdf.render_pdf", side_effect=lambda src, out: Path(out).write_bytes(b"%PDF-fixture")):
            convert_book(self.source, destination)
        self.assertEqual((destination / "第一_章.pdf").read_bytes(), b"%PDF-fixture")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        with self.assertRaises(FileExistsError):
            convert_book(self.source, destination)

    def test_existing_normalized_source_is_not_overwritten(self):
        occupied = self.folder / "my_book.epub"
        occupied.write_bytes(b"another book")
        original = self.folder / "my book.epub"
        original.write_bytes(b"original book")
        with self.assertRaises(FileExistsError):
            convert_book(original)
        self.assertEqual(original.read_bytes(), b"original book")
        self.assertEqual(occupied.read_bytes(), b"another book")

    def test_failed_converter_does_not_publish_or_rename(self):
        def fail(src, out):
            Path(out).write_bytes(b"partial")
            raise OSError("interrupted")
        with patch("ebook_to_pdf.render_pdf", side_effect=fail), self.assertRaises(OSError):
            convert_book(self.source)
        self.assertEqual(list(self.folder.iterdir()), [self.source])

    def test_concurrent_publication_preserves_winner(self):
        out = self.folder / "out"
        def race(src, staged):
            Path(staged).write_bytes(b"late result")
            (out / "第一_章.pdf").write_bytes(b"first result")
        with patch("ebook_to_pdf.render_pdf", side_effect=race), self.assertRaises(FileExistsError):
            convert_book(self.source, out)
        self.assertEqual((out / "第一_章.pdf").read_bytes(), b"first result")

class BookInboxTests(unittest.TestCase):
    def test_bursts_replacements_and_writes_in_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            old = folder / "already there.txt"
            old.write_text("existing")
            inbox = BookInbox(folder)
            self.assertEqual(inbox.ready(), [])
            a, b = folder / "A.txt", folder / "B.EPUB"
            old.unlink()
            a.write_text("in progress")
            b.write_text("complete")
            (folder / "Other.pdf").write_text("output")
            (folder / "partial.epub.part").write_text("unfinished")
            (folder / "alias.epub").symlink_to(a)
            (folder / ".hidden.epub").write_text("hidden")
            self.assertEqual(inbox.ready(), [])
            a.write_text("finally complete")
            self.assertEqual([p for p, _ in inbox.ready()], [b])
            self.assertEqual([p for p, _ in inbox.ready()], [a])
            a.rename(folder / "normalized.txt")
            self.assertEqual(inbox.ready(), [])
            self.assertEqual(inbox.ready(), [])
            old.write_text("replaced")
            self.assertEqual(inbox.ready(), [])
            self.assertEqual([p for p, _ in inbox.ready()], [old])

    def test_simultaneous_complete_books(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            inbox = BookInbox(folder)
            for name in ["c.txt", "a.txt", "b.txt"]:
                (folder / name).write_text(name)
            self.assertEqual(inbox.ready(), [])
            self.assertEqual([p.name for p, _ in inbox.ready()], ["a.txt", "b.txt", "c.txt"])
            self.assertEqual(inbox.ready(), [])

    def test_changed_input_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "book.txt"
            source.write_text("first revision")
            def render(src, staged):
                Path(staged).write_bytes(b"%PDF-test")
                Path(src).write_text("new revision while converting")
            with patch("ebook_to_pdf.render_pdf", side_effect=render), self.assertRaisesRegex(OSError, "Input changed"):
                convert_book(source, folder / "out")
            self.assertEqual(list((folder / "out").iterdir()), [])
            self.assertEqual(source.read_text(), "new revision while converting")


if __name__ == '__main__':
    unittest.main()
