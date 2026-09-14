import pytest
import requests

from showsaver import sonarr


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'status {self.status_code}')


SERIES = [
    {'id': 1, 'title': 'Game Changer'},
    {'id': 2, 'title': 'Very Important People (2023)'},
    {'id': 3, 'title': 'Dimension 20'},
]

EPISODES_GAME_CHANGER = [
    {'id': 10, 'seriesId': 1, 'seasonNumber': 6, 'episodeNumber': 3, 'title': 'The Big One', 'hasFile': True},
    {'id': 11, 'seriesId': 1, 'seasonNumber': 6, 'episodeNumber': 4, 'title': 'Not Yet', 'hasFile': False},
    {'id': 12, 'seriesId': 1, 'seasonNumber': 0, 'episodeNumber': 5, 'title': 'Last Looks: "Sam"?', 'hasFile': True},
]


@pytest.fixture
def sonarr_enabled(monkeypatch):
    monkeypatch.setattr(sonarr, 'SONARR_URL', 'http://sonarr.test/')
    monkeypatch.setattr(sonarr, 'SONARR_API_KEY', 'key')
    sonarr.clear_cache()
    yield
    sonarr.clear_cache()


@pytest.fixture
def fake_get(monkeypatch):
    """Route sonarr.requests.get by path; tracks calls and lets tests inject failures."""
    state = {
        'calls': [],
        'series': SERIES,
        'episodes': {1: EPISODES_GAME_CHANGER, 2: [], 3: []},
        'fail_series': False,
        'fail_episodes': False,
    }

    def _get(url, headers=None, params=None, timeout=None):
        state['calls'].append((url, params))
        assert headers['X-Api-Key'] == 'key'
        if url.endswith('/api/v3/series'):
            if state['fail_series']:
                raise requests.ConnectionError('down')
            return _Resp(state['series'])
        if url.endswith('/api/v3/episode'):
            if state['fail_episodes']:
                return _Resp({}, status=500)
            return _Resp(state['episodes'].get(params['seriesId'], []))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(sonarr.requests, 'get', _get)
    return state


class TestMatchSeries:
    def test_exact_match_on_override_name(self):
        assert sonarr._match_series(SERIES, 'Very Important People', 'Very Important People (2023)') == 2

    def test_exact_match_on_original_when_override_missing(self):
        assert sonarr._match_series(SERIES, 'Game Changer', 'Game Changer (1999)') == 1

    def test_substring_match(self):
        assert sonarr._match_series(SERIES, 'Dimension') == 3

    def test_case_insensitive(self):
        assert sonarr._match_series(SERIES, 'game changer') == 1

    def test_no_match_returns_none(self):
        assert sonarr._match_series(SERIES, 'Make Some Noise') is None


class TestMatchEpisode:
    def test_season_episode_hit(self):
        ep = sonarr._match_episode(EPISODES_GAME_CHANGER, 6, 3, 'ignored')
        assert ep['id'] == 10

    def test_season_episode_known_but_unmatched_does_not_fall_back_to_title(self):
        assert sonarr._match_episode(EPISODES_GAME_CHANGER, 9, 9, 'The Big One') is None

    def test_zero_zero_falls_back_to_title(self):
        ep = sonarr._match_episode(EPISODES_GAME_CHANGER, 0, 0, "Last Looks - 'Sam'")
        assert ep['id'] == 12

    def test_none_numbers_fall_back_to_title(self):
        ep = sonarr._match_episode(EPISODES_GAME_CHANGER, None, None, 'the big one')
        assert ep['id'] == 10

    def test_title_fallback_with_empty_title_returns_none(self):
        assert sonarr._match_episode(EPISODES_GAME_CHANGER, None, None, '') is None

    def test_missing_episode_number_falls_back_to_title(self):
        ep = sonarr._match_episode(EPISODES_GAME_CHANGER, 6, None, 'Not Yet')
        assert ep['id'] == 11


class TestIsEpisodeInLibrary:
    def test_disabled_returns_none(self, monkeypatch, fake_get):
        monkeypatch.setattr(sonarr, 'SONARR_URL', '')
        monkeypatch.setattr(sonarr, 'SONARR_API_KEY', '')
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None
        assert fake_get['calls'] == []

    def test_has_file_true(self, sonarr_enabled, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is True

    def test_has_file_false(self, sonarr_enabled, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 4, 'x') is False

    def test_series_not_found_returns_none(self, sonarr_enabled, fake_get):
        assert sonarr.is_episode_in_library('Make Some Noise', None, 1, 1, 'x') is None
        # Only the series list was fetched
        assert len(fake_get['calls']) == 1

    def test_episode_not_found_returns_none(self, sonarr_enabled, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 42, 42, 'x') is None

    def test_special_matched_by_title(self, sonarr_enabled, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 0, 0, "Last Looks - 'Sam'") is True

    def test_series_http_error_returns_none(self, sonarr_enabled, fake_get):
        fake_get['fail_series'] = True
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None

    def test_episode_http_error_returns_none(self, sonarr_enabled, fake_get):
        fake_get['fail_episodes'] = True
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None

    def test_second_call_uses_cache(self, sonarr_enabled, fake_get):
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        sonarr.is_episode_in_library('Game Changer', None, 6, 4, 'x')
        assert len(fake_get['calls']) == 2  # one series + one episodes fetch

    def test_clear_cache_refetches(self, sonarr_enabled, fake_get):
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        sonarr.clear_cache()
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        assert len(fake_get['calls']) == 4

    def test_failure_is_negatively_cached(self, sonarr_enabled, fake_get):
        fake_get['fail_series'] = True
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        fake_get['fail_series'] = False
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None
        assert len(fake_get['calls']) == 1

    def test_cache_expires_after_ttl(self, sonarr_enabled, fake_get, monkeypatch):
        clock = {'now': 1000.0}
        monkeypatch.setattr(sonarr.time, 'time', lambda: clock['now'])
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        clock['now'] += sonarr.SONARR_CACHE_TTL + 1
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        assert len(fake_get['calls']) == 4

    def test_unexpected_exception_returns_none(self, sonarr_enabled, monkeypatch):
        def _boom(*_a, **_k):
            raise RuntimeError('unexpected')
        monkeypatch.setattr(sonarr, '_cached', _boom)
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None


class TestFindSeriesByName:
    def test_is_uncached(self, sonarr_enabled, fake_get):
        assert sonarr.find_series_by_name('Game Changer') == 1
        assert sonarr.find_series_by_name('Game Changer') == 1
        assert len(fake_get['calls']) == 2

    def test_override_then_original(self, sonarr_enabled, fake_get):
        assert sonarr.find_series_by_name('Very Important People', 'Very Important People (2023)') == 2
