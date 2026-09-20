import showsaver.database as database
import showsaver.sonarr as sonarr
from showsaver.downloader import BASE_YT_OPTS, get_metadata
from showsaver.processors import Processor
from showsaver.special_patterns import get_special_patterns
from showsaver.state import queue_metadata

import re
import requests
import time
import yt_dlp
from bs4 import BeautifulSoup
from typing import Any
from urllib.parse import urlparse

DROPOUT_NEW_RELEASES_URL = "https://watch.dropout.tv/new-releases"

# Cache for new releases found on last scrape
_new_releases_cache = {
    'data': None,
    'timestamp': 0
}
CACHE_TTL = 300  # 5 minutes
METADATA_CACHE_TTL = 7 * 24 * 60 * 60 # 1 week in seconds

DROPOUT_SITEMAP_URL = 'https://watch.dropout.tv/sitemap.xml'
D20_COMPLETE_SERIES_URL = 'https://watch.dropout.tv/dimension-20-the-complete-series'
D20_SERIES_NAME = 'Dimension 20'
_D20_SITEMAP_RE = re.compile(r'dimension-20-the-complete-series-season-(\d+)/videos/([a-z0-9-]+)')
_d20_season_cache = {
    'data': None,
    'timestamp': 0
}
D20_SEASON_CACHE_TTL = 60 * 60  # 1 hour

SHOW_NAME_OVERRIDES = {
    'Very Important People' : 'Very Important People (2023)',
    'Don\'t Hug Me I\'m Scared' : 'Don\'t Hug Me I\'m Scared (2022)'
}

class DropoutProcessor(Processor):
    def process_info_dict(self, info_dict) -> None:

        season_number = info_dict.get('season_number') or 0
        if self.treat_as_special(info_dict):
            info_dict['season_number'] = 0
            info_dict['episode_number'] = 0
        elif self.__is_dim20(info_dict):
            # Seaon 27 is now On a Bus S1, and 28 is On a Bus S2. We need to decrement season number for each
            # 5/27/26 - TVDB seasons now match official listings. This is no longer needed for D20
            # 5/28.26 - TVDB undid the change
            if season_number > 29:
                info_dict['season_number'] = season_number - 2
            elif season_number > 27:
                info_dict['season_number'] = season_number - 1
        elif self.__is_adventuring_party(info_dict):
            # Season 23 is On a Bus S2 adventuring party. So we need to decrement to match actual expected season number.
            if season_number > 23:
                info_dict['season_number'] = season_number - 1


    def process_dlp_opts(self, dlp_opts, info_dict) -> None:

        if self.treat_as_special(info_dict):
            dlp_opts['outtmpl'] = {'default' : '%(series)s - S00E00 - %(title)s WEBDL-1080p.%(ext)s'}
        elif self.__is_dim20(info_dict) or self.__is_adventuring_party(info_dict):
            # Because of the season number modification we have to specify it directly in the file name template
            season_number = info_dict.get('season_number') or 0
            dlp_opts['outtmpl'] = {'default' : f'%(series)s - S{season_number}E%(episode_number)02d - %(title)s WEBDL-1080p.%(ext)s'}


    def get_show_name_override(self, show_name: str) -> str | None:

        return SHOW_NAME_OVERRIDES.get(show_name)


    def should_trigger_rename(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        if self.treat_as_special(info_dict):
            return True
        if 'Don\'t Hug Me I\'m Scared' in series:
            return True
        return False


    def find_d20_season(self, show_url: str, info_dict, refresh_on_miss: bool = True) -> int | None:
        """
        Complete-series season for a Dimension 20 campaign url, from the sitemap map.
        Returns None when the series is not a campaign or the slug is unknown.
        """
        if 'Dimension 20:' not in (info_dict.get('series') or ''):
            return None

        slug = _get_url_path(show_url)
        season = _get_d20_season_map().get(slug)
        if season is None and refresh_on_miss:
            # The cached map can be up to D20_SEASON_CACHE_TTL stale, so a miss is most
            # likely a newly published episode. Refresh once before giving up.
            season = _get_d20_season_map(force_refresh=True).get(slug)
        return season


    def find_corrected_url(self, show_url: str, info_dict) -> tuple[str, dict] | None:

        if 'Dimension 20:' not in (info_dict.get('series') or ''):
            return None

        print(f'Attempting to correct url: {show_url}')
        season = self.find_d20_season(show_url, info_dict)
        if season is None:
            print('Failed to find corrected Dimension 20 url.')
            return None

        url = f'{D20_COMPLETE_SERIES_URL}/season:{season}/videos/{_get_url_path(show_url)}'
        print(f'Found corrected url: {url}')
        try:
            corrected_info = get_metadata(url)
        except Exception as e:
            print(f'Failed to fetch metadata for corrected url {url}: {e}')
            return None
        if not (corrected_info and corrected_info.get('season_number')):
            # Season numbers past the real range resolve to the season-less page
            print(f'Corrected url did not resolve to a season: {url}')
            return None
        return url, corrected_info


    def treat_as_special(self, info_dict) -> bool:

        series = info_dict.get('series') or ''
        title = info_dict.get('title') or ''
        return any(
            series_pattern.search(series) and title_pattern.search(title)
            for series_pattern, title_pattern in get_special_patterns()
        )


    def __is_dim20(self, info_dict) -> bool:

        series = info_dict.get('series', '')
        if D20_SERIES_NAME == series:
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
    response = requests.get(DROPOUT_NEW_RELEASES_URL, timeout=30)

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
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
    return None


def _get_d20_season_map(force_refresh: bool = False) -> dict[str, int]:
    """
    Map of episode slug -> season number in the 'Dimension 20: The Complete Series'
    collection, parsed from the Dropout sitemap. Cached for D20_SEASON_CACHE_TTL.
    """
    cached = _d20_season_cache['data']
    fetched_at = _d20_season_cache['timestamp']
    if not force_refresh and cached is not None and (time.time() - fetched_at < D20_SEASON_CACHE_TTL):
        return cached

    try:
        response = requests.get(DROPOUT_SITEMAP_URL, timeout=30)
        if response.status_code != 200:
            print(f'Failed to fetch Dropout sitemap. Status code {response.status_code}')
            return cached or {}
        season_map = {
            slug: int(season) for season, slug in _D20_SITEMAP_RE.findall(response.text)
        }
        if not season_map:
            # A 200 that parses to nothing means the sitemap changed shape, not that the
            # collection is empty. Keep whatever we already had.
            print('Dropout sitemap contained no Dimension 20 complete-series entries.')
            return cached or {}
        _d20_season_cache['data'] = season_map
        _d20_season_cache['timestamp'] = time.time()
        return season_map
    except Exception as e:
        print(f'Failed to fetch Dropout sitemap: {e}')
        return cached or {}


def _get_url_path(url: str) -> str:
    parsed_url = urlparse(url)
    stripped_path = parsed_url.path.rstrip('/')
    split_path = stripped_path.split('/')
    return split_path[-1]


def _update_database_episode(video_info: dict) -> None:
    full_url = video_info.get('url', '')
    url_path = _get_url_path(full_url)

    database.upsert_dropout_episode(
        url_path=url_path,
        url=full_url,
        show_name=video_info.get('show_name', ''),
        episode_title=video_info.get('title', ''),
        thumbnail=video_info.get('thumbnail', ''),
        duration_secs=video_info.get('duration', -1),
        season_number=video_info.get('season_number'),
        episode_number=video_info.get('episode_number'),
    )


def _annotate_in_library(video: dict, processor: DropoutProcessor) -> None:
    """Set video['in_library'] via Sonarr after applying the processor's season/episode remaps."""
    show_name = video.get('show_name') or ''
    if not show_name:
        video['in_library'] = None
        return

    info = {
        'series': show_name,
        'title': video.get('title') or '',
        'season_number': video.get('season_number'),
        'episode_number': video.get('episode_number'),
    }
    # Map a D20 campaign row onto 'Dimension 20' at its complete-series season; the
    # episode number and title are identical, so the sitemap map is enough (no yt-dlp).
    season = processor.find_d20_season(video.get('url') or '', info, refresh_on_miss=False)
    if season is not None:
        info['series'] = D20_SERIES_NAME
        info['season_number'] = season
    processor.process_info_dict(info)
    video['in_library'] = sonarr.is_episode_in_library(
        info['series'],
        processor.get_show_name_override(info['series']),
        info['season_number'],
        info['episode_number'],
        info['title'],
    )


def get_new_releases(force_refresh: bool=False):
    """
    Get list of new releases from Dropout using yt-dlp.
    Returns dict with 'success', 'videos' list, 'cached' flag.
    """
    if force_refresh:
        sonarr.clear_cache()

    processor = DropoutProcessor()
    if not force_refresh and _new_releases_cache['data'] and (time.time() - _new_releases_cache['timestamp'] < CACHE_TTL):
        fetched = [row for row in (database.get_dropout_episode(_get_url_path(u)) for u in _new_releases_cache['data']) if row]
        if fetched:
            for video in fetched:
                _annotate_in_library(video, processor)
            return {'success': True, 'videos': fetched, 'cached': True}
    
    try:
        scraped = _get_new_releases_bs() or []
        videos = []
        for v in scraped:
            url_path = _get_url_path(v['url'])
            # Preserve any existing show_name in data
            database.upsert_dropout_episode_basic(
                url_path=url_path,
                url=v['url'],
                episode_title=v.get('title', ''),
                thumbnail=v.get('thumbnail', ''),
                duration_secs=v.get('duration', -1),
            )
            row = database.get_dropout_episode(url_path) or {}
            metadata_fetched_at = row.get('metadata_fetched_at')
            merged = {
                **v,
                'show_name': row.get('show_name', ''),
                'metadata_fetched_at': metadata_fetched_at,
                'season_number': row.get('season_number'),
                'episode_number': row.get('episode_number'),
            }
            _annotate_in_library(merged, processor)
            videos.append(merged)

            if not merged['show_name'] and (time.time() - (metadata_fetched_at or 0)) > METADATA_CACHE_TTL:
                queue_metadata(v['url'], url_path)
        
        _new_releases_cache['data'] = [v['url'] for v in videos if v]
        _new_releases_cache['timestamp'] = time.time()
        return {'success': True, 'videos': videos, 'cached': False}
    except Exception as e:
        return {'success': False, 'error': str(e), 'videos': []}


def fetch_and_store_episode_info(episode_url: str) -> dict[str, Any]:
    # Run yt-dlp, upsert the full row to DB. Returns the info dict or raises.
    opts = {
        **BASE_YT_OPTS,
        'skip_download': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(episode_url, download=False)
    
    episode_info = {
        'title': info.get('title'),
        'url': info.get('webpage_url'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'description': info.get('description'),
        'id': info.get('id'),
        'show_name': info.get('series', ''),
        'season_number': info.get('season_number'),
        'episode_number': info.get('episode_number'),
    }
    _update_database_episode(episode_info)
    return episode_info
    

def get_epsiode_info(episode_url: str):
    """DB-only read. Background worker is responsible for populating rows."""
    try:
        url_path = _get_url_path(episode_url)
        entry = database.get_dropout_episode(url_path)
        if entry:
            return {'success': True, 'info': entry}
        return {'success': False, 'error': 'not_yet_fetched', 'info': None}
    except Exception as e:
        return {'success': False, 'error': str(e), 'info': None}
