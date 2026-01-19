import downloader

import os
import yt_dlp
from env import (
    CONFIG_DIR, SHOW_DIR, URL
)

URL_LIST_FILE_PATH = os.path.join(CONFIG_DIR, 'urls.txt')


def get_urls_to_process():
    urls = []
    if URL:
        urls.append(URL)

    with open(URL_LIST_FILE_PATH, 'r') as url_list_file:
        file_urls = [line.strip() for line in url_list_file if line.strip()]
        urls.extend(file_urls)
    
    return urls


def create_config_files():
    netrc_path = os.path.join(CONFIG_DIR, '.netrc')
    if not os.path.exists(netrc_path):
        with open(netrc_path, 'w') as netrc_file:
            print('Created .netrc file: ' + netrc_path)

    if not os.path.exists(URL_LIST_FILE_PATH):
        with open(URL_LIST_FILE_PATH, 'w') as url_list_file:
            print('Created url text file: ' + URL_LIST_FILE_PATH)


def main():
    create_config_files()
    
    print("yt-dlp version: " + yt_dlp.version.__version__)

    urls_to_process = get_urls_to_process()
    downloader.process_urls(urls_to_process, SHOW_DIR)


if __name__=="__main__":
    main()
