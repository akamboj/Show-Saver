import re

from yt_dlp.utils import sanitize_filename

DOUBLE_QUOTE = '"'
FULLWIDTH_DOUBLE_QUOTE = '\uff02'


def normalize_title(title: str) -> str:
    """Apply yt-dlp's ``filename-sanitization`` compat rules, the same ones ``download_show`` uses.

    A literal U+FF02 (full-width double quote) is first folded to ``"`` so it sanitizes to ``'``
    like an ASCII quote. U+FF07 (full-width apostrophe) and curly quotes are deliberately left as-is."""
    return sanitize_filename(title.replace(FULLWIDTH_DOUBLE_QUOTE, DOUBLE_QUOTE), is_id=False)


def title_match_key(title: str | None) -> str:
    """Lowercase alphanumerics only, so raw DB titles match Sonarr titles regardless of punctuation."""
    return re.sub(r'[^a-z0-9]+', '', (title or '').lower())
