import os
import requests
import shutil
import yt_dlp
import yt_dlp.postprocessor.metadataparser

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from env import (
    CONFIG_DIR, TMP_DIR, DO_CLEANUP
)
from sonarr import refresh_and_rescan_series


class StreamType(StrEnum):
    VIDEO = 'video'
    AUDIO = 'audio'
    VIDEO_AUDIO = 'video+audio'


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    percent: float
    step: int
    total_steps: int
    step_type: StreamType

    def __post_init__(self):
        if not 0.0 <= self.percent <= 100.0:
            raise ValueError(f"percent out of range: {self.percent}")
        if self.step < 1 or self.step > self.total_steps:
            raise ValueError(f"step {self.step} not in 1..{self.total_steps}")


ProgressCallback = Callable[[ProgressUpdate], None]

YT_REPLACE_COLON_ACTION = {
    'actions': [
        (yt_dlp.postprocessor.metadataparser.MetadataParserPP.replacer,
        'title',
        ':',
        ' -'),
        (yt_dlp.postprocessor.metadataparser.MetadataParserPP.replacer,
        'playlist',
        ':',
        ' -'),
        (yt_dlp.postprocessor.metadataparser.MetadataParserPP.replacer,
        'playlist_title',
        ':',
        ' -')
    ],
    'key': 'MetadataParser',
    'when': 'pre_process'
}

class DownloaderLogger:
    def debug(self, msg):
        # yt-dlp sends various info messages here.
        # To see progress, you'd usually ignore messages that don't start with '[debug]'
        if msg.startswith('[debug] ') or msg.startswith('[download] '):
            pass
        else:
            self.info(msg)
            pass

    def info(self, msg):
        #print(f"YTDLP INFO: {msg}")
        pass

    def warning(self, msg):
        if 'Failed to parse XML' not in msg:
            print(f"YTDLP WARNING: {msg}")

    def error(self, msg):
        print(f"YTDLP ERROR: {msg}")

def progress_hook(d):
    print(d['_default_template'])


BASE_YT_OPTS = {
    #'verbose' : True,
    'logger': DownloaderLogger(),
    'usenetrc' : True,
    'netrc_location' : str(CONFIG_DIR),
    #'netrc_cmd' : "echo machine dropout login {} password {}".format(USERNAME, PASSWORD),
    'paths' : {
        'home' : str(TMP_DIR)
    },
    'progress_hooks' : [progress_hook]
}

# yt-dlp docs
# https://github.com/yt-dlp/yt-dlp/blob/00dcde728635633eee969ad4d498b9f233c4a94e/yt_dlp/YoutubeDL.py#L212


# the info file has the show name and season number, we need these for building the destination path on the server
def get_metadata(show_url):
    dlp_opts = {
        **BASE_YT_OPTS,
        'skip_download' : True,
        'postprocessors': [
            YT_REPLACE_COLON_ACTION
        ]
    }
    yt = yt_dlp.YoutubeDL(dlp_opts)

    print('Downloading metadata for url: ' + show_url)
    info_dict = yt.extract_info(show_url)
    print('\nMetadata download complete!')
    return info_dict


def download_show(
    show_url: str,
    info_dict: dict,
    progress_callback: ProgressCallback | None = None,
    processor=None,
) -> str:
    download_state: dict = {'current_step': 0, 'steps': [], 'last_filename': None}

    def progress_hook_callback(download_progress):
        print(download_progress['_default_template'])
        if progress_callback and download_progress['status'] == 'downloading':
            info = download_progress.get('info_dict', {})
            vcodec = info.get('vcodec', 'none')
            acodec = info.get('acodec', 'none')
            filename = download_progress.get('filename', '')

            if vcodec != 'none' and acodec == 'none':
                stream_type = StreamType.VIDEO
            elif acodec != 'none' and vcodec == 'none':
                stream_type = StreamType.AUDIO
            else:
                stream_type = StreamType.VIDEO_AUDIO

            # Detect new step (filename changes)
            if filename != download_state['last_filename']:
                download_state['last_filename'] = filename
                if stream_type not in download_state['steps']:
                    download_state['steps'].append(stream_type)
                    download_state['current_step'] = len(download_state['steps'])

            # Calculate progress
            total = download_progress.get('total_bytes') or download_progress.get('total_bytes_estimate')
            percent = 0.0
            if total:
                percent = (download_progress.get('downloaded_bytes', 0) / total) * 100

            #print(f'Eta num {download_progress.get('eta', 0)}. eta str {download_progress.get('_eta_str', '')}')
            progress_callback(ProgressUpdate(
                percent=percent,
                step=download_state['current_step'],
                total_steps=max(len(download_state['steps']), download_state['current_step']),
                step_type=stream_type,
            ))

    dlp_opts = {
        **BASE_YT_OPTS,
        'outtmpl' : {'default' : '%(series)s - S%(season_number)02dE%(episode_number)02d - %(title)s WEBDL-1080p.%(ext)s'},
        'postprocessors': [
            {
                'api': 'https://sponsor.ajay.app',
                'key': 'SponsorBlock',
                'when': 'after_filter',
                'categories': ['sponsor', 'selfpromo', 'interaction', 'intro', 'outro']
            },
            {
                'key': 'ModifyChapters',
                'remove_sponsor_segments': ['sponsor', 'selfpromo', 'interaction', 'intro', 'outro'],
                'sponsorblock_chapter_title': '[SponsorBlock]: ' '%(category_names)l',
            },
            {
                'key': 'FFmpegEmbedSubtitle',
                'already_have_subtitle': False
            },
            YT_REPLACE_COLON_ACTION
        ],
        'writesubtitles' : True,
        'progress_hooks' : [progress_hook_callback]
    }
    if processor:
        processor.process_dlp_opts(dlp_opts, info_dict)
    yt = yt_dlp.YoutubeDL(dlp_opts)

    yt.download(show_url)
    show_file_name = yt.evaluate_outtmpl(dlp_opts['outtmpl']['default'], info_dict)
    show_path = os.path.abspath(os.path.join(dlp_opts['paths']['home'], show_file_name))
    return show_path


def copy_to_destination(info_dict, show_path, base_destination_path, processor=None):
    show_name = info_dict['series']
    season_number = info_dict['season_number']
    season_folder = 'Specials' if season_number == 0 else 'Season ' + str(season_number)
    episode_filename = os.path.basename(show_path)

    if processor:
        new_show_name = processor.process_show_name(show_name)
        if new_show_name != show_name:
            episode_filename = episode_filename.replace(show_name, new_show_name)
            show_name = new_show_name

    full_destination_path = os.path.join(base_destination_path, show_name, season_folder)
    full_episode_path = os.path.join(full_destination_path, episode_filename)

    print(f'Starting copy from: {show_path}, to: {full_destination_path}')
    os.makedirs(full_destination_path, exist_ok=True)
    os.chmod(full_destination_path, 0o777)

    shutil.copy2(show_path, full_episode_path)
    os.chmod(full_episode_path, 0o666)
    print("Copy complete!")


def find_corrected_url(show_url, info_dict):
    show_name = info_dict['series']
    if 'Dimension 20:' in show_name:
        print(f'Attempting to correct url: {show_url}')
        # Loop through seasons
        # https://watch.dropout.tv/dimension-20/season:27/videos/poppy-persona-non-grata
        # https://watch.dropout.tv/videos/poppy-persona-non-grata
        file_name_part = show_url.rsplit('/', 1)[-1]
        for i in range(1, 100):
            url_to_try = f'https://watch.dropout.tv/dimension-20/season:{i}/videos/{file_name_part}'
            try:
                print(f'Trying url: {url_to_try}')
                r = requests.head(url_to_try)
                if r.status_code == 404:
                    continue

                print(f'Found corrected url: {url_to_try}')
                new_info_dict = get_metadata(url_to_try)
                return url_to_try, new_info_dict
            except Exception as e:
                pass
    return None, None


def process_urls(url_list, desired_destination):
    print('********** Processing Urls: **********')
    if len(url_list) > 0:
        for url in url_list:
            print(url)

        for url in url_list:
            process_url(url, desired_destination)
    else:
        print("No initial Urls provided.")


def process_url(
    show_url: str,
    desired_destination,
    progress_callback: ProgressCallback | None = None,
    processor=None,
) -> None:
    info_dict = get_metadata(show_url)

    corrected_url, corrected_info_dict = find_corrected_url(show_url, info_dict)
    if corrected_url and corrected_info_dict:
        show_url = corrected_url
        info_dict = corrected_info_dict

    if processor:
        processor.process_info_dict(info_dict)

    show_path = download_show(show_url, info_dict, progress_callback, processor)

    copy_to_destination(info_dict, show_path, str(desired_destination), processor)

    # Trigger Sonarr rescan (optional)
    try:
        show_name = info_dict.get('series')
        if show_name:
            should_trigger_rename = False
            if processor:
                override_name = processor.process_show_name(show_name)
                should_trigger_rename = processor.should_trigger_rename(info_dict)
            refresh_and_rescan_series(show_name, override_name, should_trigger_rename)
    except Exception as e:
        print(f"Sonarr integration warning: {e}")

    if DO_CLEANUP:
        if os.path.exists(show_path):
            os.remove(show_path)
