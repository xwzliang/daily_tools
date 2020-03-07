#!/usr/bin/env python3

from pathlib import Path
import urllib.request
import sys
import os
from bs4 import BeautifulSoup
import re
import pickle
from pyzotero import zotero

def parse_person_name(persons_name):
    authors_name = []
    authors = persons_name.split(", ")
    for author in authors:
        parts = author.split(" ")
        first_name = " ".join(parts[0:-1])
        last_name = parts[-1]
        authors_name.append((first_name, last_name))
    return authors_name

def extract_book_info(decode_html):
    book_info = {}
    soup = BeautifulSoup(decode_html, 'html.parser')
    meta = soup.find(name = "title")
    meta_str = meta.string
    # meta_str = "The Bullet Journal Method: Track the Past, Order the Present, Design the Future: Ryder Carroll: 9780525533337: Amazon.com: Books"
    # meta_str = "Amazon.com: A History of Modern Psychology (9781111344979): Duane P. Schultz, Sydney Ellen Schultz: Books"
    meta_item = meta_str.split(": ")
    if meta_item[0] == "Amazon.com":
        amazon_title = ": ".join(meta_item[1:-2])
        book_name = amazon_title.split(" (")[0]
        author_name = meta_item[-2]
    else:
        book_name = ": ".join(meta_item[0:-4])
        author_name = meta_item[-4]

    book_isbn = re.findall('<li><b>ISBN-13:</b> (.*)</li>', decode_html)[0]
    numPages = re.findall('<li><b>(?:Hardcover|Paperback):</b> ([0-9]+) pages</li>', decode_html)[0]

    publisher_and_date = re.findall('<li><b>Publisher:</b> (.*)</li>', decode_html)[0]
    publisher = publisher_and_date.split("(")[0].strip()
    if ";" in publisher:
        publisher_parts = publisher.split("; ")
        publisher = publisher_parts[0]
        edition = publisher_parts[1]
        book_info["edition"] = edition
    publish_date = publisher_and_date.split("(")[1].replace(")", "")
    publish_year = publish_date.split(" ")[-1]

    img_src = re.findall('class="a-dynamic-image.*id="imgBlkFront".* data-a-dynamic-image="{&quot;https://images-na.ssl-images-amazon.com/images/.*&quot;.*&quot;(https://images-na.ssl-images-amazon.com/images/.*)&quot;', decode_html)[0]
    print(img_src)

    book_info["title"] = book_name
    if ":" in book_name:
        shortTitle = meta_item[0]
        book_info["shortTitle"] = shortTitle
    book_info["author_name_parts"] = parse_person_name(author_name)
    book_info["numPages"] = numPages
    book_info["ISBN"] = book_isbn
    book_info["libraryCatalog"] = "Amazon"
    book_info["date"] = publish_date
    book_info["publish_year"] = publish_year
    book_info["publisher"] = publisher

    print(book_info)
    return book_info

def get_zot():
    with open(Path(zotero_api_key_file_path).expanduser(), 'r') as inf:
        library_id = inf.readline().strip()
        api_key = inf.readline().strip()
    library_type = "user"
    zot = zotero.Zotero(library_id, library_type, api_key)
    return zot

def get_collection_keys(collections_of_item):
    with open(Path(zotero_collections_file_path).expanduser(), "rb") as inf:
        zot_collections = pickle.load(inf)
    collection_keys = {}
    for zot_collection in zot_collections:
        for collection_of_item in collections_of_item:
            if zot_collection['data']['name'] == collection_of_item:
                collection_keys[collection_of_item] = zot_collection['data']['key']
    for collection_of_item in collections_of_item:
        if collection_of_item not in collection_keys:
            raise ValueError("{} not in current librabry!".format(collection_of_item))
    return [key for key in collection_keys.values()]

def get_my_tags():
    tags = {
        "1": "01_Excellent",
        "2": "02_Important",
        "3": "03_Worthwhile",
        "4": "04_Optional",
        "5": "05_Trivial",
        "6": "06_Careful",
    }
    return tags

def set_tags():
    tags = get_my_tags()
    tags_input = [x.strip() for x in sys.argv[2].split(",")]
    for tag_input in tags_input:
        if tag_input not in tags:
            raise ValueError("{} not in current librabry!".format(tag_input))
    tags_for_book = [{"tag": tags[x]} for x in tags_input]
    return tags_for_book

def create_book_template(zot, book_info):
    # book_template = zot.item_template('book')
    book_template = {'itemType': 'book', 'title': '', 'creators': [{'creatorType': 'author', 'firstName': '', 'lastName': ''}], 'abstractNote': '', 'series': '', 'seriesNumber': '', 'volume': '', 'numberOfVolumes': '', 'edition': '', 'place': '', 'publisher': '', 'date': '', 'numPages': '', 'language': '', 'ISBN': '', 'shortTitle': '', 'url': '', 'accessDate': '', 'archive': '', 'archiveLocation': '', 'libraryCatalog': '', 'callNumber': '', 'rights': '', 'extra': '', 'tags': [], 'collections': [], 'relations': {}}
    book_template['title'] = book_info["title"]
    book_template['tags'] = set_tags()
    authors_name = book_info["author_name_parts"]
    book_template['creators'][0]['firstName'] = authors_name[0][0]
    book_template['creators'][0]['lastName'] = authors_name[0][1]
    if len(authors_name) > 1:
        for i in range(1, len(authors_name)):
            creators_dict = book_template['creators'][0].copy()
            creators_dict['firstName'] = authors_name[i][0]
            creators_dict['lastName'] = authors_name[i][1]
            book_template['creators'].append(creators_dict)
    for info_type in ["edition", "publisher", "date", "numPages", "language", "ISBN", "shortTitle", "libraryCatalog"]:
        if info_type in book_info:
            book_template[info_type] = book_info[info_type]
    collections_of_item = parse_collections_of_item()
    collection_keys = get_collection_keys(collections_of_item)
    book_template['collections'] = collection_keys
    return book_template
    
def create_book_item(zot, book_info):
    book_template = create_book_template(zot, book_info)
    resp = zot.create_items([book_template])
    if '0' in resp['successful']:
        item_key = resp['successful']['0']['key']
        print(item_key)
        return item_key
    else:
        # Create book failed
        print(resp)
   
def set_pdf_name(book_info):
    # Renaming rule: {%a_}{%y_}{%t}
    # %a = author last name; %y = year; %t = title
    if "shortTitle" in book_info:
        pdf_title = book_info["shortTitle"]
    else:
        pdf_title = book_info["title"]
    author_name_parts = book_info["author_name_parts"]
    if len(author_name_parts) > 1:
        if len(author_name_parts) > 2:
            pdf_author = "{} et al".format(author_name_parts[0][1])
        else:
            pdf_author = "{}_{}".format(author_name_parts[0][1], author_name_parts[1][1])
    else:
        pdf_author = author_name_parts[0][1]
    if book_info["publish_year"]:
        pdf_name = "{}_{}_{}.pdf".format(pdf_author, book_info["publish_year"], pdf_title)
    else:
        pdf_name = "{}_{}.pdf".format(pdf_author, pdf_title)
    # return pdf_name.replace(" ", "_")
    return pdf_name
    
def copy_pdf_to_dropbox(pdf_name):
    pdf_path = os.popen("newest {}/*.pdf".format(book_dir)).read().strip()
    target_pdf_path = "{}/{}".format(dropbox_zotero_storage_dir, pdf_name.replace(" ", "\\ "))
    os.system("cp '{}' {}".format(pdf_path, target_pdf_path))
    
def attach_pdf(zot, item_key, pdf_name):
    # linked_file_template = zot.item_template('attachment', 'linked_file')
    linked_file_template = {'itemType': 'attachment', 'linkMode': 'linked_file', 'title': '', 'accessDate': '', 'note': '', 'tags': [], 'collections': [], 'relations': {}, 'contentType': '', 'charset': '', 'path': ''} 
    linked_file_template['path'] = "attachments:{}".format(pdf_name)
    linked_file_template['contentType'] = "application/pdf"
    linked_file_template['title'] = pdf_name
    resp = zot.create_items([linked_file_template], item_key)
    if '0' in resp['successful']:
        pdf_item_key = resp['successful']['0']['key']
        print(pdf_item_key)
    else:
        print(resp)

def get_linked_url():
    with open(Path(linked_url_file_path).expanduser(), 'r') as inf:
        linked_url = inf.read()
    return linked_url

def attach_link(zot, item_key, linked_url):
    # linked_url_template = zot.item_template('attachment', 'linked_url')
    linked_url_template = {'itemType': 'attachment', 'linkMode': 'linked_url', 'title': '', 'accessDate': '', 'url': '', 'note': '', 'tags': [], 'collections': [], 'relations': {}, 'contentType': '', 'charset': ''}
    linked_url_template['title'] = "Amazon.com Link"
    linked_url_template['url'] = linked_url
    resp = zot.create_items([linked_url_template], item_key)
    if '0' in resp['successful']:
        link_item_key = resp['successful']['0']['key']
        print(link_item_key)
    else:
        print(resp)
 
def zot_add_book(book_info):
    zot = get_zot()
    item_key = create_book_item(zot, book_info)
    pdf_name = set_pdf_name(book_info)
    copy_pdf_to_dropbox(pdf_name)
    attach_pdf(zot, item_key, pdf_name)
    linked_url = get_linked_url()
    attach_link(zot, item_key, linked_url)

def get_decode_html():
    with open(Path(amazon_book_html_file_path).expanduser(), 'r') as inf:
        decode_html = inf.read()
    return decode_html

def parse_collections_of_item():
    input_str_collections = sys.argv[1]
    collections_of_item = [x.strip() for x in input_str_collections.split(",")]
    return collections_of_item

def main():
    decode_html = get_decode_html()
    book_info = extract_book_info(decode_html)
    zot_add_book(book_info)

if __name__ == '__main__':
    os.environ["https_proxy"] = "https://127.0.0.1:8118"
    amazon_book_html_file_path = "~/pipes/zotero/amazon_book.html"
    linked_url_file_path = "~/pipes/zotero/linked_url"
    book_dir = "~/Downloads/books"
    dropbox_zotero_storage_dir = "~/Dropbox/ZoteroStorage"
    zotero_api_key_file_path = "~/Dropbox/keys/zotero/api"
    zotero_collections_file_path = "~/Dropbox/keys/zotero/collections"
    main()
