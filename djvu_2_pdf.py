#!/usr/bin/env python3

import os
import sys
import re

def rm_invalid_chars(filename):
    filename_replace_invalid_chars = re.sub('[^A-Za-z0-9._-]', '_', filename)
    if os.path.exists(filename):
        os.rename(filename, filename_replace_invalid_chars)
    return filename_replace_invalid_chars

djvu = rm_invalid_chars(sys.argv[1])
djvu2pdf = djvu.replace('.djvu', '.pdf')
ocr_pdf = djvu2pdf.replace('.pdf', '.ocr.pdf')

# Use ddjvu to convert djvu to pdf
os.system('ddjvu -format=pdf -quality=150 -verbose {} {}'.format(djvu, djvu2pdf))

print('Start ocr pdf...')
# Use ocrmypdf to ocr pdf
os.system('ocrmypdf {} {}'.format(djvu2pdf, ocr_pdf))
