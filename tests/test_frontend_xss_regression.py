import re
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / 'showsaver' / 'static' / 'js' / 'app.js'


def test_app_js_does_not_assign_inner_html():
    source = APP_JS.read_text()

    assert not re.search(r'\.innerHTML\s*=', source)


def test_app_js_does_not_render_queue_or_release_cards_with_template_html():
    source = APP_JS.read_text()

    unsafe_patterns = [
        r'allItems\.map\([^)]*=>\s*`',
        r'videos\.map\([^)]*=>\s*`',
        r'<div\s+class=["\']queue-item',
        r'<div\s+class=["\']release-card',
    ]
    for pattern in unsafe_patterns:
        assert not re.search(pattern, source, flags=re.DOTALL)


def test_app_js_does_not_interpolate_data_url_selectors():
    source = APP_JS.read_text()

    assert not re.search(r'querySelector\(\s*`[^`]*\[data-url=', source)
