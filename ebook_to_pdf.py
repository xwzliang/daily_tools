#!/usr/bin/env python3

import argparse
import ctypes
import errno
import sys
import shutil
import tempfile
from pathlib import Path
import os
import re
import glob
import subprocess
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote


EXTRA_CONVERSION_CSS = (
    "* { "
    "font-variant-ligatures: none !important; "
    'font-feature-settings: "liga" 0, "clig" 0, "dlig" 0 !important; '
    '-webkit-font-feature-settings: "liga" 0, "clig" 0, "dlig" 0 !important; '
    "text-rendering: optimizeSpeed !important; "
    "}"
)


def clean_author(author):
    parts = [part.strip() for part in author.split(",")]
    parts = [
        part
        for part in parts
        if part
        and not re.search(r"\b(author|editor|translator|contributor)\b", part, flags=re.IGNORECASE)
        and not re.fullmatch(r"\d{3,4}(?:-\d{0,4})?", part)
    ]
    return " ".join(parts).strip()


def find_year(parts):
    for part in parts:
        if re.search(r"^(?:isbn\d*|[0-9a-f]{32,}|Anna['’]s Archive)", part, flags=re.IGNORECASE):
            break

        match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", part)
        if match:
            return match.group(1)

    return ""


def clean_ebook_filename(ebook_path, preserve_unicode=False):
    """
    Clean ebook filename by:
    1. Keeping title, author, and year for Anna's Archive filename exports
    2. Removing ISBN part (e.g., "isbn13 9780307377906")
    3. Removing hash and everything after it (e.g., " -- 0a0f25abf0c76a9162411698d795c7e0")
    4. Replacing remaining invalid characters
    """
    directory = os.path.dirname(ebook_path)
    filename = os.path.basename(ebook_path)
    
    # Split into name and extension
    name, ext = os.path.splitext(filename)

    # Anna's Archive names are usually "Title -- author -- edition -- ... -- isbn -- hash -- Anna's Archive".
    if re.search(r"\s*--\s*Anna['’]s Archive\s*$", name, flags=re.IGNORECASE):
        parts = [part.strip() for part in name.split(" -- ")]
        title = parts[0] if parts else ""
        author = clean_author(parts[1]) if len(parts) > 1 else ""
        year = find_year(parts[2:]) if len(parts) > 2 else ""
        name = "_".join(part for part in (title, author, year) if part)
    
    # Remove ISBN part (e.g., "isbn13 9780307377906")
    name = re.sub(r'\s*--\s*isbn\d*\s*[\d\-]+', '', name, flags=re.IGNORECASE)
    
    # Remove hash part (32 or more hex characters) and everything after it
    # This matches " -- " followed by hex characters and removes everything from there onwards
    name = re.sub(r'\s*--\s*[0-9a-f]{32,}(\s*--.*)?$', '', name, flags=re.IGNORECASE)
    
    # Strip trailing whitespace and dashes
    name = name.rstrip(' -')
    
    # Replace remaining invalid characters with underscores
    allowed = r"[^\w.-]" if preserve_unicode else r"[^A-Za-z0-9._-]"
    name_cleaned = re.sub(allowed, "_", name)
    
    return os.path.join(directory, name_cleaned + ext)


def heading_toc_options(archive, opf_path, items, spine, ns):
    """Map heading ranks to TOC levels, ignoring headings before the first root.

    Some EPUBs put subtitle/author h3s before their first part h2. Read in
    spine order (including across files) so those do not become TOC entries.
    """
    headings = []
    by_id = {item.get("id"): item for item in items}
    for ref in spine if spine is not None else []:
        item = by_id.get(ref.get("idref"))
        if item is None or ref.get("linear") == "no":
            continue
        path = posixpath.normpath(posixpath.join(
            posixpath.dirname(opf_path), unquote(item.get("href", ""))))
        try:
            document = ET.fromstring(archive.read(path))
        except (KeyError, ET.ParseError):
            continue
        for element in document.iter():
            for rank in (1, 2, 3):
                if element.tag == "{" + ns["h"] + "}h" + str(rank):
                    text = " ".join("".join(element.itertext()).split())
                    if text:
                        headings.append((rank, text))
    ranks = sorted({rank for rank, _ in headings}) or [1, 2, 3]
    excluded = []
    for rank, text in headings:
        if rank == ranks[0]:
            break
        excluded.append(text)

    def xpath_literal(text):
        if "'" not in text:
            return "'" + text + "'"
        return "concat(" + ", \"'\", ".join("'" + part + "'" for part in text.split("'")) + ")"

    predicate = "".join(
        "[normalize-space(.) != " + xpath_literal(text) + "]" for text in excluded)
    return ["--use-auto-toc"] + [
        f"--level{level}-toc=//h:h{rank}{predicate}"
        for level, rank in enumerate(ranks, 1)
    ]


def epub_toc_options(ebook):
    """Rebuild missing/placeholder EPUB navigation, leaving useful TOCs intact."""
    if not ebook.lower().endswith(".epub"):
        return []

    ns = {
        "container": "urn:oasis:names:tc:opendocument:xmlns:container",
        "opf": "http://www.idpf.org/2007/opf",
        "ncx": "http://www.daisy.org/z3986/2005/ncx/",
        "h": "http://www.w3.org/1999/xhtml",
    }
    try:
        with zipfile.ZipFile(ebook) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find("container:rootfiles/container:rootfile", ns)
            opf_path = rootfile.attrib["full-path"]
            package = ET.fromstring(archive.read(opf_path))
            items = package.findall("opf:manifest/opf:item", ns)
            spine = package.find("opf:spine", ns)
            ncx_id = spine.get("toc") if spine is not None else None
            labels = []
            for item in items:
                is_nav = "nav" in item.get("properties", "").split()
                is_ncx = (item.get("id") == ncx_id or
                          item.get("media-type") == "application/x-dtbncx+xml")
                if not (is_nav or is_ncx):
                    continue
                path = posixpath.normpath(posixpath.join(
                    posixpath.dirname(opf_path), unquote(item.attrib["href"])))
                try:
                    navigation = ET.fromstring(archive.read(path))
                except (KeyError, ET.ParseError):
                    continue  # Missing/broken navigation can be rebuilt from headings.
                if is_nav:
                    for nav in navigation.findall(".//h:nav", ns):
                        kind = nav.get("{http://www.idpf.org/2007/ops}type", "")
                        if "toc" in kind.split():
                            labels.extend(" ".join(a.itertext()).strip()
                                          for a in nav.findall(".//h:a", ns)
                                          if a.get("href"))
                else:
                    for point in navigation.findall(".//ncx:navPoint", ns):
                        label = point.find("ncx:navLabel", ns)
                        content = point.find("ncx:content", ns)
                        if label is not None and content is not None and content.get("src"):
                            labels.append(" ".join(label.itertext()).strip())
            if any(label and label.casefold() != "start" for label in labels):
                return []
            options = heading_toc_options(archive, opf_path, items, spine, ns)
    except (OSError, zipfile.BadZipFile, KeyError, AttributeError, ET.ParseError) as error:
        # Let Calibre handle inputs we cannot inspect; never override unknown navigation.
        print(f"Could not inspect EPUB navigation: {error}", file=sys.stderr)
        return []

    print("EPUB navigation is missing or only Start; generating TOC from headings.")
    return options


def render_pdf(ebook, pdf_name):
    """Run Calibre with the existing navigation and typography settings."""
    subprocess.run(
        [
            "ebook-convert",
            ebook,
            pdf_name,
            *epub_toc_options(ebook),
            "--output-profile=tablet",
            "--minimum-line-height=1.5",
            "--change-justification=justify",
            "--filter-css=background-color,background",
            f"--extra-css={EXTRA_CONVERSION_CSS}",
            "--pdf-page-margin-left=72",
            "--pdf-page-margin-right=72",
            "--pdf-page-margin-top=72",
            "--pdf-page-margin-bottom=72",
        ],
        check=True,
    )


def move_without_overwrite(source, destination):
    """Move within a filesystem, atomically refusing an occupied destination."""
    if sys.platform == "win32":
        os.rename(source, destination)  # Windows rename refuses existing files.
        return
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        src, dst = os.fsencode(source), os.fsencode(destination)
        if sys.platform == "darwin":
            result = libc.renamex_np(src, dst, 4)  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            result = libc.renameat2(-100, src, -100, dst, 1)  # AT_FDCWD, RENAME_NOREPLACE
        else:
            result = -1
            ctypes.set_errno(errno.ENOSYS)
        if result == 0:
            return
        code = ctypes.get_errno()
        if code not in (errno.ENOSYS, errno.ENOTSUP, errno.EINVAL):
            raise OSError(code, os.strerror(code), str(destination))
    os.link(source, destination, follow_symlinks=False)
    os.unlink(source)


def convert_book(ebook, output_dir=None, dry_run=False):
    """Publish a complete PDF without clobbering an existing destination."""
    source = Path(ebook)
    cleaned = Path(clean_ebook_filename(str(source), preserve_unicode=output_dir is not None))
    rename = output_dir is None and cleaned != source
    destination = (Path(output_dir) / cleaned.name if output_dir is not None else cleaned).with_suffix(".pdf")
    is_pdf = source.suffix.lower() == ".pdf"
    if is_pdf and output_dir is None:
        destination = cleaned
    if rename and os.path.lexists(cleaned):
        if not cleaned.samefile(source):
            raise FileExistsError(f"Normalized name already in use: {cleaned}")
        rename = False
    if os.path.lexists(destination):
        if is_pdf and destination.samefile(source):
            print(f"Already a PDF: {source}")
            return
        raise FileExistsError(f"Output already exists: {destination}")
    if dry_run:
        print(f"{source} -> {destination}")
        return
    if output_dir is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
    if not (is_pdf and output_dir is None):
        with tempfile.TemporaryDirectory(prefix=".ebook-pdf-", dir=destination.parent) as tmp:
            staged = Path(tmp) / "output.pdf"
            if is_pdf:
                shutil.copy2(source, staged)
            else:
                render_pdf(str(source), str(staged))
            if not staged.is_file() or staged.stat().st_size == 0:
                raise OSError(f"Converter produced an empty PDF for {source}")
            move_without_overwrite(staged, destination)
    if rename:
        # Preserve legacy normalized names without replacing another input.
        move_without_overwrite(source, cleaned)
    print(f"Ready: {destination}")


def main():
    parser = argparse.ArgumentParser(description="Convert ebooks with Calibre, preserving useful EPUB navigation.")
    parser.add_argument("--output-dir", type=Path, help="write PDFs here and keep source files in place")
    parser.add_argument("--dry-run", action="store_true", help="show output paths without writing or converting")
    parser.add_argument("books", nargs="*", help="files or quoted glob patterns; no arguments watches the current directory")
    args = parser.parse_args()
    if args.books:
        failures = 0
        seen = set()
        for pattern in args.books:
            matches = [pattern] if os.path.isfile(pattern) else sorted(glob.glob(pattern))
            files = [path for path in matches if os.path.isfile(path)]
            if not files:
                print(f"No matching file: {pattern}", file=sys.stderr)
                failures += 1
            for path in files:
                key = os.path.abspath(path)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    convert_book(path, args.output_dir, args.dry_run)
                except (OSError, subprocess.CalledProcessError) as error:
                    print(f"Skipped {path}: {error}", file=sys.stderr)
                    failures += 1
        return int(failures > 0)
    elif args.output_dir is not None or args.dry_run:
        parser.error("specify at least one input file or pattern")
    else:
        import time

        cwd = os.getcwd()
        old_list_of_files = os.listdir(cwd)

        while True:  # Monitor the cwd
            time.sleep(2)
            new_list_of_files = os.listdir(cwd)
            if len(new_list_of_files) > len(old_list_of_files):  # New file added
                # get the latest file as ebook
                ebook = max(new_list_of_files, key=os.path.getctime)
                if (
                    ".pdf" not in ebook and ".jpg" not in ebook
                ):  # Don't convert pdf file and jpg
                    try:
                        convert_book(ebook)
                    except (OSError, subprocess.CalledProcessError) as error:
                        print(f"Skipped {ebook}: {error}", file=sys.stderr)
                    time.sleep(2)
            # Update the list of files
            old_list_of_files = os.listdir(cwd)


if __name__ == "__main__":
    sys.exit(main())
