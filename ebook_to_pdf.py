#!/usr/bin/env python3

import sys
import os
import re
import glob


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


def clean_ebook_filename(ebook_path):
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
    name_cleaned = re.sub("[^A-Za-z0-9._-]", "_", name)
    
    return os.path.join(directory, name_cleaned + ext)


def convert_book(ebook):
    """Convert ebook to PDF after renaming it"""
    # Clean and rename the file
    ebook_renamed = clean_ebook_filename(ebook)
    if ebook != ebook_renamed:
        print(f"Renaming: {ebook} -> {ebook_renamed}")
        os.rename(ebook, ebook_renamed)
        ebook = ebook_renamed
    
    # If it's already a PDF, just return (no conversion needed)
    if ebook.lower().endswith('.pdf'):
        return
    
    pdf_name = os.path.splitext(ebook)[0] + ".pdf"
    
    # use Calibre ebook converter to convert to pdf
    # os.system(
    #     "ebook-convert {} {} --pretty-print --minimum-line-height=1.5 --change-justification='justify'".format(
    #         ebook, pdf_name
    #     )
    # )
    os.system(
        "ebook-convert {} {} --output-profile=tablet --minimum-line-height=1.5 --change-justification='justify' --pdf-page-margin-left=72 --pdf-page-margin-right=72 --pdf-page-margin-top=72 --pdf-page-margin-bottom=72".format(
            ebook, pdf_name
        )
    )


def main():
    if len(sys.argv) > 1:
        # Handle multiple arguments (from shell expansion of wildcards) or glob patterns
        patterns = sys.argv[1:]
        files_to_process = []

        for pattern in patterns:
            # Shell-expanded globs may produce filenames with literal glob chars,
            # such as Anna's Archive names containing [United States_].
            if os.path.isfile(pattern):
                files_to_process.append(pattern)
            elif glob.has_magic(pattern):
                files_to_process.extend(glob.glob(pattern))
            else:
                files_to_process.append(pattern)

        if files_to_process:
            for ebook in files_to_process:
                if os.path.isfile(ebook):
                    convert_book(ebook)
        else:
            print("No matching files found")
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
                    convert_book(ebook)
                    time.sleep(2)
            # Update the list of files
            old_list_of_files = os.listdir(cwd)


if __name__ == "__main__":
    main()
