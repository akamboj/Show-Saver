import os

import pytest
import yt_dlp

from showsaver.downloader import BASE_YT_OPTS
from showsaver.text import normalize_title, title_match_key


def test_normalize_title_replaces_fullwidth_double_quote():
    assert normalize_title('Some \uff02Quoted\uff02 Title') == 'Some \'Quoted\' Title'


def test_normalize_title_replaces_fullwidth_double_quote_char():
    assert normalize_title('Some ＂Quoted＂ Title') == 'Some \'Quoted\' Title'


def test_normalize_title_leaves_other_titles_unchanged():
    title = 'Some \'Quoted\' Title'
    assert normalize_title(title) == title


def test_normalize_title_folds_fullwidth_quotes_that_ytdlp_passes_through():
    ydl = yt_dlp.YoutubeDL({
        'compat_opts': {'filename-sanitization'},
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
    })

    filename = ydl.prepare_filename({
        'title': 'Some \uff02Quoted\uff02 Title',
        'ext': 'mkv',
    })

    assert filename == 'Some \uff02Quoted\uff02 Title.mkv'
    assert normalize_title(filename) == 'Some \'Quoted\' Title.mkv'


@pytest.mark.parametrize('title, expected', [
    ('J*r J*r B*nks WEBDL-1080p.mkv', 'J_r J_r B_nks WEBDL-1080p.mkv'),
    ('Last Looks: Sam?', 'Last Looks - Sam'),
    ('This/That', 'This_That'),
    ('A|B', 'A_B'),
])
def test_normalize_title_applies_ytdlp_filename_rules(title, expected):
    assert normalize_title(title) == expected


@pytest.mark.parametrize('title', [
    'J*r J*r B*nks',
    'Last Looks: "Sam"?',
    'This/That | <Other>',
])
def test_normalize_title_matches_ytdlp_prepare_filename(title):
    ydl = yt_dlp.YoutubeDL({
        'compat_opts': {'filename-sanitization'},
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
    })

    filename = ydl.prepare_filename({'title': title, 'ext': 'mkv'})

    assert filename == normalize_title(title) + '.mkv'


def test_prepare_filename_with_real_download_opts_matches_disk_and_is_idempotent(tmp_path):
    """Mirrors download_show(): the path includes paths.home, every field is compat-sanitized,
    and normalize_title() is a no-op on the resulting basename (copy_to_destination relies on this)."""
    ydl = yt_dlp.YoutubeDL({
        **BASE_YT_OPTS,
        'outtmpl': {'default': '%(series)s - S%(season_number)02dE%(episode_number)02d - %(title)s WEBDL-1080p.%(ext)s'},
        'paths': {'home': str(tmp_path)},
        'quiet': True,
    })

    path = ydl.prepare_filename({
        'series': 'Dimension 20: Fantasy High',
        'season_number': 1,
        'episode_number': 2,
        'title': 'Last Looks: "Sam"? This/That',
        'ext': 'mkv',
    })

    assert path.startswith(str(tmp_path))
    basename = os.path.basename(path)
    assert basename == "Dimension 20 - Fantasy High - S01E02 - Last Looks - 'Sam' This_That WEBDL-1080p.mkv"
    assert normalize_title(basename) == basename


class TestTitleMatchKey:
    @pytest.mark.parametrize('title, expected', [
        ('Last Looks: "Sam"?', 'lastlookssam'),  # lowercased, punctuation stripped
        ('The  Big - One', 'thebigone'),          # whitespace and hyphens ignored
        (None, ''),
        ('', ''),
    ])
    def test_key(self, title, expected):
        assert title_match_key(title) == expected

    def test_normalized_and_raw_titles_share_a_key(self):
        raw = 'Last Looks: "Sam"?'
        assert title_match_key(normalize_title(raw)) == title_match_key(raw)
