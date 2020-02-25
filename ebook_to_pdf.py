#!/usr/bin/env python3

import sys
import os
import re

def convert_book(ebook):
    # Remove invalid chars
    ebook_replace_invalid_chars = re.sub('[^A-Za-z0-9._-]', '_', ebook)
    pdf_name = ebook_replace_invalid_chars.split('.')[0] + '.pdf'
    os.rename(ebook, ebook_replace_invalid_chars)
    # use Calibre ebook converter to convert to pdf
    os.system("ebook-convert {} {} --pdf-page-numbers --pretty-print --minimum-line-height=1.5 --change-justification='justify'".format(ebook_replace_invalid_chars, pdf_name))


if len(sys.argv) > 1:
    ebook = sys.argv[1]
    convert_book(ebook)
else:
    import glob
    import time
    cwd = os.getcwd()
    old_list_of_files = os.listdir(cwd)

    while True:		# Monitor the cwd
        time.sleep(2)
        new_list_of_files = os.listdir(cwd)
        if len(new_list_of_files) > len(old_list_of_files):	# New file added
            # get the latest file as ebook
            ebook = max(new_list_of_files, key=os.path.getctime)
            if '.pdf' not in ebook and '.jpg' not in ebook:	# Don't convert pdf file and jpg
                convert_book(ebook)
                time.sleep(2)
        # Update the list of files
        old_list_of_files = os.listdir(cwd)

