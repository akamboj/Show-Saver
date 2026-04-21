from processors import dropout

from flask import Blueprint, jsonify, request

bp = Blueprint('dropout', __name__, url_prefix='/dropout')


@bp.route('/new-releases', methods=['GET'])
def new_releases():
    force_refresh = request.args.get('refresh', '').lower() == 'true'
    result = dropout.get_new_releases(force_refresh=force_refresh)

    if result['success']:
        return jsonify({
            'success': True,
            'videos': result['videos'],
            'count': len(result['videos']),
            'cached': result.get('cached', False),
        })
    return jsonify({
        'success': False,
        'message': result.get('error', 'Failed to fetch new releases'),
        'videos': [],
    }), 503


@bp.route('/info', methods=['GET'])
def episode_info():
    episode_url = request.args.get('episode', '')
    result = dropout.get_epsiode_info(episode_url)

    if result['success']:
        return jsonify({'success': True, 'info': result['info']})
    if result.get('error') == 'not_yet_fetched':
        return jsonify({'success': False, 'message': result.get('error'), 'info': None}), 200
    return jsonify({
        'success': False,
        'message': result.get('error', 'Failed to fetch episode info'),
        'info': None,
    }), 503
