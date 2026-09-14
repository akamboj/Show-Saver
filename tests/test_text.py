import yt_dlp

from showsaver.text import normalize_title, title_match_key


def test_normalize_title_replaces_fullwidth_double_quote():
    assert normalize_title('Some \uff02Quoted\uff02 Title') == 'Some \'Quoted\' Title'


def test_normalize_title_replaces_fullwidth_double_quote_char():
    assert normalize_title('Some ＂Quoted＂ Title') == 'Some \'Quoted\' Title'


def test_normalize_title_leaves_other_titles_unchanged():
    title = 'Some \'Quoted\' Title'
    assert normalize_title(title) == title


def test_normalize_title_handles_fullwidth_quotes_left_by_ytdlp_filename_sanitization():
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


class TestTitleMatchKey:
    def test_lowercases_and_strips_punctuation(self):
        assert title_match_key('Last Looks: "Sam"?') == 'lastlookssam'

    def test_normalized_and_raw_titles_share_a_key(self):
        raw = 'Last Looks: "Sam"?'
        assert title_match_key(normalize_title(raw)) == title_match_key(raw)

    def test_whitespace_and_hyphens_ignored(self):
        assert title_match_key('The  Big - One') == 'thebigone'

    def test_none_and_empty_return_empty(self):
        assert title_match_key(None) == ''
        assert title_match_key('') == ''
