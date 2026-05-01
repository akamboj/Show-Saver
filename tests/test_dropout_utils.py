from showsaver.processors.dropout import _time_to_sec, _get_url_path


class TestTimeToSec:
    def test_seconds_only(self):
        assert _time_to_sec("45") == 45

    def test_minutes_and_seconds(self):
        assert _time_to_sec("1:30") == 90

    def test_hours_minutes_seconds(self):
        assert _time_to_sec("1:02:03") == 3723

    def test_zero(self):
        assert _time_to_sec("0") == 0

    def test_zero_padded_mm_ss(self):
        assert _time_to_sec("01:05") == 65

    def test_hour_boundary(self):
        assert _time_to_sec("1:00:00") == 3600


class TestGetUrlPath:
    def test_simple_path(self):
        assert _get_url_path("https://watch.dropout.tv/videos/some-episode") == "some-episode"

    def test_trailing_slash(self):
        assert _get_url_path("https://watch.dropout.tv/videos/some-episode/") == "some-episode"

    def test_deep_path(self):
        assert _get_url_path("https://watch.dropout.tv/a/b/c/episode-slug") == "episode-slug"

    def test_no_path(self):
        assert _get_url_path("https://watch.dropout.tv/") == ""

    def test_query_string_ignored(self):
        assert _get_url_path("https://watch.dropout.tv/videos/ep?ref=home") == "ep"
