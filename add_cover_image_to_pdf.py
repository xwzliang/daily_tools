#!/usr/bin/env python3
"""Prepend a cover image to a PDF using PyMuPDF."""

import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from daily_tools_lib.publication import move_without_overwrite


def add_cover(image_path, pdf_path):
    import pymupdf

    destination = pdf_path.with_name(pdf_path.stem + "_final.pdf")
    if os.path.lexists(destination):
        raise FileExistsError(f"Output already exists: {destination}")

    with pymupdf.open(pdf_path) as book, pymupdf.open(image_path) as image:
        if not book.is_pdf or book.needs_pass:
            raise ValueError("The book must be a readable, unlocked PDF")
        with pymupdf.open("pdf", image.convert_to_pdf()) as cover:
            book.insert_pdf(cover, start_at=0)
        with TemporaryDirectory(dir=destination.parent) as staging:
            staged = Path(staging) / "covered.pdf"
            book.save(staged, encryption=pymupdf.PDF_ENCRYPT_KEEP)
            move_without_overwrite(staged, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        print(add_cover(args.image, args.pdf))
    except ImportError as error:
        sys.exit(f"Could not load PyMuPDF: {error}")
    except Exception as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
