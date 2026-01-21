import downloader

import os
import queue
import threading
import time
import yt_dlp
from datetime import datetime
from env import (
    CONFIG_DIR, SHOW_DIR, DEBUG, FLASK_PORT, URL
)
from flask import Flask, jsonify, request, render_template

# Enable remote debugging when debugging is enabled
if DEBUG:
    import debugpy
    debugpy.listen(('0.0.0.0', 5678))
    print('Debugpy listening on port 5678. Waiting for debugger to attach...')
    debugpy.wait_for_client()
    print('Debugger attached!')

URL_LIST_FILE_PATH = os.path.join(CONFIG_DIR, 'urls.txt')

app = Flask(__name__)

# Download queue and status tracking
download_queue = queue.Queue()
download_status = {}
download_history = []
thread_lock = threading.Lock()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    url = data.get('text', '').strip()

    # Validate URL
    if not url:
        return jsonify({
            'success': False,
            'message': 'URL cannot be empty'
        }), 400

    job_id = queue_url(url)

    # Get queue position
    queue_position = download_queue.qsize()

    response = {
        'success': True,
        'message': 'URL queued for download',
        'job_id': job_id,
        'url': url,
        'queue_position': queue_position,
        'status': 'queued'
    }

    return jsonify(response)


@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    with thread_lock:
        if job_id in download_status:
            return jsonify({
                'success': True,
                'status': download_status[job_id]
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Job not found'
            }), 404


@app.route('/queue', methods=['GET'])
def get_queue():
    with thread_lock:
        queued = [v for v in download_status.values() if v['status'] == 'queued']
        downloading = [v for v in download_status.values() if v['status'] == 'downloading']
        completed = download_history[-10:] if download_history else []

        return jsonify({
            'success': True,
            'queued': queued,
            'downloading': downloading,
            'completed': completed,
            'queue_size': len(queued)
        })


def download_worker():
    # Background worker that processes download queue
    print('Download thread started.')
    while True:
        try:
            item = download_queue.get(timeout=1)
            if item is None:
                break

            url = item['url']
            job_id = item['id']

            # Update status to downloading
            with thread_lock:
                download_status[job_id]['status'] = 'downloading'
                download_status[job_id]['started_at'] = datetime.now().isoformat()

            try:
                def update_progress(progress_info):
                    with thread_lock:
                        download_status[job_id]['progress'] = int(progress_info['percent'])
                        download_status[job_id]['step'] = progress_info.get('step', 1)
                        download_status[job_id]['step_type'] = progress_info.get('step_type', 'downloading')
                        download_status[job_id]['total_steps'] = progress_info.get('total_steps', 1)

                downloader.process_url(url, SHOW_DIR, progress_callback=update_progress)

                file_path = ''
                file_size = 0

                # Mark as completed
                with thread_lock:
                    download_status[job_id]['status'] = 'completed'
                    download_status[job_id]['completed_at'] = datetime.now().isoformat()
                    download_status[job_id]['file_path'] = file_path
                    download_status[job_id]['size'] = file_size
                    download_history.append(download_status[job_id].copy())

            except Exception as e:
                # Mark as failed
                with thread_lock:
                    download_status[job_id]['status'] = 'failed'
                    download_status[job_id]['error'] = str(e)
                    download_status[job_id]['completed_at'] = datetime.now().isoformat()

            download_queue.task_done()

        except queue.Empty:
            continue


def generate_job_id():
    return f"{int(time.time())}_{len(download_status)}"


def create_job_status(job_id, url):
    job_status = {
        'id': job_id,
        'url': url,
        'status': 'queued',
        'queued_at': datetime.now().isoformat(),
        'progress': 0,
        'step': 0,
        'step_type': '',
        'total_steps': 0
    }
    return job_status


def queue_url(url):
    # Generate job ID
    job_id = generate_job_id()
    # Add to queue
    job_status = create_job_status(job_id, url)

    with thread_lock:
        download_status[job_id] = job_status.copy()

    download_queue.put({'id': job_id, 'url': url})
    return job_id


def get_urls_to_process():
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
        create_config_files()

        print("yt-dlp version: " + yt_dlp.version.__version__)

        urls_to_process = get_urls_to_process()
        for url in urls_to_process:
            queue_url(url)

        download_thread = threading.Thread(target=download_worker, daemon=True)
        download_thread.start()
    except Exception as e:
        print(f"Initialization error: {e}")
        import traceback
        traceback.print_exc()
        raise


_initialize()


def main():
    app.run(debug=DEBUG, host='0.0.0.0', port=FLASK_PORT)


if __name__ == "__main__":
    main()
