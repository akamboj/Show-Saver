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


class TestProcessInfoDictDimension20:
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
