import os
import requests
import shutil
import yt_dlp
from env import (
    CONFIG_DIR, TMP_DIR, DO_CLEANUP
)
from sonarr import refresh_and_rescan_series

SHOW_NAME_OVERRIDES = {
    'Very Important People' : 'Very Important People (2023)'
}


def progress_hook(d):
    print(d['_default_template'])


BASE_YT_OPTS = {
    #'verbose' : True,
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
        'skip_download' : True
    }
    yt = yt_dlp.YoutubeDL(dlp_opts)

    print('Downloading metadata for url: ' + show_url)
    info_dict = yt.extract_info(show_url)
    print('\nMetadata download complete!')
    return info_dict


def download_show(show_url, info_dict, progress_callback=None):
    download_state = {'current_step': 0, 'steps': [], 'last_filename': None}

    def progress_hook_callback(download_progress):
        print(download_progress['_default_template'])
        if progress_callback and download_progress['status'] == 'downloading':
            # Detect stream type from info_dict
            info = download_progress.get('info_dict', {})
            vcodec = info.get('vcodec', 'none')
            acodec = info.get('acodec', 'none')
            filename = download_progress.get('filename', '')

            # Determine stream type
            if vcodec != 'none' and acodec == 'none':
                stream_type = 'video'
            elif acodec != 'none' and vcodec == 'none':
                stream_type = 'audio'
            else:
                stream_type = 'video+audio'  # Combined or unknown

            # Detect new step (filename changes)
            if filename != download_state['last_filename']:
                download_state['last_filename'] = filename
                if stream_type not in download_state['steps']:
                    download_state['steps'].append(stream_type)
                    download_state['current_step'] = len(download_state['steps'])

            # Calculate progress
            total = download_progress.get('total_bytes') or download_progress.get('total_bytes_estimate')
            percent = 0
            if total:
                percent = (download_progress.get('downloaded_bytes', 0) / total) * 100

            # Report progress with step info
            progress_callback({
                'percent': percent,
                'step': download_state['current_step'],
                'step_type': stream_type,
                'total_steps': max(len(download_state['steps']), download_state['current_step'])
            })

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
            }
        ],
        'writesubtitles' : True,
        'progress_hooks' : [progress_hook_callback]
    }
    yt = yt_dlp.YoutubeDL(dlp_opts)

    yt.download(show_url)
    show_file_name = yt.evaluate_outtmpl(dlp_opts['outtmpl']['default'], info_dict)
    show_path = os.path.abspath(os.path.join(dlp_opts['paths']['home'], show_file_name))
    return show_path


def copy_to_destination(info_dict, show_path, base_destination_path):
    show_name = info_dict['series']
    season_number = info_dict['season_number']
    season_folder = 'Season ' + str(season_number)
    episode_filename = os.path.basename(show_path)

    if show_name in SHOW_NAME_OVERRIDES:
        episode_filename = episode_filename.replace(show_name, SHOW_NAME_OVERRIDES[show_name])
        show_name = SHOW_NAME_OVERRIDES[show_name]

    full_destination_path = os.path.join(base_destination_path, show_name, season_folder)
    full_episode_path = os.path.join(full_destination_path, episode_filename)

    print("Starting copy to: " + full_destination_path)
    os.makedirs(full_destination_path, exist_ok=True)

    shutil.copy2(show_path, full_episode_path)
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


def process_url(show_url, desired_destination, progress_callback=None):
    info_dict = get_metadata(show_url)

    corrected_url, corrected_info_dict = find_corrected_url(show_url, info_dict)
    if corrected_url and corrected_info_dict:
        show_url = corrected_url
        info_dict = corrected_info_dict

    show_path = download_show(show_url, info_dict, progress_callback)

    copy_to_destination(info_dict, show_path, str(desired_destination))

    # Trigger Sonarr rescan (optional, non-blocking)
    try:
        show_name = info_dict.get('series')
        if show_name:
            refresh_and_rescan_series(show_name, SHOW_NAME_OVERRIDES)
    except Exception as e:
        print(f"Sonarr integration warning: {e}")

    if DO_CLEANUP:
        if os.path.exists(show_path):
            os.remove(show_path)