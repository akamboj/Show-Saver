import yt_dlp

from showsaver.text import normalize_title


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
