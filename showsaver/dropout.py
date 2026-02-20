import requests
import time
import yt_dlp
from bs4 import BeautifulSoup
from downloader import BASE_YT_OPTS
from urllib.parse import urlsplit, urlunsplit

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


def time_to_sec(t) -> int:
    if not ':' in t:
        return int(t)
    
    split_time = t.split(':')
    if len(split_time) == 3:
        h, m, s = map(int, split_time)
        return h * 3600 + m * 60 + s
    else:
        m, s = map(int, split_time)
        return m * 60 + s


def _get_new_releases_bs():
    """
    Use BeautifulSoup to parse webpage to fetch new releases.
    """
    response = requests.get(DROPOUT_NEW_RELEASES_URL)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        videos = []
        list_items = soup.find_all('li', class_='js-collection-item')
        for list_item in list_items:
            thumbnail = list_item.img['src']
            link = list_item.find('a', href=True)
            title = list_item.find('strong')['title']
            url = link['href'].replace('/new-releases', '')
            id = int(list_item['data-item-id'])

            duration_container = list_item.find('div', class_='duration-container')
            duration_txt = duration_container.text.strip()
            duration = time_to_sec(duration_txt)

            extracted_data = {
                'title': title,
                'url': url,
                'thumbnail': thumbnail,
                'duration': duration,  # seconds
                'id': id,
            }

            videos.append(extracted_data)

        return videos
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")


def _get_new_releases_ytdlp():
    """
    Use yt-dlp to fetch new release info.
    """
    opts = {
        **BASE_YT_OPTS,
        'extract_flat': 'in_playlist',  # Get metadata without downloading
        'list_thumbnails': True,
        'skip_download': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(DROPOUT_NEW_RELEASES_URL, download=False)

    videos = []
    for entry in info.get('entries', []):
        url = entry.get('url') or entry.get('webpage_url')
        url = url.replace('/new-releases', '')

        extracted_data = {
            'title': entry.get('title'),
            'url': url,
            'thumbnail': entry.get('thumbnail'),
            'duration': entry.get('duration'),  # seconds
            'id': entry.get('id'),
        }

        videos.append(extracted_data)
    
    return videos


def get_new_releases(force_refresh=False):
    """
    Get list of new releases from Dropout using yt-dlp.
    Returns dict with 'success', 'videos' list, 'cached' flag.
    """
    # Check cache
    if not force_refresh and _new_releases_cache['data'] and (time.time() - _new_releases_cache['timestamp'] < CACHE_TTL):
        return {'success': True, 'videos': _new_releases_cache['data'], 'cached': True}
    
    try:
        videos = _get_new_releases_bs()
        
        # Update cache
        _new_releases_cache['data'] = videos
        _new_releases_cache['timestamp'] = time.time()

        return {'success': True, 'videos': videos, 'cached': False}

    except Exception as e:
        return {'success': False, 'error': str(e), 'videos': []}


def get_epsiode_info(episode_url):
    """
    Get detailed info for a single episode URL.
    Returns dict with 'success', 'info' dict.
    """
    # Check cache
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
