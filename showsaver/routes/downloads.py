from flask import Blueprint, jsonify, request, render_template
from state import download_history, download_status, thread_lock, queue_url
from version import __version__

bp = Blueprint('downloads', __name__)


@bp.route('/')
def home():
    return render_template('index.html', version=__version__)


@bp.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    url = data.get('text', '').strip()

    if not url:
        return jsonify({'success': False, 'message': 'URL cannot be empty'}), 400

    job_id = queue_url(url)
    queue_position = len([v for v in download_status.values() if v['status'] == 'queued'])

    return jsonify({
        'success': True,
        'message': 'URL queued for download',
        'job_id': job_id,
        'url': url,
        'queue_position': queue_position,
        'status': 'queued',
    })


@bp.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    with thread_lock:
        if job_id in download_status:
            return jsonify({'success': True, 'status': download_status[job_id]})
        return jsonify({'success': False, 'message': 'Job not found'}), 404


@bp.route('/queue', methods=['GET'])
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
            'queue_size': len(queued),
            'total_queue_size': len(queued) + len(downloading),
        })


@bp.route('/history', methods=['DELETE'])
def clear_history():
    with thread_lock:
        download_history.clear()
        completed_ids = [jid for jid, s in download_status.items() if s['status'] == 'completed']
        for jid in completed_ids:
            del download_status[jid]
    return jsonify({'status': 'ok'})
