import os
from unittest.mock import Mock

import pytest

import zotero_add_book as importer


@pytest.fixture
def library(tmp_path, monkeypatch):
    downloads = tmp_path / "books"
    storage = tmp_path / "linked files"
    downloads.mkdir()
    storage.mkdir()
    zot = Mock()
    monkeypatch.setattr(importer, "book_dir", downloads, raising=False)
    monkeypatch.setattr(importer, "dropbox_zotero_storage_dir", storage, raising=False)
    monkeypatch.setattr(importer, "get_zot", lambda: zot)
    monkeypatch.setattr(importer, "create_book_template", lambda *_: {"itemType": "book"})
    monkeypatch.setattr(importer, "get_linked_url", lambda: "https://example.org/book\n")
    info = {"title": "A/B $(echo test)", "author_name_parts": [("", "O'Neil")], "publish_year": "2020"}
    return downloads, storage, zot, info


def test_missing_pdf_creates_no_book(library):
    _, _, zot, info = library
    with pytest.raises(FileNotFoundError, match="No PDF"):
        importer.zot_add_book(info)
    zot.create_items.assert_not_called()


def test_copy_newest_and_refuse_repeat(library):
    downloads, storage, zot, info = library
    older = downloads / "older.pdf"
    older.write_bytes(b"first")
    os.utime(older, (1, 1))
    newer = downloads / "a publisher's book.pdf"
    newer.write_bytes(b"second")
    zot.create_items.side_effect = [{"successful": {"0": {"key": key}}} for key in ("BOOK", "PDF", "URL")]
    importer.zot_add_book(info)
    saved, = storage.iterdir()
    assert saved.name == "O_Neil_2020_A_B $(echo test).pdf"
    assert saved.read_bytes() == newer.read_bytes() == b"second"
    _, pdf_call, url_call = zot.create_items.call_args_list
    assert pdf_call.args[0][0]["path"] == "attachments:" + saved.name
    assert url_call.args[0][0]["url"] == "https://example.org/book"
    assert pdf_call.args[1] == url_call.args[1] == "BOOK"
    newer.write_bytes(b"different")
    with pytest.raises(FileExistsError):
        importer.zot_add_book(info)
    assert zot.create_items.call_count == 3
    assert saved.read_bytes() == b"second"


def test_rejected_book_stops_attachments_and_preserves_copy(library):
    downloads, storage, zot, info = library
    (downloads / "book.pdf").write_bytes(b"pdf")
    zot.create_items.return_value = {"failed": {"0": {"message": "invalid metadata"}}}
    with pytest.raises(RuntimeError, match="invalid metadata"):
        importer.zot_add_book(info)
    zot.create_items.assert_called_once()
    saved, = storage.iterdir()
    assert saved.read_bytes() == b"pdf"
