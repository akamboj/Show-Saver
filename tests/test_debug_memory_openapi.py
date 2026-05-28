import tracemalloc

import pytest
from flask import Flask
from flask_smorest import Api

from showsaver.routes import debug
from showsaver.routes.debug import bp as debug_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(
        API_TITLE='Test API',
        API_VERSION='1.0.0',
        OPENAPI_VERSION='3.0.3',
        OPENAPI_URL_PREFIX='/docs',
    )
    api = Api(app)
    api.register_blueprint(debug_bp)
    debug._baseline['snapshot'] = None
    return app


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        yield test_client
    debug._baseline['snapshot'] = None


@pytest.fixture
def tracing():
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start(10)
    yield
    if not was_tracing and tracemalloc.is_tracing():
        tracemalloc.stop()


def test_openapi_spec_includes_debug_memory(client):
    response = client.get('/docs/openapi.json')

    assert response.status_code == 200
    spec = response.get_json()
    operation = spec['paths']['/debug/memory']['get']
    parameters = {param['name']: param for param in operation['parameters']}

    assert set(parameters) == {'action', 'limit'}
    assert parameters['action']['schema']['default'] == 'diff'
    assert parameters['limit']['schema']['default'] == 25
    assert '200' in operation['responses']
    assert '400' in operation['responses']


def test_memory_baseline_response(client, tracing):
    response = client.get('/debug/memory?action=baseline')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['action'] == 'baseline_set'
    assert isinstance(payload['traced_current_bytes'], int)
    assert isinstance(payload['traced_peak_bytes'], int)


def test_memory_diff_response_after_baseline(client, tracing):
    client.get('/debug/memory?action=baseline')

    response = client.get('/debug/memory?limit=1')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['action'] == 'diff'
    assert isinstance(payload['top_allocators_by_size_diff'], list)
    assert len(payload['top_allocators_by_size_diff']) <= 1


def test_memory_invalid_limit_returns_error(client):
    response = client.get('/debug/memory?limit=not-a-number')

    assert response.status_code == 400
    assert response.get_json() == {'error': 'limit must be an integer'}
