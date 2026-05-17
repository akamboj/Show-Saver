import tracemalloc

from flask import jsonify, request
from flask_smorest import Blueprint

bp = Blueprint('debug', __name__, url_prefix='/debug', description='Debug-only diagnostics')

_baseline: dict = {'snapshot': None}


@bp.route('/memory', methods=['GET'])
def memory():
    action = request.args.get('action', 'diff')
    limit = int(request.args.get('limit', '25'))

    if not tracemalloc.is_tracing():
        return jsonify({'error': 'tracemalloc not started (set IS_DEBUG=true and ENABLE_MEMORY_PROFILING=true)'}), 400

    snapshot = tracemalloc.take_snapshot().filter_traces((
        tracemalloc.Filter(False, tracemalloc.__file__),
        tracemalloc.Filter(False, '<frozen importlib._bootstrap>'),
        tracemalloc.Filter(False, '<frozen importlib._bootstrap_external>'),
    ))

    if action == 'baseline' or _baseline['snapshot'] is None:
        _baseline['snapshot'] = snapshot
        current, peak = tracemalloc.get_traced_memory()
        return jsonify({
            'action': 'baseline_set',
            'traced_current_bytes': current,
            'traced_peak_bytes': peak,
        })

    diff = snapshot.compare_to(_baseline['snapshot'], 'lineno')
    top = []
    for stat in diff[:limit]:
        frame = stat.traceback[0]
        top.append({
            'file': frame.filename,
            'line': frame.lineno,
            'size_diff_bytes': stat.size_diff,
            'count_diff': stat.count_diff,
            'size_bytes': stat.size,
            'count': stat.count,
        })
    current, peak = tracemalloc.get_traced_memory()
    return jsonify({
        'action': 'diff',
        'traced_current_bytes': current,
        'traced_peak_bytes': peak,
        'top_allocators_by_size_diff': top,
    })
