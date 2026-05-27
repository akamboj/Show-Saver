from showsaver.text import normalize_title


def test_normalize_title_replaces_fullwidth_double_quote():
    assert normalize_title('Some \uff02Quoted\uff02 Title') == 'Some \'Quoted\' Title'


def test_normalize_title_replaces_fullwidth_double_quote_char():
    assert normalize_title('Some ＂Quoted＂ Title') == 'Some \'Quoted\' Title'


def test_normalize_title_leaves_other_titles_unchanged():
    title = 'Some \'Quoted\' Title'
    assert normalize_title(title) == title
