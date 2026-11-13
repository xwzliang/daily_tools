import tempfile
import unittest
import zipfile
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from ebook_to_pdf import epub_toc_options, convert_book, heading_toc_options


class TocFallbackTests(unittest.TestCase):
    def options(self, labels=(), nav=False, broken=False, absent=False):
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory) / 'book.epub'
            with zipfile.ZipFile(book, 'w') as archive:
                archive.writestr('META-INF/container.xml', '''<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>''')
                item = '<item id="toc" href="toc.xml" ' + ('properties="nav"' if nav else 'media-type="application/x-dtbncx+xml"') + '/>'
                if absent:
                    item = ''
                archive.writestr('OEBPS/content.opf', '<package xmlns="http://www.idpf.org/2007/opf"><manifest>' + item + '</manifest><spine toc="toc"/></package>')
                if not broken:
                    if nav:
                        text = '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><nav epub:type="toc"><ol>' + ''.join(f'<li><a href="chapter.xhtml">{label}</a></li>' for label in labels) + '</ol></nav><nav epub:type="landmarks"><a href="cover.xhtml">Cover</a></nav></html>'
                    else:
                        text = '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>' + ''.join(f'<navPoint><navLabel><text>{label}</text></navLabel><content src="chapter.xhtml"/></navPoint>' for label in labels) + '</navMap></ncx>'
                    archive.writestr('OEBPS/toc.xml', text)
            return epub_toc_options(str(book))

    def heading_options(self, documents):
        ns = {"h": "http://www.w3.org/1999/xhtml"}
        data = io.BytesIO()
        items = []
        spine = ET.Element("spine")
        with zipfile.ZipFile(data, "w") as archive:
            for index, body in enumerate(documents):
                name = f"{index}.xhtml"
                archive.writestr(name, '<html xmlns="' + ns["h"] + '">' + body + '</html>')
                items.append(ET.Element("item", id=str(index), href=name))
                ET.SubElement(spine, "itemref", idref=str(index))
            return heading_toc_options(archive, "content.opf", items, spine, ns)

    def test_parts_chapters_and_front_matter_across_files(self):
        options = self.heading_options([
            '<h3>Subtitle</h3><h3>Author</h3>',
            '<h2>Part One</h2><h3>1 Chapter</h3>',
            '<h3>2 Chapter</h3><h2>Part Two</h2><h3>3 Chapter</h3>',
        ])
        self.assertEqual(options, [
            '--use-auto-toc',
            "--level1-toc=//h:h2[normalize-space(.) != 'Subtitle'][normalize-space(.) != 'Author']",
            "--level2-toc=//h:h3[normalize-space(.) != 'Subtitle'][normalize-space(.) != 'Author']",
        ])

    def test_single_rank_and_three_ranks(self):
        self.assertEqual(self.heading_options(['<h3>Chapter</h3>']),
                         ['--use-auto-toc', '--level1-toc=//h:h3'])
        self.assertEqual(self.heading_options(['<h1>Part</h1><h2>Chapter</h2><h3>Section</h3>']),
                         ['--use-auto-toc', '--level1-toc=//h:h1',
                          '--level2-toc=//h:h2', '--level3-toc=//h:h3'])

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
        convert_book('book.epub')
        self.assertIn('--use-auto-toc', run.call_args.args[0])
        self.assertTrue(run.call_args.kwargs['check'])


if __name__ == '__main__':
    unittest.main()
