from flask_smorest import Blueprint, abort

from showsaver.schemas import (
    HistoryResponseSchema,
    QueueResponseSchema, StatusResponseSchema,
    SubmitRequestSchema, SubmitResponseSchema,
)
from showsaver.state import download_history, download_status, thread_lock, queue_url

bp = Blueprint('downloads', __name__, description='Download queue operations')


@bp.route('/submit', methods=['POST'])
@bp.arguments(SubmitRequestSchema)
@bp.response(200, SubmitResponseSchema)
def submit(payload):
    url = payload['text']
    job_id = queue_url(url)
    queue_position = len([v for v in download_status.values() if v['status'] == 'queued'])

    return {
        'success': True,
        'message': 'URL queued for download',
        'job_id': job_id,
        'url': url,
        'queue_position': queue_position,
        'status': 'queued',
    }


@bp.route('/status/<job_id>', methods=['GET'])
@bp.response(200, StatusResponseSchema)
@bp.alt_response(404)
def get_status(job_id):
    with thread_lock:
        if job_id in download_status:
            return {'success': True, 'status': download_status[job_id]}
        return abort(404, message='Job not found')


@bp.route('/queue', methods=['GET'])
@bp.response(200, QueueResponseSchema)
def get_queue():
    with thread_lock:
        queued = [v for v in download_status.values() if v['status'] == 'queued']
        downloading = [v for v in download_status.values() if v['status'] == 'downloading']
        completed = download_history[-10:] if download_history else []

        return {
            'success': True,
            'queued': queued,
            'downloading': downloading,
            'completed': completed,
            'queue_size': len(queued),
            'total_queue_size': len(queued) + len(downloading),
        }


@bp.route('/history', methods=['DELETE'])
@bp.response(200, HistoryResponseSchema)
def clear_history():
    with thread_lock:
        download_history.clear()
        completed_ids = [jid for jid, s in download_status.items() if s['status'] == 'completed']
        for jid in completed_ids:
            del download_status[jid]
    return {'status': 'ok'}
