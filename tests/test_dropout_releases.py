import time

import pytest

from showsaver.processors import dropout


def _no_network(*_args, **_kwargs):
    raise AssertionError('unexpected network or yt-dlp call')


@pytest.fixture
def mock_releases(monkeypatch):
    """Wires up get_new_releases dependencies and tracks queue_metadata calls."""
    # Reset in-memory cache so each test starts clean
    dropout._new_releases_cache['data'] = None
    dropout._new_releases_cache['timestamp'] = 0

    state = {
        'scraped': [
            {'id': 1, 'url': 'https://watch.dropout.tv/videos/ep-one',
             'title': 'Ep One', 'thumbnail': 'https://t/1.jpg', 'duration': 100},
        ],
        'db_row': None,
        'enqueued': [],
        'basic_upserts': 0,
        'in_library': None,
        'sonarr_calls': [],
        'cache_clears': 0,
    }

    # The annotate path must never hit the network or yt-dlp; only the scrape does.
    monkeypatch.setattr(dropout.requests, 'get', _no_network)
    monkeypatch.setattr(dropout, 'get_metadata', _no_network)
    monkeypatch.setattr(dropout, '_get_new_releases_bs', lambda: state['scraped'])
    monkeypatch.setattr(dropout.database, 'get_dropout_episode', lambda _url_path: state['db_row'])

    def _basic(*_args, **_kwargs):
        state['basic_upserts'] += 1
    monkeypatch.setattr(dropout.database, 'upsert_dropout_episode_basic', _basic)

    def _queue(url, url_path):
        state['enqueued'].append((url, url_path))
    monkeypatch.setattr(dropout, 'queue_metadata', _queue)

    def _in_library(show_name, override_name, season_number, episode_number, title):
        state['sonarr_calls'].append({
            'show_name': show_name,
            'override_name': override_name,
            'season_number': season_number,
            'episode_number': episode_number,
            'title': title,
        })
        return state['in_library']
    monkeypatch.setattr(dropout.sonarr, 'is_episode_in_library', _in_library)

    def _clear():
        state['cache_clears'] += 1
    monkeypatch.setattr(dropout.sonarr, 'clear_cache', _clear)

    return state


class TestQueueMetadataGating:
    def test_empty_show_name_with_no_prior_fetch_enqueues(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': None}
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['enqueued'] == [
            ('https://watch.dropout.tv/videos/ep-one', 'ep-one')
        ]

    def test_empty_show_name_with_recent_fetch_skips(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': time.time() - 60}
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['enqueued'] == []

    def test_empty_show_name_with_stale_fetch_enqueues(self, mock_releases):
        stale = time.time() - (dropout.METADATA_CACHE_TTL + 60)
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': stale}
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['enqueued'] == [
            ('https://watch.dropout.tv/videos/ep-one', 'ep-one')
        ]

    def test_non_empty_show_name_skips_regardless_of_age(self, mock_releases):
        # Even with a stale metadata_fetched_at, having a show_name means done
        stale = time.time() - (dropout.METADATA_CACHE_TTL + 60)
        mock_releases['db_row'] = {'show_name': 'Game Changer', 'metadata_fetched_at': stale}
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['enqueued'] == []

    def test_no_db_row_treats_as_never_fetched_and_enqueues(self, mock_releases):
        # First scrape ever: get_dropout_episode returns None
        mock_releases['db_row'] = None
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['enqueued'] == [
            ('https://watch.dropout.tv/videos/ep-one', 'ep-one')
        ]


class TestApiPayload:
    def test_response_includes_metadata_fetched_at(self, mock_releases):
        ts = time.time() - 30
        mock_releases['db_row'] = {'show_name': 'Game Changer', 'metadata_fetched_at': ts}
        result = dropout.get_new_releases(force_refresh=True)
        assert result['success'] is True
        assert result['videos'][0]['metadata_fetched_at'] == ts

    def test_response_metadata_fetched_at_is_none_for_unfetched(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': None}
        result = dropout.get_new_releases(force_refresh=True)
        assert result['videos'][0]['metadata_fetched_at'] is None


def _row(**overrides):
    """A fully-fetched Game Changer S06E03 DB row, with optional field overrides."""
    return {'show_name': 'Game Changer', 'metadata_fetched_at': time.time(),
            'season_number': 6, 'episode_number': 3, **overrides}


class TestInLibraryAnnotation:
    @pytest.mark.parametrize('flag', [True, False, None])
    def test_in_library_propagates_from_sonarr(self, mock_releases, flag):
        mock_releases['db_row'] = _row()
        mock_releases['in_library'] = flag
        result = dropout.get_new_releases(force_refresh=True)
        assert result['videos'][0]['in_library'] is flag

    def test_empty_show_name_skips_sonarr(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': None}
        result = dropout.get_new_releases(force_refresh=True)
        assert result['videos'][0]['in_library'] is None
        assert mock_releases['sonarr_calls'] == []

    def test_season_and_episode_numbers_are_exposed(self, mock_releases):
        mock_releases['db_row'] = _row()
        result = dropout.get_new_releases(force_refresh=True)
        assert result['videos'][0]['season_number'] == 6
        assert result['videos'][0]['episode_number'] == 3

    def test_dimension_20_season_is_remapped_before_lookup(self, mock_releases):
        mock_releases['db_row'] = _row(show_name='Dimension 20', season_number=30, episode_number=5)
        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert call['show_name'] == 'Dimension 20'
        assert call['season_number'] == 28
        assert call['episode_number'] == 5

    def test_special_is_zeroed_and_override_applied(self, mock_releases):
        mock_releases['scraped'][0]['title'] = 'Last Looks: Someone'
        mock_releases['db_row'] = _row(show_name='Very Important People', season_number=3, episode_number=7)
        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert call['override_name'] == 'Very Important People (2023)'
        assert (call['season_number'], call['episode_number']) == (0, 0)
        assert call['title'] == 'Last Looks: Someone'

    def test_show_without_override_forwards_none(self, mock_releases):
        mock_releases['db_row'] = _row(show_name='Dimension 20', season_number=6, episode_number=3)
        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert call['show_name'] == 'Dimension 20'
        assert call['override_name'] is None

    def test_null_numbers_pass_through_for_title_fallback(self, mock_releases):
        mock_releases['db_row'] = _row(show_name='Dimension 20', season_number=None, episode_number=None)
        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert (call['season_number'], call['episode_number']) == (None, None)

    def test_dimension_20_campaign_row_is_mapped_to_complete_series(self, mock_releases, monkeypatch):
        # The metadata worker stores the bare-url values (campaign series, season 1);
        # the badge lookup must use 'Dimension 20' + the sitemap season, offset-remapped.
        mock_releases['db_row'] = _row(show_name='Dimension 20: Toylight', season_number=1, episode_number=1)
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'ep-one': 31})
        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert call['show_name'] == 'Dimension 20'
        assert call['override_name'] is None
        assert call['season_number'] == 29
        assert call['episode_number'] == 1
        assert call['title'] == 'Ep One'

    def test_dimension_20_campaign_row_missing_from_sitemap_falls_through(self, mock_releases, monkeypatch):
        mock_releases['db_row'] = _row(show_name='Dimension 20: Toylight', season_number=1, episode_number=1)
        map_calls = []

        def season_map(force_refresh=False):
            map_calls.append(force_refresh)
            return {'other': 31}
        monkeypatch.setattr(dropout, '_get_d20_season_map', season_map)

        dropout.get_new_releases(force_refresh=True)
        call = mock_releases['sonarr_calls'][0]
        assert call['show_name'] == 'Dimension 20: Toylight'
        assert (call['season_number'], call['episode_number']) == (1, 1)
        assert map_calls == [False]

    def test_cached_path_maps_dimension_20_campaign_row(self, mock_releases, monkeypatch):
        mock_releases['db_row'] = _row(show_name='Dimension 20: Toylight', season_number=1, episode_number=3,
                                       url='https://watch.dropout.tv/videos/ep-one', title='Ep One')
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'ep-one': 28})
        dropout._new_releases_cache['data'] = ['https://watch.dropout.tv/videos/ep-one']
        dropout._new_releases_cache['timestamp'] = time.time()
        result = dropout.get_new_releases(force_refresh=False)
        assert result['cached'] is True
        call = mock_releases['sonarr_calls'][0]
        assert (call['show_name'], call['season_number'], call['episode_number']) == ('Dimension 20', 27, 3)

    def test_cached_path_is_annotated(self, mock_releases):
        mock_releases['db_row'] = _row(url='https://watch.dropout.tv/videos/ep-one')
        mock_releases['in_library'] = True
        dropout._new_releases_cache['data'] = ['https://watch.dropout.tv/videos/ep-one']
        dropout._new_releases_cache['timestamp'] = time.time()
        result = dropout.get_new_releases(force_refresh=False)
        assert result['cached'] is True
        assert result['videos'][0]['in_library'] is True

    def test_force_refresh_clears_sonarr_cache(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': None}
        dropout.get_new_releases(force_refresh=True)
        assert mock_releases['cache_clears'] == 1

    def test_unforced_fetch_keeps_sonarr_cache(self, mock_releases):
        mock_releases['db_row'] = {'show_name': '', 'metadata_fetched_at': None}
        dropout.get_new_releases(force_refresh=False)
        assert mock_releases['cache_clears'] == 0
