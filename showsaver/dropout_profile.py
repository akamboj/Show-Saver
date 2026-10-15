"""Workaround for Dropout's account profile picker (launched 2026-10-14).

After a successful login, Dropout now redirects the first page request to
``/profile/pick`` (a Netflix-style "who's watching" screen) until a profile has
been selected for the session. yt-dlp's ``DropoutIE`` does not know about this
page, so it fails with ``Unable to extract embed url``
(https://github.com/yt-dlp/yt-dlp/issues/17823).

This module patches ``DropoutIE._login`` so that, right after the stock login
succeeds, it selects a profile the same way the browser does: a JSON ``POST`` to
``/profile/login`` carrying the page's CSRF token. If ``/profile/pick`` no
longer renders the picker (Dropout removes it, or upstream yt-dlp learns to
handle it), the patch is a no-op. Remove this module once the upstream fix
ships.

Note: ``DropoutIE._real_extract`` skips ``_login`` entirely when a ``_session``
cookie is already present (cookie-file auth). Show-Saver authenticates with
``.netrc``, so that branch is not handled here.
"""

import json

from yt_dlp.extractor.dropout import DropoutIE

PICK_URL = 'https://watch.dropout.tv/profile/pick'
PROFILE_LOGIN_URL = 'https://watch.dropout.tv/profile/login'
PICKER_MARKER = 'profile-picker-react-app'
# 0 is the account owner's profile and always exists. Every profile has the same
# entitlements and streams; only watch history differs.
PROFILE_INDEX = 0

_original_login = DropoutIE._login


def select_profile(ie, display_id):
    """Select an account profile for the current yt-dlp session.

    Returns True when a profile was selected, False when the picker is not
    shown or the selection request failed. Never raises.
    """
    pick_page = ie._download_webpage(
        PICK_URL, display_id, note='Checking for profile picker', fatal=False)
    if not pick_page or PICKER_MARKER not in pick_page:
        return False

    csrf_token = ie._html_search_meta('csrf-token', pick_page, 'csrf token', default=None)
    if not csrf_token:
        ie.report_warning('Profile picker found but no CSRF token; cannot select a profile')
        return False

    response = ie._request_webpage(
        PROFILE_LOGIN_URL, display_id, note=f'Selecting profile {PROFILE_INDEX}',
        errnote='Unable to select profile', fatal=False,
        data=json.dumps({'profile_index': PROFILE_INDEX}).encode(),
        headers={
            'Content-Type': 'application/json',
            'Referer': PICK_URL,
            'X-CSRF-Token': csrf_token,
        })
    return bool(response)


def _login_with_profile(self, display_id):
    err = _original_login(self, display_id)
    if err:
        # True (no credentials) or an error string: nothing to select.
        return err
    select_profile(self, display_id)
    return err


def install():
    """Patch DropoutIE._login. Idempotent."""
    if getattr(DropoutIE, '_showsaver_profile_patch', False):
        return
    DropoutIE._login = _login_with_profile
    DropoutIE._showsaver_profile_patch = True


install()
