import queue
import threading
import time

from datetime import datetime
from typing import Any

download_queue: queue.Queue = queue.Queue()
download_status: dict[str, Any] = {}
download_history: list[dict] = []
thread_lock = threading.Lock()


def generate_job_id() -> str:
    return f"{int(time.time())}_{len(download_status)}"


def create_job_status(job_id: str, url: str) -> dict[str, Any]:
    return {
        'id': job_id,
        'url': url,
        'status': 'queued',
        'queued_at': datetime.now().isoformat(),
        'progress': 0,
        'step': 0,
        'step_type': '',
        'total_steps': 0,
    }


def queue_url(url: str) -> str:
    for job_status in download_status.values():
        if url == job_status.get('url', '') and job_status.get('status', '') != 'failed':
            return ''

    job_id = generate_job_id()
    job_status = create_job_status(job_id, url)

    with thread_lock:
        download_status[job_id] = job_status.copy()

    download_queue.put({'id': job_id, 'url': url})
    return job_id
