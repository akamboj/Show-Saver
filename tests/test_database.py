import time

import pytest

from showsaver import database


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    database.init_db()
    return database


URL_PATH = 'some-episode'
URL = 'https://watch.dropout.tv/videos/some-episode'
TITLE = 'Some Episode Title'
THUMB = 'https://img.example/thumb.jpg'
DURATION = 1234


class TestUpsertBasic:
    def test_basic_insert_creates_row_with_empty_show_name(self, db):
        db.upsert_dropout_episode_basic(URL_PATH, URL, TITLE, THUMB, DURATION)
        row = db.get_dropout_episode(URL_PATH)
        assert row is not None
        assert row['show_name'] == ''
        assert row['url'] == URL
        assert row['title'] == TITLE
        assert row['thumbnail'] == THUMB
        assert row['duration'] == DURATION

    def test_basic_does_not_clobber_show_name_after_full_upsert(self, db):
        db.upsert_dropout_episode_basic(URL_PATH, URL, TITLE, THUMB, DURATION)
        db.upsert_dropout_episode(URL_PATH, URL, 'Game Changer', TITLE, THUMB, DURATION)

        # Re-scrape with updated title/thumbnail/duration but no show_name available
        new_title = 'Updated Title'
        new_thumb = 'https://img.example/new.jpg'
        new_duration = 9999
        db.upsert_dropout_episode_basic(URL_PATH, URL, new_title, new_thumb, new_duration)

        row = db.get_dropout_episode(URL_PATH)
        assert row['show_name'] == 'Game Changer'
        assert row['title'] == new_title
        assert row['thumbnail'] == new_thumb
        assert row['duration'] == new_duration

    def test_basic_advances_fetched_at(self, db):
        db.upsert_dropout_episode_basic(URL_PATH, URL, TITLE, THUMB, DURATION)
        first = db.get_dropout_episode(URL_PATH)['fetched_at']
        time.sleep(0.01)
        db.upsert_dropout_episode_basic(URL_PATH, URL, TITLE, THUMB, DURATION)
        second = db.get_dropout_episode(URL_PATH)['fetched_at']
        assert second > first


class TestUpsertFull:
    def test_full_upsert_after_basic_sets_show_name(self, db):
        db.upsert_dropout_episode_basic(URL_PATH, URL, TITLE, THUMB, DURATION)
        db.upsert_dropout_episode(URL_PATH, URL, 'Dropout Presents', TITLE, THUMB, DURATION)
        row = db.get_dropout_episode(URL_PATH)
        assert row['show_name'] == 'Dropout Presents'

    def test_full_upsert_overwrites_existing_show_name(self, db):
        db.upsert_dropout_episode(URL_PATH, URL, 'Old Show', TITLE, THUMB, DURATION)
        db.upsert_dropout_episode(URL_PATH, URL, 'New Show', TITLE, THUMB, DURATION)
        row = db.get_dropout_episode(URL_PATH)
        assert row['show_name'] == 'New Show'


class TestReads:
    def test_get_unknown_url_path_returns_none(self, db):
        assert db.get_dropout_episode('does-not-exist') is None

    def test_get_all_empty_returns_empty_list(self, db):
        assert db.get_all_dropout_episodes() == []

    def test_get_all_returns_all_rows(self, db):
        db.upsert_dropout_episode('a', 'http://x/a', 'Show A', 'Title A', 'thumb', 100)
        db.upsert_dropout_episode('b', 'http://x/b', 'Show B', 'Title B', 'thumb', 200)
        rows = db.get_all_dropout_episodes()
        assert len(rows) == 2
        assert {r['url_path'] for r in rows} == {'a', 'b'}
