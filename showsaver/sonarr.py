import requests
import time
from env import SONARR_URL, SONARR_API_KEY


def is_sonarr_enabled() -> bool:
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


def find_series_by_name(show_name, override_name=None):
    """
    Find a series ID in Sonarr by show name.

    Args:
        show_name: The show name from yt-dlp metadata
        overrides: Dict of show name overrides (original -> corrected)

    Returns:
        Series ID if found, None otherwise
    """
    if override_name:
        # Apply override if present
        search_name = override_name


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
    response = requests.post(url, headers=_get_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def rename_series(series_ids):
    """
    Trigger a rename for a specific series in Sonarr.

    Args:
        series_id: The Sonarr series ID

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


def wait_for_command(command_id, timeout=30, poll_interval=3):
    """
    Poll /api/v3/command/{id} until Sonarr reports a terminal status.

    Args:
        command_id: The command ID returned by a previous POST to /api/v3/command
        timeout: Maximum seconds to wait (default 120)
        poll_interval: Seconds between polls (default 3)

    Returns:
        Final status string, e.g. 'completed', 'failed', 'aborted'
    """
    url = f"{SONARR_URL.rstrip('/')}/api/v3/command/{command_id}"
    terminal = {'completed', 'failed', 'aborted'}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(url, headers=_get_headers(), timeout=10)
        response.raise_for_status()
        status = response.json().get('status', '')
        if status in terminal:
            return status
        time.sleep(poll_interval)
    return 'timeout'


def refresh_and_rescan_series(show_name, override_name=None, do_rename=False):
    """
    Main entry point: find series and trigger rescan.

    Args:
        show_name: The show name from yt-dlp metadata
        override_name: Potential overriden name of show

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

    if command_id and do_rename:
        final_status = wait_for_command(command_id)
        print(f"Sonarr: Rescan finished with status '{final_status}' for '{show_name}'")

    if do_rename:
        rename_ret = rename_series([series_id])
        print(f"Sonarr: Triggered rename for series '{show_name}' (ID: {series_id})")
    return True
