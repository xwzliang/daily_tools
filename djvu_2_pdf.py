#!/usr/bin/env python3
"""Convert a DjVu book to a PDF and, by default, a searchable OCR copy."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from daily_tools_lib.publication import move_without_overwrite


def convert(source, *, ocr=True):
    if source.suffix.lower() not in {".djvu", ".djv"}:
        raise ValueError(f"Expected a .djvu or .djv file: {source}")
    if not source.is_file():
        raise FileNotFoundError(f"Input file not found: {source}")
    pdf = source.with_suffix(".pdf")
    outputs = [pdf]
    if ocr:
        outputs.append(source.with_suffix(".ocr.pdf"))
    for destination in outputs:
        if os.path.lexists(destination):
            raise FileExistsError(f"Output already exists: {destination}")

    with TemporaryDirectory(prefix=".djvu-pdf-", dir=source.parent) as tmp:
        decoded = Path(tmp).absolute() / "decoded.pdf"
        subprocess.run(["ddjvu", "-format=pdf", "-quality=150", "-verbose",
                        source.absolute(), decoded], check=True)
        staged = [decoded]
        if ocr:
            searchable = decoded.with_name("searchable.pdf")
            subprocess.run(["ocrmypdf", decoded, searchable], check=True)
            staged.append(searchable)
        for path in staged:
            with path.open("rb") as candidate:
                if candidate.read(5) != b"%PDF-":
                    raise ValueError(f"Conversion produced no PDF in {path.name}")
        for path, destination in zip(staged, outputs):
            move_without_overwrite(path, destination)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--no-ocr", action="store_true", help="create only the image PDF using ddjvu")
    args = parser.parse_args()
    try:
        for output in convert(args.source, ocr=not args.no_ocr):
            print(output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
