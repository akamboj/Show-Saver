import time

import pytest

from showsaver.processors import dropout


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
    }

    monkeypatch.setattr(dropout, '_get_new_releases_bs', lambda: state['scraped'])
    monkeypatch.setattr(dropout.database, 'get_dropout_episode', lambda _url_path: state['db_row'])

    def _basic(*_args, **_kwargs):
        state['basic_upserts'] += 1
    monkeypatch.setattr(dropout.database, 'upsert_dropout_episode_basic', _basic)

    def _queue(url, url_path):
        state['enqueued'].append((url, url_path))
    monkeypatch.setattr(dropout, 'queue_metadata', _queue)

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
