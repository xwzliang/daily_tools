#!/usr/bin/python3

import os
import sys

cover_image = sys.argv[1]
pdf = sys.argv[2]

cover_pdf = cover_image.split('.')[0] + '_cover.pdf'
out_pdf = pdf.replace('.pdf', '_final.pdf')

# Use convert to convert image to pdf
os.system('convert {} {}'.format(cover_image, cover_pdf))

# Use qpdf to concatnate cover_pdf and pdf
os.system('qpdf --empty --pages {} {} -- {}'.format(cover_pdf, pdf, out_pdf))

if os.path.exists(out_pdf):
    os.system('rm {} {}'.format(cover_image, cover_pdf))
