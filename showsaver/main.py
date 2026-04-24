import database
import downloader

import logging
import os
import queue
import threading
import time
import yt_dlp
import yt_dlp.version

from datetime import datetime
from flask import Flask
from flask_smorest import Api

from env import (
    CONFIG_DIR, SHOW_DIR, DEBUG, WAIT_FOR_DEBUGGER, FLASK_PORT, URL
)
from processors import dropout
from routes.downloads import bp as downloads_bp
from routes.dropout import bp as dropout_bp
from routes.views import bp as views_bp
from sonarr import is_sonarr_enabled
from state import (
    download_queue, download_status, download_history, thread_lock, queue_url,
    metadata_queue, metadata_in_flight
)
from version import __version__

# Enable remote debugging when debugging is enabled
if DEBUG:
    import debugpy
    debugpy.configure(subProcess=False)  # Disable subprocess debugging for Docker
    try:
        debugpy.listen(('0.0.0.0', 5678))
        print('Debugpy listening on port 5678.')
    except RuntimeError:
        pass
    if WAIT_FOR_DEBUGGER:
        print('Waiting for debugger to attach...')
        debugpy.wait_for_client()
        print('Debugger attached!')

URL_LIST_FILE_PATH = os.path.join(CONFIG_DIR, 'urls.txt')

app = Flask(__name__)
app.config['API_TITLE'] = 'Show-Saver API'
app.config['API_VERSION'] = __version__
app.config['OPENAPI_VERSION'] = '3.0.3'
app.config['OPENAPI_URL_PREFIX'] = '/docs'
app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.32.4/'


@app.context_processor
def inject_version():
    return {'version': __version__}


app.register_blueprint(views_bp)

api = Api(app)
api.register_blueprint(downloads_bp)
api.register_blueprint(dropout_bp)

class _NoQueueFilter(logging.Filter):
    def filter(self, record):
        return '/queue' not in record.getMessage()

logging.getLogger('werkzeug').addFilter(_NoQueueFilter())


def download_worker() -> None:
    """Background worker that processes download queue"""
    print('Download thread started.')
    while True:
        time.sleep(2)
        try:
            item = download_queue.get(timeout=1)
            if item is None:
                break

            url = item['url']
            job_id = item['id']

            # Any updates to data here must be reflected to JobStatusSchema
            with thread_lock:
                download_status[job_id]['status'] = 'downloading'
                download_status[job_id]['started_at'] = datetime.now().isoformat()

            try:
                def update_progress(progress_info):
                    with thread_lock:
                        download_status[job_id]['progress'] = int(progress_info.get('percent', 0))
                        download_status[job_id]['step'] = progress_info.get('step', 1)
                        download_status[job_id]['step_type'] = progress_info.get('step_type', 'downloading')
                        download_status[job_id]['total_steps'] = progress_info.get('total_steps', 1)

                downloader.process_url(url, SHOW_DIR, progress_callback=update_progress, processor=dropout.DropoutProcessor())

                with thread_lock:
                    download_status[job_id]['status'] = 'completed'
                    download_status[job_id]['completed_at'] = datetime.now().isoformat()
                    download_status[job_id]['file_path'] = ''
                    download_status[job_id]['size'] = 0
                    download_history.append(download_status[job_id].copy())

            except Exception as e:
                with thread_lock:
                    download_status[job_id]['status'] = 'failed'
                    download_status[job_id]['error'] = str(e)
                    download_status[job_id]['completed_at'] = datetime.now().isoformat()

            download_queue.task_done()

        except queue.Empty:
            continue


def metadata_worker() -> None:
    """Background worker that fills in episode metadata via yt-dlp."""
    print('Metadata thread started.')
    while True:
        try:
            episode_url_data = metadata_queue.get(timeout=1)
        except queue.Empty:
            continue

        url_path = episode_url_data['url_path']
        full_url = episode_url_data['url']
        try:
            dropout.fetch_and_store_episode_info(full_url)
            print(f'Metadata fetch succeeded for {full_url}')
        except Exception as e:
            print(f'Metadata fetch failed for {full_url}: {e}')
        finally:
            if url_path is not None:
                with thread_lock:
                    metadata_in_flight.discard(url_path)
            metadata_queue.task_done()


def get_urls_to_process() -> list[str]:
    urls = []
    if URL:
        urls.append(URL)

    with open(URL_LIST_FILE_PATH, 'r') as url_list_file:
        file_urls = [line.strip() for line in url_list_file if line.strip()]
        urls.extend(file_urls)

    return urls


def create_config_files():
    netrc_path = os.path.join(CONFIG_DIR, '.netrc')
    if not os.path.exists(netrc_path):
        with open(netrc_path, 'w') as netrc_file:
            print('Created .netrc file: ' + netrc_path)

    if not os.path.exists(URL_LIST_FILE_PATH):
        with open(URL_LIST_FILE_PATH, 'w') as url_list_file:
            print('Created url text file: ' + URL_LIST_FILE_PATH)


def _initialize():
    """Initialize app - runs on module load for gunicorn compatibility."""
    try:
        database.init_db()
        create_config_files()

        print("yt-dlp version: " + yt_dlp.version.__version__)
        if is_sonarr_enabled():
            print("Sonarr integration enabled")
        else:
            print("Sonarr integration disabled")

        for url in get_urls_to_process():
            queue_url(url)

        download_thread = threading.Thread(target=download_worker, daemon=True)
        download_thread.start()
        metadata_thread = threading.Thread(target=metadata_worker, daemon=True)
        metadata_thread.start()
    except Exception as e:
        print(f"Initialization error: {e}")
        import traceback
        traceback.print_exc()
        raise


_initialize()


def main():
    app.run(debug=DEBUG, host='0.0.0.0', port=FLASK_PORT, use_reloader=False)


if __name__ == "__main__":
    main()
