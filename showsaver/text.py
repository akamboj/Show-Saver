import re

DOUBLE_QUOTE = '"'
FULLWIDTH_DOUBLE_QUOTE = '\uff02'


def normalize_title(title: str) -> str:
    title = title.replace(FULLWIDTH_DOUBLE_QUOTE, '\'')
    title = title.replace(DOUBLE_QUOTE, '\'')
    title = title.replace('?', '')
    return title


def title_match_key(title: str | None) -> str:
    """Lowercase alphanumerics only, so normalized DB titles match raw Sonarr titles."""
    return re.sub(r'[^a-z0-9]+', '', (title or '').lower())
