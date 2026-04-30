import os

import pytest

from showsaver.downloader import copy_to_destination
from showsaver.processors import Processor


class _OverrideProcessor(Processor):
    def __init__(self, mapping):
        self._mapping = mapping

    def process_show_name(self, show_name):
        return self._mapping.get(show_name, show_name)


@pytest.fixture
def src_file(tmp_path):
    """A dummy downloaded file matching the show output template."""
    src_dir = tmp_path / 'src'
    src_dir.mkdir()
    path = src_dir / 'Very Important People - S02E04 - Some Guest WEBDL-1080p.mkv'
    path.write_bytes(b'fake video bytes')
    return path


@pytest.fixture
def dest_dir(tmp_path):
    d = tmp_path / 'tvshows'
    d.mkdir()
    return d


def test_regular_episode_lands_in_season_folder(src_file, dest_dir):
    info = {'series': 'Very Important People', 'season_number': 2}
    copy_to_destination(info, str(src_file), str(dest_dir))
    expected = dest_dir / 'Very Important People' / 'Season 2' / src_file.name
    assert expected.is_file()


def test_special_lands_in_specials_folder(src_file, dest_dir):
    info = {'series': 'Very Important People', 'season_number': 0}
    copy_to_destination(info, str(src_file), str(dest_dir))
    expected = dest_dir / 'Very Important People' / 'Specials' / src_file.name
    assert expected.is_file()


def test_processor_override_rewrites_folder_and_filename(src_file, dest_dir):
    info = {'series': 'Very Important People', 'season_number': 2}
    processor = _OverrideProcessor({
        'Very Important People': 'Very Important People (2023)',
    })
    copy_to_destination(info, str(src_file), str(dest_dir), processor)

    overridden_dir = dest_dir / 'Very Important People (2023)' / 'Season 2'
    assert overridden_dir.is_dir()

    files = list(overridden_dir.iterdir())
    assert len(files) == 1
    written = files[0]
    assert 'Very Important People (2023)' in written.name
    # The original (non-overridden) show name must not appear standalone in the filename
    # (it would only appear as a prefix of the overridden name).
    assert written.name.replace('Very Important People (2023)', '') \
        .find('Very Important People') == -1

    # Original folder should not exist
    assert not (dest_dir / 'Very Important People').exists()


def test_noop_processor_leaves_filename_untouched(src_file, dest_dir):
    info = {'series': 'Very Important People', 'season_number': 2}
    processor = _OverrideProcessor({})  # no overrides
    copy_to_destination(info, str(src_file), str(dest_dir), processor)
    expected = dest_dir / 'Very Important People' / 'Season 2' / src_file.name
    assert expected.is_file()


def test_destination_file_is_readable(src_file, dest_dir):
    info = {'series': 'Very Important People', 'season_number': 2}
    copy_to_destination(info, str(src_file), str(dest_dir))
    expected = dest_dir / 'Very Important People' / 'Season 2' / src_file.name
    assert os.access(expected, os.R_OK)
    assert expected.read_bytes() == b'fake video bytes'
