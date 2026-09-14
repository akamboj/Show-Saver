import requests
import threading
import time
from collections.abc import Callable
from typing import Any

from showsaver.env import SONARR_URL, SONARR_API_KEY
from showsaver.text import title_match_key

# Short-lived cache for read-only lookups (series list, per-series episode lists).
# Failures are cached too (as None) so a down Sonarr costs at most one stalled
# request per TTL instead of one per frontend poll.
SONARR_CACHE_TTL = 60  # seconds
LOOKUP_TIMEOUT = 5  # seconds; read-only lookups must stay short since the frontend polls them
_cache: dict[str, tuple[float, Any]] = {}
_cache_gen = 0  # bumped by clear_cache() so in-flight fetches don't resurrect stale data
_cache_lock = threading.Lock()


def is_sonarr_enabled() -> bool:
    """Check if Sonarr integration is configured."""
    return bool(SONARR_URL and SONARR_API_KEY)


def _get_headers() -> dict[str, str]:
    """Get headers for Sonarr API requests."""
    return {
        "X-Api-Key": SONARR_API_KEY,
        "Content-Type": "application/json"
    }


def clear_cache() -> None:
    """Drop all cached Sonarr lookups, including the result of any fetch in flight."""
    global _cache_gen
    with _cache_lock:
        _cache.clear()
        _cache_gen += 1


def _cached(key: str, fetch: Callable[[], Any]) -> Any:
    """
    Return the cached value for key if fresh, otherwise call fetch() and cache it.

    A fetch that raises requests.RequestException is cached as None for the same
    TTL (negative caching). Never raises.

    The lock is not held during fetch() so a slow Sonarr cannot stall every
    caller; concurrent misses may fetch twice, which is harmless. If
    clear_cache() runs while a fetch is in flight, that fetch's result is
    returned but not stored, so a pre-import snapshot can't outlive the clear.
    """
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and now - entry[0] < SONARR_CACHE_TTL:
            return entry[1]
        gen = _cache_gen
    try:
        value = fetch()
    except requests.RequestException as e:
        print(f"Sonarr: lookup '{key}' failed: {e}")
        value = None
    with _cache_lock:
        if _cache_gen == gen:
            _cache[key] = (now, value)
    return value


def get_all_series():
    """Fetch all series from Sonarr library."""
    url = f"{SONARR_URL.rstrip('/')}/api/v3/series"
    response = requests.get(url, headers=_get_headers(), timeout=LOOKUP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_series_episodes(series_id: int) -> list[dict]:
    """Fetch every episode Sonarr knows about for a series (includes hasFile)."""
    url = f"{SONARR_URL.rstrip('/')}/api/v3/episode"
    response = requests.get(url, headers=_get_headers(), params={"seriesId": series_id}, timeout=LOOKUP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _match_series(series_list: list[dict], show_name: str, override_name: str | None = None) -> int | None:
    """
    Pick a series ID out of a Sonarr series list by name.

    Passes, all case-insensitive: exact match on the override name (if any),
    exact match on the original name, then substring match on the override name.
    """
    titles = [(series.get("title", "").lower(), series.get("id")) for series in series_list]
    search_name = (override_name or show_name).lower()

    for candidate in dict.fromkeys((search_name, show_name.lower())):
        for title, series_id in titles:
            if title == candidate:
                return series_id

    for title, series_id in titles:
        if search_name in title:
            return series_id
    return None


def find_series_by_name(show_name: str, override_name: str|None=None) -> int | None:
    """Uncached series lookup used by the download path."""
    return _match_series(get_all_series(), show_name, override_name)


def _match_episode(
    episodes: list[dict],
    season_number: int | None,
    episode_number: int | None,
    title: str | None,
) -> dict | None:
    """
    Find the Sonarr episode matching a Dropout release.

    Matches on (seasonNumber, episodeNumber) when both are known and not the
    S00E00 placeholder the processor assigns to specials; otherwise falls back
    to a case/punctuation-insensitive title match.
    """
    if season_number is not None and episode_number is not None and (season_number, episode_number) != (0, 0):
        for episode in episodes:
            if episode.get("seasonNumber") == season_number and episode.get("episodeNumber") == episode_number:
                return episode
        return None

    key = title_match_key(title)
    if not key:
        return None
    for episode in episodes:
        if title_match_key(episode.get("title")) == key:
            return episode
    return None


def is_episode_in_library(
    show_name: str,
    override_name: str | None,
    season_number: int | None,
    episode_number: int | None,
    title: str | None,
) -> bool | None:
    """
    Check whether Sonarr already has a file for an episode.

    Returns:
        True if the matched episode has a file, False if it is known but has no
        file, None if Sonarr is disabled, the series/episode could not be
        matched, or the lookup failed. Never raises.
    """
    try:
        if not is_sonarr_enabled():
            return None

        series_list = _cached("series", get_all_series)
        if series_list is None:
            return None

        series_id = _match_series(series_list, show_name, override_name)
        if series_id is None:
            return None

        episodes = _cached(f"episodes:{series_id}", lambda: get_series_episodes(series_id))
        if episodes is None:
            return None

        episode = _match_episode(episodes, season_number, episode_number, title)
        if episode is None:
            return None
        return bool(episode.get("hasFile"))
    except Exception as e:
        print(f"Sonarr: episode lookup failed for '{show_name}': {e}")
        return None


def rescan_series(series_id: int):
    """
    Trigger a rescan for a specific series in Sonarr.

    Args:
        series_id: The Sonarr series ID

    Returns:
        Command response from Sonarr
    """
    url = f"{SONARR_URL.rstrip('/')}/api/v3/command"
    payload = {
        "name": "RescanSeries",
        "seriesId": series_id
    }
    response = requests.post(url, headers=_get_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def rename_series(series_ids):
    """
    Trigger a rename for specific series in Sonarr.

    Args:
        series_ids: List of Sonarr series IDs

    Returns:
        Command response from Sonarr
    """
    url = f"{SONARR_URL.rstrip('/')}/api/v3/command"
    payload = {
        "name": "RenameSeries",
        "seriesIds": series_ids
    }
    response = requests.post(url, headers=_get_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def wait_for_command(command_id, timeout: int=30, poll_interval: int=3):
    """
    Poll /api/v3/command/{id} until Sonarr reports a terminal status.

    Args:
        command_id: The command ID returned by a previous POST to /api/v3/command
        timeout: Maximum seconds to wait (default 30)
        poll_interval: Seconds between polls (default 3)

    Returns:
        Final status string ('completed', 'failed', 'aborted'), or 'timeout'
        if no terminal status was seen within `timeout` seconds total.
    """
    url = f"{SONARR_URL.rstrip('/')}/api/v3/command/{command_id}"
    terminal = {'completed', 'failed', 'aborted'}
    deadline = time.monotonic() + timeout
    # Each poll's request timeout and the sleep are clamped to the remaining
    # budget; a poll with under a second left is skipped rather than raising.
    while (remaining := deadline - time.monotonic()) >= 1:
        response = requests.get(url, headers=_get_headers(), timeout=min(10, remaining))
        response.raise_for_status()
        status = response.json().get('status', '')
        if status in terminal:
            return status
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
    return 'timeout'


def refresh_and_rescan_series(show_name: str, override_name: str|None=None, do_rename: bool=False) -> bool:
    """
    Main entry point: find series, trigger rescan, wait for it, refresh the lookup cache.

    Args:
        show_name: The show name from yt-dlp metadata
        override_name: Potential overriden name of show
        do_rename: Also trigger a RenameSeries after the rescan finishes

    Returns:
        True if rescan was triggered, False otherwise
    """
    if not is_sonarr_enabled():
        return False

    series_id = find_series_by_name(show_name, override_name)

    if series_id is None:
        print(f"Sonarr: Series '{show_name}' not found in library")
        return False

    rescan_ret = rescan_series(series_id)
    command_id = rescan_ret.get('id')
    print(f"Sonarr: Triggered rescan for series '{show_name}' (ID: {series_id})")

    if command_id:
        try:
            final_status = wait_for_command(command_id)
            print(f"Sonarr: Rescan finished with status '{final_status}' for '{show_name}'")
        except requests.RequestException as e:
            print(f"Sonarr: Could not confirm rescan completion for '{show_name}': {e}")

    # Drop cached series/episode lists so in_library lookups see the imported file
    clear_cache()

    if do_rename:
        rename_series([series_id])
        print(f"Sonarr: Triggered rename for series '{show_name}' (ID: {series_id})")
    return True
