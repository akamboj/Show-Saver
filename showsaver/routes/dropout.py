from flask_smorest import Blueprint, abort

from showsaver.processors import dropout
from showsaver.schemas import (
    EpisodeInfoQuerySchema, EpisodeInfoResponseSchema,
    NewReleasesQuerySchema, NewReleasesResponseSchema
)

bp = Blueprint('dropout', __name__, url_prefix='/dropout', description='Dropout metadata and releases')


@bp.route('/new-releases', methods=['GET'])
@bp.arguments(NewReleasesQuerySchema, location='query')
@bp.response(200, NewReleasesResponseSchema)
@bp.alt_response(503)
def new_releases(query_args):
    force_refresh = query_args.get('refresh', False)
    result = dropout.get_new_releases(force_refresh=force_refresh)

    if result['success']:
        return {
            'success': True,
            'videos': result['videos'],
            'count': len(result['videos']),
            'cached': result.get('cached', False),
        }
    abort(503, message=result.get('error', 'Failed to fetch new releases'))


@bp.route('/info', methods=['GET'])
@bp.arguments(EpisodeInfoQuerySchema, location='query')
@bp.response(200, EpisodeInfoResponseSchema)
@bp.alt_response(503)
def episode_info(query_args):
    episode_url = query_args.get('episode', '')
    result = dropout.get_epsiode_info(episode_url)

    if result['success']:
        return {'success': True, 'info': result['info']}
    if result.get('error') == 'not_yet_fetched':
        return {'success': False, 'message': 'not_yet_fetched', 'info': None}
    abort(503, message=result.get('error', 'Failed to fetch episode info'))
