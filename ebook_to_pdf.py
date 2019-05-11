import sys
import os

ebook = sys.argv[1]
pdf_name = ebook.split('.')[0] + '.pdf'

# use Calibre ebook converter to convert to pdf
os.system("ebook-convert {} {} --pdf-page-numbers --pretty-print --minimum-line-height=1.5 --change-justification='justify'".format(ebook, pdf_name))
