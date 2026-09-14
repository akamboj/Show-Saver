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
    @pytest.mark.parametrize('show_name, override_name, expected', [
        ('Very Important People', 'Very Important People (2023)', 2),  # exact on override
        ('Game Changer', 'Game Changer (1999)', 1),                    # override missing, exact on original
        ('Dimension', None, 3),                                        # substring
        ('game changer', None, 1),                                     # case-insensitive
        ('Make Some Noise', None, None),                               # no match
    ])
    def test_match(self, show_name, override_name, expected):
        assert sonarr._match_series(SERIES, show_name, override_name) == expected


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


@pytest.mark.usefixtures('sonarr_enabled')
class TestIsEpisodeInLibrary:
    def test_disabled_returns_none(self, monkeypatch, fake_get):
        monkeypatch.setattr(sonarr, 'SONARR_URL', '')
        monkeypatch.setattr(sonarr, 'SONARR_API_KEY', '')
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None
        assert fake_get['calls'] == []

    @pytest.mark.parametrize('episode_number, expected', [(3, True), (4, False)])
    def test_has_file(self, fake_get, episode_number, expected):
        assert sonarr.is_episode_in_library('Game Changer', None, 6, episode_number, 'x') is expected

    def test_series_not_found_returns_none(self, fake_get):
        assert sonarr.is_episode_in_library('Make Some Noise', None, 1, 1, 'x') is None
        # Only the series list was fetched
        assert len(fake_get['calls']) == 1

    def test_episode_not_found_returns_none(self, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 42, 42, 'x') is None

    def test_special_matched_by_title(self, fake_get):
        assert sonarr.is_episode_in_library('Game Changer', None, 0, 0, "Last Looks - 'Sam'") is True

    def test_series_http_error_returns_none(self, fake_get):
        fake_get['fail_series'] = True
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None

    def test_episode_http_error_returns_none(self, fake_get):
        fake_get['fail_episodes'] = True
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None

    def test_second_call_uses_cache(self, fake_get):
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        sonarr.is_episode_in_library('Game Changer', None, 6, 4, 'x')
        assert len(fake_get['calls']) == 2  # one series + one episodes fetch

    def test_clear_cache_refetches(self, fake_get):
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        sonarr.clear_cache()
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        assert len(fake_get['calls']) == 4

    def test_failure_is_negatively_cached(self, fake_get):
        fake_get['fail_series'] = True
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        fake_get['fail_series'] = False
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None
        assert len(fake_get['calls']) == 1

    def test_cache_expires_after_ttl(self, fake_get, monkeypatch):
        clock = {'now': 1000.0}
        monkeypatch.setattr('time.time', lambda: clock['now'])
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        clock['now'] += sonarr.SONARR_CACHE_TTL + 1
        sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x')
        assert len(fake_get['calls']) == 4

    def test_malformed_payload_returns_none(self, monkeypatch):
        def _boom(*_a, **_k):
            raise TypeError('malformed')
        monkeypatch.setattr(sonarr, '_cached', _boom)
        assert sonarr.is_episode_in_library('Game Changer', None, 6, 3, 'x') is None


class TestFindSeriesByName:
    def test_is_uncached(self, sonarr_enabled, fake_get):
        assert sonarr.find_series_by_name('Game Changer') == 1
        assert sonarr.find_series_by_name('Game Changer') == 1
        assert len(fake_get['calls']) == 2

    def test_override_then_original(self, sonarr_enabled, fake_get):
        assert sonarr.find_series_by_name('Very Important People', 'Very Important People (2023)') == 2


@pytest.fixture
def rescan_stubs(monkeypatch, sonarr_enabled):
    """Stub the command endpoints used by refresh_and_rescan_series and record calls."""
    state = {
        'series_id': 1,
        'rescan_response': {'id': 99},
        'wait_status': 'completed',
        'calls': [],
    }

    def _find(show_name, override_name=None):
        state['calls'].append(('find', show_name, override_name))
        return state['series_id']

    def _rescan(series_id):
        state['calls'].append(('rescan', series_id))
        return state['rescan_response']

    def _wait(command_id, timeout=30, poll_interval=3):
        state['calls'].append(('wait', command_id))
        return state['wait_status']

    def _rename(series_ids):
        state['calls'].append(('rename', tuple(series_ids)))
        return {'id': 100}

    monkeypatch.setattr(sonarr, 'find_series_by_name', _find)
    monkeypatch.setattr(sonarr, 'rescan_series', _rescan)
    monkeypatch.setattr(sonarr, 'wait_for_command', _wait)
    monkeypatch.setattr(sonarr, 'rename_series', _rename)
    return state


def _prime_cache():
    with sonarr._cache_lock:
        sonarr._cache['series'] = (sonarr.time.time(), SERIES)
        sonarr._cache['episodes:1'] = (sonarr.time.time(), EPISODES_GAME_CHANGER)


class TestRefreshAndRescanSeries:
    def test_waits_and_clears_cache_without_rename(self, rescan_stubs):
        _prime_cache()
        assert sonarr.refresh_and_rescan_series('Game Changer') is True
        assert rescan_stubs['calls'] == [('find', 'Game Changer', None), ('rescan', 1), ('wait', 99)]
        assert sonarr._cache == {}

    def test_rename_runs_after_wait(self, rescan_stubs):
        assert sonarr.refresh_and_rescan_series('Game Changer', 'Game Changer (2019)', do_rename=True) is True
        assert rescan_stubs['calls'] == [
            ('find', 'Game Changer', 'Game Changer (2019)'), ('rescan', 1), ('wait', 99), ('rename', (1,)),
        ]

    def test_no_command_id_skips_wait_but_still_clears_cache(self, rescan_stubs):
        rescan_stubs['rescan_response'] = {}
        _prime_cache()
        assert sonarr.refresh_and_rescan_series('Game Changer') is True
        assert [c[0] for c in rescan_stubs['calls']] == ['find', 'rescan']
        assert sonarr._cache == {}

    def test_timeout_still_clears_cache(self, rescan_stubs):
        rescan_stubs['wait_status'] = 'timeout'
        _prime_cache()
        assert sonarr.refresh_and_rescan_series('Game Changer') is True
        assert sonarr._cache == {}

    def test_series_not_found_returns_false_and_keeps_cache(self, rescan_stubs):
        rescan_stubs['series_id'] = None
        _prime_cache()
        assert sonarr.refresh_and_rescan_series('Nope') is False
        assert [c[0] for c in rescan_stubs['calls']] == ['find']
        assert 'series' in sonarr._cache

    def test_disabled_returns_false(self, rescan_stubs, monkeypatch):
        monkeypatch.setattr(sonarr, 'SONARR_URL', '')
        assert sonarr.refresh_and_rescan_series('Game Changer') is False
        assert rescan_stubs['calls'] == []

    def test_wait_http_error_still_clears_cache(self, rescan_stubs, monkeypatch):
        def _boom(command_id, timeout=30, poll_interval=3):
            raise requests.ConnectionError('down')
        monkeypatch.setattr(sonarr, 'wait_for_command', _boom)
        _prime_cache()
        assert sonarr.refresh_and_rescan_series('Game Changer') is True
        assert sonarr._cache == {}
