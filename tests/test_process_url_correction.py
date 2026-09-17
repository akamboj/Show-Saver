import showsaver.downloader as downloader
from showsaver.processors import Processor

ORIGINAL_URL = 'https://watch.dropout.tv/videos/poppy-persona-non-grata'
CORRECTED_URL = 'https://watch.dropout.tv/dimension-20-the-complete-series/season:28/videos/poppy-persona-non-grata'
ORIGINAL_INFO = {'series': 'Dimension 20: Gladlands', 'title': 'Poppy Persona Non Grata'}
CORRECTED_INFO = {'series': 'Dimension 20', 'title': 'Poppy Persona Non Grata', 'season_number': 28}


class _RecordingProcessor(Processor):
    def __init__(self):
        self.correct_calls = []
        self.info_dicts_seen = []

    def find_corrected_url(self, show_url, info_dict):
        self.correct_calls.append((show_url, info_dict))
        return CORRECTED_URL, dict(CORRECTED_INFO)

    def process_info_dict(self, info_dict):
        self.info_dicts_seen.append(dict(info_dict))


def test_corrected_url_and_info_are_used_before_processing(monkeypatch, tmp_path):
    downloads = []

    def fake_download_show(show_url, info_dict, progress_callback=None, processor=None):
        downloads.append((show_url, info_dict))
        return str(tmp_path / 'file.mkv')

    monkeypatch.setattr(downloader, 'get_metadata', lambda url: dict(ORIGINAL_INFO))
    monkeypatch.setattr(downloader, 'download_show', fake_download_show)
    monkeypatch.setattr(downloader, 'copy_to_destination', lambda *a, **k: None)
    monkeypatch.setattr(downloader, 'refresh_and_rescan_series', lambda *a, **k: None)
    monkeypatch.setattr(downloader, 'DO_CLEANUP', False)
    processor = _RecordingProcessor()

    downloader.process_url(ORIGINAL_URL, tmp_path, processor=processor)

    assert processor.correct_calls == [(ORIGINAL_URL, ORIGINAL_INFO)]
    assert processor.info_dicts_seen == [CORRECTED_INFO]
    assert downloads == [(CORRECTED_URL, CORRECTED_INFO)]
