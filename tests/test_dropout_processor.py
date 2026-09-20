import pytest

import showsaver.processors.dropout as dropout


@pytest.fixture
def processor():
    return dropout.DropoutProcessor()


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


class TestProcessDlpOpts:
    @pytest.mark.parametrize('season_number, expected', [(30, 'S30E'), (None, 'S0E')])
    def test_dimension_20_template_uses_season_number(self, processor, season_number, expected):
        info = {'series': 'Dimension 20', 'title': 'Episode', 'season_number': season_number}
        opts = {}
        processor.process_dlp_opts(opts, info)
        assert expected in opts['outtmpl']['default']
        assert 'SNone' not in opts['outtmpl']['default']


@pytest.fixture
def fake_ydl(monkeypatch):
    """Patch yt-dlp to return a fixed info dict; returns the kwargs captured by the DB upsert."""
    captured = {}

    def _install(info):
        class _FakeYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def extract_info(self, _url, download=False):
                return info

        monkeypatch.setattr(dropout.yt_dlp, 'YoutubeDL', _FakeYDL)
        monkeypatch.setattr(dropout.database, 'upsert_dropout_episode', lambda **kw: captured.update(kw))
        return captured

    return _install


class TestFetchAndStoreEpisodeInfo:
    def test_persists_raw_season_and_episode_numbers(self, fake_ydl):
        captured = fake_ydl({
            'title': 'Some Episode',
            'webpage_url': 'https://watch.dropout.tv/videos/some-episode',
            'thumbnail': 'https://t/1.jpg',
            'duration': 100,
            'id': 'abc',
            'series': 'Dimension 20',
            'season_number': 30,
            'episode_number': 5,
        })

        result = dropout.fetch_and_store_episode_info('https://watch.dropout.tv/videos/some-episode')

        assert result['season_number'] == 30
        assert result['episode_number'] == 5
        # Raw yt-dlp value is stored; the D20 remap happens at read time
        assert captured['season_number'] == 30
        assert captured['episode_number'] == 5
        assert captured['url_path'] == 'some-episode'
        assert captured['show_name'] == 'Dimension 20'

    def test_missing_numbers_persist_as_none(self, fake_ydl):
        captured = fake_ydl({'title': 'T', 'webpage_url': 'https://watch.dropout.tv/videos/x', 'series': 'S'})

        dropout.fetch_and_store_episode_info('https://watch.dropout.tv/videos/x')

        assert captured['season_number'] is None
        assert captured['episode_number'] is None


# ---------------------------------------------------------------------------
# Dimension 20 url correction
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code=200, text=''):
        self.status_code = status_code
        self.text = text


def _fail(*args, **kwargs):
    raise AssertionError('unexpected network call')


SITEMAP_SNIPPET = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://watch.dropout.tv/dimension-20-the-complete-series-season-28/videos/poppy-persona-non-grata</loc></url>
<url><loc>https://watch.dropout.tv/dimension-20-audio-only-season-27/videos/poppy-persona-non-grata-audio-only</loc></url>
<url><loc>https://watch.dropout.tv/dimension-20-gladlands-season-1/videos/poppy-persona-non-grata</loc></url>
</urlset>'''

D20_URL = 'https://watch.dropout.tv/videos/poppy-persona-non-grata'
CORRECTED_URL = 'https://watch.dropout.tv/dimension-20-the-complete-series/season:28/videos/poppy-persona-non-grata'


@pytest.fixture
def reset_d20_cache():
    dropout._d20_season_cache['data'] = None
    dropout._d20_season_cache['timestamp'] = 0
    yield
    dropout._d20_season_cache['data'] = None
    dropout._d20_season_cache['timestamp'] = 0


@pytest.mark.usefixtures('reset_d20_cache')
class TestGetD20SeasonMap:
    def test_parses_only_complete_series_entries(self, monkeypatch):
        monkeypatch.setattr(dropout.requests, 'get', lambda *a, **k: _Resp(200, SITEMAP_SNIPPET))
        assert dropout._get_d20_season_map() == {'poppy-persona-non-grata': 28}

    def test_second_call_uses_cache(self, monkeypatch):
        calls = []
        monkeypatch.setattr(dropout.requests, 'get', lambda *a, **k: calls.append(a) or _Resp(200, SITEMAP_SNIPPET))
        first = dropout._get_d20_season_map()
        second = dropout._get_d20_season_map()
        assert first == second
        assert len(calls) == 1

    def test_failed_refresh_returns_stale_map(self, monkeypatch):
        monkeypatch.setattr(dropout.requests, 'get', lambda *a, **k: _Resp(200, SITEMAP_SNIPPET))
        stale = dropout._get_d20_season_map()

        def boom(*a, **k):
            raise ConnectionError('offline')
        monkeypatch.setattr(dropout.requests, 'get', boom)
        assert dropout._get_d20_season_map(force_refresh=True) == stale

    def test_unparseable_sitemap_keeps_cached_map(self, monkeypatch):
        # A 200 that yields no entries means the sitemap changed shape, not that the
        # collection emptied -- it must not clobber a good map.
        monkeypatch.setattr(dropout.requests, 'get', lambda *a, **k: _Resp(200, SITEMAP_SNIPPET))
        good = dropout._get_d20_season_map()

        monkeypatch.setattr(dropout.requests, 'get', lambda *a, **k: _Resp(200, '<urlset></urlset>'))
        assert dropout._get_d20_season_map(force_refresh=True) == good
        assert dropout._d20_season_cache['data'] == good

    def test_empty_map_is_negatively_cached(self, monkeypatch):
        # An empty map is falsy, so a truthiness check on the cache would re-download
        # the ~1.4 MB sitemap on every single call.
        calls = []

        def get(*a, **k):
            calls.append(a)
            return _Resp(200, '<urlset></urlset>')
        monkeypatch.setattr(dropout.requests, 'get', get)

        dropout._d20_season_cache['data'] = {}
        dropout._d20_season_cache['timestamp'] = dropout.time.time()
        assert dropout._get_d20_season_map() == {}
        assert calls == []


@pytest.mark.usefixtures('reset_d20_cache')
class TestFindCorrectedUrl:
    @pytest.fixture(autouse=True)
    def no_network(self, monkeypatch):
        monkeypatch.setattr(dropout.requests, 'get', _fail)

    @pytest.fixture
    def metadata_calls(self, monkeypatch):
        calls = []
        monkeypatch.setattr(dropout, 'get_metadata',
                            lambda url: calls.append(url) or {'series': 'Dimension 20', 'season_number': 28})
        return calls

    @pytest.mark.parametrize('series', ['Game Changer', 'Dimension 20', None])
    def test_non_campaign_series_returns_none(self, processor, series):
        assert processor.find_corrected_url(D20_URL, {'series': series}) is None

    def test_uses_sitemap_map(self, processor, monkeypatch, metadata_calls):
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'poppy-persona-non-grata': 28})

        result = processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'})

        assert result == (CORRECTED_URL, {'series': 'Dimension 20', 'season_number': 28})
        assert metadata_calls == [CORRECTED_URL]

    def test_refreshes_sitemap_once_when_slug_missing(self, processor, monkeypatch, metadata_calls):
        # A stale map is the likeliest reason for a miss, so one forced refresh should
        # find a newly published episode -- with no url probing of any kind.
        map_calls = []

        def season_map(force_refresh=False):
            map_calls.append(force_refresh)
            return {'poppy-persona-non-grata': 28} if force_refresh else {'other': 31}
        monkeypatch.setattr(dropout, '_get_d20_season_map', season_map)

        result = processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'})

        assert map_calls == [False, True]
        assert result == (CORRECTED_URL, {'series': 'Dimension 20', 'season_number': 28})

    def test_returns_none_when_slug_missing_after_refresh(self, processor, monkeypatch):
        monkeypatch.setattr(dropout, 'get_metadata', _fail)
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'other': 31})

        assert processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'}) is None

    def test_empty_season_map_returns_none_without_probing(self, processor, monkeypatch):
        # Regression: an empty map used to seed a probe at season 40, which the site
        # answers 200 for any slug. There is no safe upper bound, so never guess.
        monkeypatch.setattr(dropout, 'get_metadata', _fail)
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {})

        assert processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'}) is None

    def test_metadata_failure_falls_back_to_original_url(self, processor, monkeypatch):
        # The original url is known to work; a corrected url we cannot read must not
        # take the whole download job down with it.
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'poppy-persona-non-grata': 28})

        def boom(url):
            raise RuntimeError('ERROR: unable to extract video data')
        monkeypatch.setattr(dropout, 'get_metadata', boom)

        assert processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'}) is None

    def test_metadata_returning_none_returns_none(self, processor, monkeypatch):
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'poppy-persona-non-grata': 28})
        monkeypatch.setattr(dropout, 'get_metadata', lambda url: None)

        assert processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'}) is None

    def test_rejects_metadata_without_season_number(self, processor, monkeypatch):
        monkeypatch.setattr(dropout, '_get_d20_season_map', lambda **k: {'poppy-persona-non-grata': 28})
        monkeypatch.setattr(dropout, 'get_metadata', lambda url: {'series': 'Dimension 20'})

        assert processor.find_corrected_url(D20_URL, {'series': 'Dimension 20: Gladlands'}) is None


class TestGetShowNameOverride:
    @pytest.mark.parametrize('show_name, expected', [
        ('Very Important People', 'Very Important People (2023)'),
        ('Don\'t Hug Me I\'m Scared', 'Don\'t Hug Me I\'m Scared (2022)'),
    ])
    def test_known_shows_return_their_override(self, processor, show_name, expected):
        assert processor.get_show_name_override(show_name) == expected

    @pytest.mark.parametrize('show_name', [
        'Dimension 20',
        'Game Changer',
        'very important people',  # overrides are exact-match, not case-insensitive
        '',
    ])
    def test_unknown_shows_return_none(self, processor, show_name):
        assert processor.get_show_name_override(show_name) is None
