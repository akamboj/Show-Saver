import re

DOUBLE_QUOTE = '"'
FULLWIDTH_DOUBLE_QUOTE = '\uff02'


def normalize_title(title: str) -> str:
    title = title.replace(FULLWIDTH_DOUBLE_QUOTE, '\'')
    title = title.replace(DOUBLE_QUOTE, '\'')
    title = title.replace('?', '')
    return title


def title_match_key(title: str | None) -> str:
    """
    Reduce a title to a loose comparison key: lowercase alphanumerics only.

    DB titles have already been through normalize_title (quotes -> ', '?' removed)
    while Sonarr/TVDB titles have not, so compare on a key that ignores case and
    punctuation entirely.
    """
    return re.sub(r'[^a-z0-9]+', '', (title or '').lower())
