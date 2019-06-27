#!/usr/bin/python3

import sys
import os
import re

if len(sys.argv) > 1:
    ebook = sys.argv[1]
else:
    # get the latest file as ebook
    import glob
    cwd = os.getcwd()
    list_of_files = glob.glob(os.path.join(cwd, '*'))
    latest_file = max(list_of_files, key=os.path.getctime)
    ebook = os.path.basename(latest_file)

# Remove invalid chars
ebook_replace_invalid_chars = re.sub('[^A-Za-z0-9._-]', '_', ebook)
pdf_name = ebook_replace_invalid_chars.split('.')[0] + '.pdf'
os.rename(ebook, ebook_replace_invalid_chars)

# use Calibre ebook converter to convert to pdf
os.system("ebook-convert {} {} --pdf-page-numbers --pretty-print --minimum-line-height=1.5 --change-justification='justify'".format(ebook_replace_invalid_chars, pdf_name))
