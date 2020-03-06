#!/usr/bin/env python3

from pathlib import Path
import os
from pyzotero import zotero
import pickle

def get_zot():
    with open(Path(zotero_api_key_file_path).expanduser(), 'r') as inf:
        library_id = inf.readline().strip()
        api_key = inf.readline().strip()
    library_type = "user"
    zot = zotero.Zotero(library_id, library_type, api_key)
    return zot

def get_collections(zot):
    collections = zot.all_collections()
    for collection in collections:
        print(collection['data']['name'])
    with open(Path(zotero_collections_file_path).expanduser(), "wb") as outf:
        pickle.dump(collections, outf)

def main():
    zot = get_zot()
    get_collections(zot)

if __name__ == '__main__':
    os.environ["https_proxy"] = "https://127.0.0.1:8118"
    zotero_api_key_file_path = "~/Dropbox/keys/zotero/api"
    zotero_collections_file_path = "~/Dropbox/keys/zotero/collections"
    main()
