import pytest

from showsaver.processors.dropout import DropoutProcessor


@pytest.fixture
def processor():
    return DropoutProcessor()


class TestProcessInfoDictLastLooks:
    def test_last_looks_zeros_season_and_episode(self, processor):
        info = {
            'series': 'Very Important People',
            'title': 'Last Looks: Some Guest',
            'season_number': 3,
            'episode_number': 7,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 0
        assert info['episode_number'] == 0

    def test_last_looks_overwrites_nonzero_episode(self, processor):
        info = {
            'series': 'Very Important People',
            'title': 'Last Looks with Someone',
            'season_number': 1,
            'episode_number': 12,
        }
        processor.process_info_dict(info)
        assert info['episode_number'] == 0

    def test_vip_without_last_looks_in_title_unchanged(self, processor):
        info = {
            'series': 'Very Important People',
            'title': 'Regular Episode',
            'season_number': 2,
            'episode_number': 4,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 2
        assert info['episode_number'] == 4


class TestProcessInfoDictOtherSpecials:
    @pytest.mark.parametrize('series,title', [
        ('Game Changer', 'Behind the Scenes of "Night Shift"'),
        ('Smartypants', 'Smartyshorts: Why Pockets Are a Scam'),
        ('Very Important People', 'Very Important Bonus Content'),
    ])
    def test_special_zeros_season_and_episode(self, processor, series, title):
        info = {
            'series': series,
            'title': title,
            'season_number': 5,
            'episode_number': 3,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 0
        assert info['episode_number'] == 0

    def test_special_match_is_case_insensitive(self, processor):
        info = {
            'series': 'very important people',
            'title': 'last looks: some guest',
            'season_number': 2,
            'episode_number': 8,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 0
        assert info['episode_number'] == 0

    def test_none_series_and_title_do_not_crash(self, processor):
        info = {
            'series': None,
            'title': None,
            'season_number': 4,
            'episode_number': 6,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 4
        assert info['episode_number'] == 6


class TestProcessInfoDictDimension20:
    # Seaon 27 is now On a Bus S1, and 28 is On a Bus S2. We need to decrement season number for each
    # 5/27/26 - TVDB seasons now match official listings. This is no longer needed for D20
    # 5/28.26 - TVDB undid the change
    @pytest.mark.parametrize('season_in,season_out', [
        (1, 1),
        (27, 27),
        (28, 27),
        (29, 28),
        (30, 28),
        (31, 29),
    ])
    def test_dim20_season_offsets(self, processor, season_in, season_out):
        info = {
            'series': 'Dimension 20',
            'title': 'Some Episode',
            'season_number': season_in,
            'episode_number': 5,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == season_out
        assert info['episode_number'] == 5

    def test_dim20_substring_does_not_match(self, processor):
        info = {
            'series': 'Dimension 20: Fantasy High',
            'title': 'Episode 1',
            'season_number': 30,
            'episode_number': 1,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 30


class TestProcessInfoDictAdventuringParty:
    @pytest.mark.parametrize('season_in,season_out', [
        (1, 1),
        (23, 23),
        (24, 23),
        (25, 24),
    ])
    def test_adventuring_party_season_offsets(self, processor, season_in, season_out):
        info = {
            'series': "Dimension 20's Adventuring Party",
            'title': 'AP Episode',
            'season_number': season_in,
            'episode_number': 2,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == season_out


class TestProcessInfoDictNoMatch:
    def test_unknown_series_unchanged(self, processor):
        info = {
            'series': 'Game Changer',
            'title': 'Some Episode',
            'season_number': 5,
            'episode_number': 3,
        }
        processor.process_info_dict(info)
        assert info['season_number'] == 5
        assert info['episode_number'] == 3

    def test_missing_season_number_defaults_to_zero(self, processor):
        info = {
            'series': 'Dimension 20',
            'title': 'Episode',
        }
        processor.process_info_dict(info)
        assert 'season_number' not in info or info['season_number'] == 0

    def test_null_season_number_does_not_crash(self, processor):
        info = {
            'series': 'Dimension 20',
            'title': 'Episode',
            'season_number': None,
            'episode_number': None,
        }
        processor.process_info_dict(info)
        assert info['season_number'] is None


class TestFetchAndStoreEpisodeInfo:
    def test_persists_raw_season_and_episode_numbers(self, monkeypatch):
        from showsaver.processors import dropout

        class _FakeYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def extract_info(self, _url, download=False):
                return {
                    'title': 'Some Episode',
                    'webpage_url': 'https://watch.dropout.tv/videos/some-episode',
                    'thumbnail': 'https://t/1.jpg',
                    'duration': 100,
                    'id': 'abc',
                    'series': 'Dimension 20',
                    'season_number': 30,
                    'episode_number': 5,
                }

        captured = {}

        def _upsert(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(dropout.yt_dlp, 'YoutubeDL', _FakeYDL)
        monkeypatch.setattr(dropout.database, 'upsert_dropout_episode', _upsert)

        result = dropout.fetch_and_store_episode_info('https://watch.dropout.tv/videos/some-episode')

        assert result['season_number'] == 30
        assert result['episode_number'] == 5
        # Raw yt-dlp value is stored; the D20 remap happens at read time
        assert captured['season_number'] == 30
        assert captured['episode_number'] == 5
        assert captured['url_path'] == 'some-episode'
        assert captured['show_name'] == 'Dimension 20'

    def test_missing_numbers_persist_as_none(self, monkeypatch):
        from showsaver.processors import dropout

        class _FakeYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def extract_info(self, _url, download=False):
                return {'title': 'T', 'webpage_url': 'https://watch.dropout.tv/videos/x', 'series': 'S'}

        captured = {}
        monkeypatch.setattr(dropout.yt_dlp, 'YoutubeDL', _FakeYDL)
        monkeypatch.setattr(dropout.database, 'upsert_dropout_episode', lambda **kw: captured.update(kw))

        dropout.fetch_and_store_episode_info('https://watch.dropout.tv/videos/x')

        assert captured['season_number'] is None
        assert captured['episode_number'] is None
