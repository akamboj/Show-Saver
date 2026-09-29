import pytest

import showsaver.special_patterns as special_patterns


@pytest.fixture(autouse=True)
def fresh_cache():
    special_patterns.clear_cache()
    yield
    special_patterns.clear_cache()


def _use_file(monkeypatch, path):
    monkeypatch.setattr(special_patterns, 'SPECIAL_PATTERNS_PATH', str(path))


class TestGetSpecialPatterns:
    def test_valid_file_parses_case_insensitive_rules(self, monkeypatch, tmp_path):
        config = tmp_path / 'patterns.toml'
        config.write_text(
            "[[special]]\n"
            "series = 'Some Show'\n"
            "titles = ['Bonus Episodes?', 'Last Looks']\n"
        )
        _use_file(monkeypatch, config)

        rules = special_patterns.get_special_patterns()
        assert len(rules) == 2
        series_pattern, title_pattern = rules[0]
        assert series_pattern.search('some show presents')
        assert title_pattern.search('BONUS EPISODE 3')
        assert rules[1][1].search('last looks: someone')

    def test_bundled_file_loads(self):
        rules = special_patterns.get_special_patterns()
        assert len(rules) >= 4

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        _use_file(monkeypatch, tmp_path / 'does-not-exist.toml')
        assert special_patterns.get_special_patterns() == []

    def test_invalid_toml_returns_empty(self, monkeypatch, tmp_path):
        config = tmp_path / 'patterns.toml'
        config.write_text('[[special\nnot toml')
        _use_file(monkeypatch, config)
        assert special_patterns.get_special_patterns() == []

    def test_bad_rules_skipped_good_rules_survive(self, monkeypatch, tmp_path):
        config = tmp_path / 'patterns.toml'
        config.write_text(
            "[[special]]\n"
            "series = 'Missing Titles Show'\n"
            "\n"
            "[[special]]\n"
            "series = '(unclosed'\n"
            "titles = ['Fine Title']\n"
            "\n"
            "[[special]]\n"
            "series = 'Partly Bad Show'\n"
            "titles = ['(unclosed', 'Good Title']\n"
            "\n"
            "[[special]]\n"
            "series = 'Good Show'\n"
            "titles = ['Good Title']\n"
        )
        _use_file(monkeypatch, config)

        rules = special_patterns.get_special_patterns()
        assert len(rules) == 2
        assert rules[0][0].search('Partly Bad Show')
        assert rules[0][1].search('Good Title')
        assert rules[1][0].search('Good Show')

    def test_result_is_cached_until_cleared(self, monkeypatch, tmp_path):
        config = tmp_path / 'patterns.toml'
        config.write_text(
            "[[special]]\n"
            "series = 'Show'\n"
            "titles = ['Title']\n"
        )
        _use_file(monkeypatch, config)

        assert len(special_patterns.get_special_patterns()) == 1
        config.write_text('')
        assert len(special_patterns.get_special_patterns()) == 1
        special_patterns.clear_cache()
        assert special_patterns.get_special_patterns() == []
