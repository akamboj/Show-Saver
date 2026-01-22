import requests
from env import SONARR_URL, SONARR_API_KEY


def is_sonarr_enabled():
    """Check if Sonarr integration is configured."""
    return bool(SONARR_URL and SONARR_API_KEY)


def _get_headers():
    """Get headers for Sonarr API requests."""
    return {
        "X-Api-Key": SONARR_API_KEY,
        "Content-Type": "application/json"
    }


def get_all_series():
    """Fetch all series from Sonarr library."""
    url = f"{SONARR_URL.rstrip('/')}/api/v3/series"
    response = requests.get(url, headers=_get_headers(), timeout=10)
    response.raise_for_status()
    return response.json()


def find_series_by_name(show_name, overrides=None):
    """
    Find a series ID in Sonarr by show name.

    Args:
        show_name: The show name from yt-dlp metadata
        overrides: Dict of show name overrides (original -> corrected)

    Returns:
        Series ID if found, None otherwise
    """
    if overrides is None:
        overrides = {}

    # Apply override if present
    search_name = overrides.get(show_name, show_name)

    series_list = get_all_series()

    # Case-insensitive search
    search_name_lower = search_name.lower()
    for series in series_list:
        if series.get("title", "").lower() == search_name_lower:
            return series.get("id")

    # If override was applied but not found, try original name
    if show_name != search_name:
        show_name_lower = show_name.lower()
        for series in series_list:
            if series.get("title", "").lower() == show_name_lower:
                return series.get("id")

    return None


def rescan_series(series_id):
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
    response = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def refresh_and_rescan_series(show_name, overrides=None):
    """
    Main entry point: find series and trigger rescan.

    Args:
        show_name: The show name from yt-dlp metadata
        overrides: Dict of show name overrides

    Returns:
        True if rescan was triggered, False otherwise
    """
    if not is_sonarr_enabled():
        return False

    series_id = find_series_by_name(show_name, overrides)

    if series_id is None:
        print(f"Sonarr: Series '{show_name}' not found in library")
        return False

    rescan_series(series_id)
    print(f"Sonarr: Triggered rescan for series '{show_name}' (ID: {series_id})")
    return True
