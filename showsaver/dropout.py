"""Dropout TV integration for browsing content."""
import time
import yt_dlp
from downloader import BASE_YT_OPTS

DROPOUT_NEW_RELEASES_URL = "https://watch.dropout.tv/new-releases"

# Simple in-memory cache
_cache = {
    'data': None,
    'timestamp': 0
}
CACHE_TTL = 300  # 5 minutes


def get_new_releases(force_refresh=False):
    """
    Get list of new releases from Dropout using yt-dlp.
    Returns dict with 'success', 'videos' list, 'cached' flag.
    """
    # Check cache
    if not force_refresh and _cache['data'] and (time.time() - _cache['timestamp'] < CACHE_TTL):
        return {'success': True, 'videos': _cache['data'], 'cached': True}

    opts = {
        **BASE_YT_OPTS,
        'extract_flat': 'in_playlist',  # Get metadata without downloading
        'skip_download': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(DROPOUT_NEW_RELEASES_URL, download=False)

        videos = []
        for entry in info.get('entries', []):
            videos.append({
                'title': entry.get('title'),
                'url': entry.get('url') or entry.get('webpage_url'),
                'thumbnail': entry.get('thumbnail'),
                'duration': entry.get('duration'),  # seconds
                'id': entry.get('id'),
            })

        # Update cache
        _cache['data'] = videos
        _cache['timestamp'] = time.time()

        return {'success': True, 'videos': videos, 'cached': False}

    except Exception as e:
        return {'success': False, 'error': str(e), 'videos': []}
