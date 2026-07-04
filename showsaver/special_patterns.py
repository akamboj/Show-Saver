import re
import tomllib
from pathlib import Path

from showsaver.env import SPECIAL_PATTERNS_PATH

BUNDLED_PATTERNS_PATH = Path(__file__).parent / 'special_patterns.toml'

# Cache of compiled rules; None means not loaded yet
_patterns_cache: list[tuple[re.Pattern, re.Pattern]] | None = None


def _read_text(source: Path) -> str:
    # Kept separate from parsing so the source can later be a hosted URL
    return source.read_text(encoding='utf-8')


def _parse_rules(text: str) -> list[tuple[re.Pattern, re.Pattern]]:
    rules = []
    for rule in tomllib.loads(text).get('special', []):
        series = rule.get('series')
        titles = rule.get('titles')
        if not isinstance(series, str) or not isinstance(titles, list) or not titles:
            print(f"Special patterns: skipping rule missing 'series' or 'titles': {rule}")
            continue
        try:
            series_pattern = re.compile(series, re.IGNORECASE)
        except re.error as e:
            print(f"Special patterns: skipping rule with invalid series regex ({e}): {rule}")
            continue
        for title in titles:
            try:
                rules.append((series_pattern, re.compile(title, re.IGNORECASE)))
            except (re.error, TypeError) as e:
                print(f"Special patterns: skipping title with invalid regex ({e}): {title!r}")
    return rules


def get_special_patterns() -> list[tuple[re.Pattern, re.Pattern]]:
    """Load the special-detection rules, cached after the first call."""
    global _patterns_cache
    if _patterns_cache is None:
        source = Path(SPECIAL_PATTERNS_PATH) if SPECIAL_PATTERNS_PATH else BUNDLED_PATTERNS_PATH
        try:
            _patterns_cache = _parse_rules(_read_text(source))
        except Exception as e:
            print(f"Special patterns: failed to load '{source}' ({e}); no episodes will be treated as specials")
            _patterns_cache = []
    return _patterns_cache


def clear_cache() -> None:
    global _patterns_cache
    _patterns_cache = None
