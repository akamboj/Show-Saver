import database
from downloader import BASE_YT_OPTS
from processors import Processor

import requests
import time
import yt_dlp
from bs4 import BeautifulSoup
from typing import Any
from urllib.parse import urlparse

DROPOUT_NEW_RELEASES_URL = "https://watch.dropout.tv/new-releases"

# Simple in-memory cache
_new_releases_cache = {
    'data': None,
    'timestamp': 0
}
CACHE_TTL = 300  # 5 minutes

# Episode info cache (keyed by URL)
_episode_cache = {}
EPISODE_CACHE_TTL = 3600  # 1 hour for individual episodes

SHOW_NAME_OVERRIDES = {
    'Very Important People' : 'Very Important People (2023)',
    'Don\'t Hug Me I\'m Scared' : 'Don\'t Hug Me I\'m Scared (2022)'
}

class DropoutProcessor(Processor):
    def process_info_dict(self, info_dict):

        season_number = info_dict.get('season_number', 0)
        if self.__is_last_look(info_dict):
            info_dict['season_number'] = 0
            info_dict['episode_number'] = 0
        elif self.__is_dim20(info_dict):
            # Seaon 27 is now On a Bus S1, and 28 is On a Bus S2. We need to decrement season number for each
            if season_number > 29:
                info_dict['season_number'] = season_number - 2
            elif season_number > 27:
                info_dict['season_number'] = season_number - 1
        elif self.__is_adventuring_party(info_dict):
            # Season 23 is On a Bus S2 adventuring party. So we need to decrement to match actual expected season number.
            if season_number > 23:
                info_dict['season_number'] = season_number - 1


    def process_dlp_opts(self, dlp_opts, info_dict):

        if self.__is_last_look(info_dict):
            dlp_opts['outtmpl'] = {'default' : '%(series)s - S00E00 - %(title)s WEBDL-1080p.%(ext)s'}
        elif self.__is_dim20(info_dict) or self.__is_adventuring_party(info_dict):
            # Because of the season number modification we have to specify it directly in the file name template
            season_number = info_dict.get('season_number', 0)
            dlp_opts['outtmpl'] = {'default' : f'%(series)s - S{season_number}E%(episode_number)02d - %(title)s WEBDL-1080p.%(ext)s'}


    def process_show_name(self, show_name) -> str:

        if show_name in SHOW_NAME_OVERRIDES:
            return SHOW_NAME_OVERRIDES[show_name]
        return show_name


    def should_trigger_rename(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        if self.__is_last_look(info_dict):
            return True
        if 'Don\'t Hug Me I\'m Scared' in series:
            return True
        return False


    def __is_last_look(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        title = info_dict.get('title', '')
        if 'Very Important People' in series and 'Last Looks' in title:
            return True
        return False
    

    def __is_dim20(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        if 'Dimension 20' == series:
            return True
        return False


    def __is_adventuring_party(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        if 'Dimension 20\'s Adventuring Party' == series:
            return True
        return False



def _time_to_sec(t: str) -> int:
    if not ':' in t:
        return int(t)

    split_time = t.split(':')
    if len(split_time) == 3:
        h, m, s = map(int, split_time)
        return h * 3600 + m * 60 + s
    else:
        m, s = map(int, split_time)
        return m * 60 + s


def _get_new_releases_bs() -> list[dict[str, Any]] | None:
    """
    Use BeautifulSoup to parse webpage to fetch new releases.
    """
    response = requests.get(DROPOUT_NEW_RELEASES_URL)

    if response.status_code == 200:
        try:
            soup = BeautifulSoup(response.text, 'html.parser')

            videos = []
            list_items = soup.find_all('li', class_='js-collection-item')
            for list_item in list_items:
                if list_item:
                    img = list_item.find('img')
                    thumbnail = img['src'] if img else None
                    link = list_item.find('a', href=True)

                    title = list_item.find('strong')['title']
                    url = link['href'].replace('/new-releases', '')
                    id = int(list_item['data-item-id'])

                    duration_container = list_item.find('div', class_='duration-container')
                    if duration_container:
                        duration_txt = duration_container.text.strip()
                        duration = _time_to_sec(duration_txt)

                        extracted_data = {
                            'title': title,
                            'url': url,
                            'thumbnail': thumbnail,
                            'duration': duration,  # seconds
                            'id': id,
                        }

                        videos.append(extracted_data)

            return videos
        except Exception as e:
            print(e)
            return None
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")


def _get_url_path(url: str) -> str:
    parsed_url = urlparse(url)
    split_path = parsed_url.path.split('/')
    return split_path[-1]


def _update_database_episode(video_info: dict) -> None:
    full_url = video_info.get('url', '')
    url_path = _get_url_path(full_url)

    database.upsert_dropout_episode(
        url_path=url_path,
        full_url=full_url,
        show_name=video_info.get('show_name', ''),
        episode_title=video_info.get('title', ''),
        thumbnail_url=video_info.get('thumbnail', ''),
        duration_secs=video_info.get('duration', -1)
    )


def get_new_releases(force_refresh: bool=False):
    """
    Get list of new releases from Dropout using yt-dlp.
    Returns dict with 'success', 'videos' list, 'cached' flag.
    """
    # Check cache
    if not force_refresh and _new_releases_cache['data'] and (time.time() - _new_releases_cache['timestamp'] < CACHE_TTL):
        return {'success': True, 'videos': _new_releases_cache['data'], 'cached': True}

    try:
        videos = _get_new_releases_bs()
        if videos:
            for video in videos:
                _update_database_episode(video)

        # Update cache
        _new_releases_cache['data'] = videos
        _new_releases_cache['timestamp'] = time.time()

        return {'success': True, 'videos': videos, 'cached': False}

    except Exception as e:
        return {'success': False, 'error': str(e), 'videos': []}


def get_epsiode_info(episode_url: str):
    """
    Get detailed info for a single episode URL.
    Returns dict with 'success', 'info' dict.
    """
    # Check cache
    entry = database.get_dropout_episode(_get_url_path(episode_url))
    if entry and time.time() - entry['timestamp'] < EPISODE_CACHE_TTL:
        return {'success': True, 'info': entry}

    if episode_url in _episode_cache:
        cached = _episode_cache[episode_url]
        if time.time() - cached['timestamp'] < EPISODE_CACHE_TTL:
            return {'success': True, 'info': cached['data']}

    opts = {
        **BASE_YT_OPTS,
        'skip_download': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(episode_url, download=False)

        episode_info = {
            'title': info.get('title'),
            'url': info.get('webpage_url'),
            'thumbnail': info.get('thumbnail'),
            'duration': info.get('duration'),
            'description': info.get('description'),
            'id': info.get('id'),
        }

        # Update cache
        _episode_cache[episode_url] = {
            'data': episode_info,
            'timestamp': time.time()
        }

        return {'success': True, 'info': episode_info}

    except Exception as e:
        return {'success': False, 'error': str(e), 'info': None}
