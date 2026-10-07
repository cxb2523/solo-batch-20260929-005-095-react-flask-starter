import re
import threading
from unittest import mock

import pytest
from celery.exceptions import Reject
from flask import Flask
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src.models import Counter, db
from src.routes import counter as counter_routes
from src.tasks import make_celery


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / 'test.db'
    flask_app = Flask(__name__)
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path.as_posix()}'
    flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False, 'timeout': 30}
    }
    flask_app.config['CELERY_BROKER_URL'] = 'memory://'
    flask_app.config['CELERY_RESULT_BACKEND'] = 'cache+memory://'
    flask_app.config['COUNTER_TASK_TIMEOUT'] = 2.0
    flask_app.config['CELERY_CONFIG'] = {
        'task_always_eager': True,
        'task_eager_propagates': True
    }
    flask_app.register_blueprint(counter_routes)

    celery = make_celery(flask_app)
    db.init_app(flask_app)

    with flask_app.app_context():
        db.create_all()
        Counter.get_or_create('Test')

    flask_app.celery = celery
    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def increment_task(app):
    return app.celery.tasks['src.tasks.ping_once']


def _ping(test_client, results, barrier):
    barrier.wait()
    response = test_client.get('/api/v1/')
    results.append((response.status_code, response.get_json()))


def test_concurrent_pings_match_successful_responses(client):
    request_count = 20
    results = []
    barrier = threading.Barrier(request_count)
    threads = [
        threading.Thread(target=_ping, args=(client, results, barrier))
        for _ in range(request_count)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with client.application.app_context():
        final_count = Counter.snapshot('Test')

    statuses = [result[0] for result in results]
    success_count = sum(status == 200 for status in statuses)
    assert len(results) == request_count
    assert success_count == request_count, results
    assert final_count == success_count


def test_worker_redelivery_after_commit_does_not_duplicate(app, increment_task):
    with app.app_context():
        increment_task.apply(args=(1,), kwargs={'label': 'Test'}, task_id='redelivered')
        assert Counter.snapshot('Test') == 1

        increment_task.apply(args=(1,), kwargs={'label': 'Test'}, task_id='redelivered')
        assert Counter.snapshot('Test') == 1


def test_worker_redelivery_after_failed_commit_does_not_duplicate(app, increment_task):
    real_commit = db.session.commit
    attempts = {'count': 0}

    def flaky_commit():
        attempts['count'] += 1
        if attempts['count'] == 1:
            raise OperationalError('INSERT', {}, Exception('connection reset'))
        return real_commit()

    with app.app_context():
        wrapped_run = increment_task.run
        increment_task.run = increment_task._orig_run
        with mock.patch.object(db.session, 'commit', side_effect=flaky_commit):
            try:
                increment_task.apply(
                    args=(1,),
                    kwargs={'label': 'Test'},
                    task_id='crash-retry',
                    throw=True
                )
            except OperationalError:
                pass
            assert attempts['count'] == 1
            assert Counter.snapshot('Test') == 0

            increment_task.run = wrapped_run
            increment_task.apply(args=(1,), kwargs={'label': 'Test'}, task_id='crash-retry')
            assert Counter.snapshot('Test') == 1


def test_refresh_response_matches_committed_snapshot(client):
    first = client.get('/api/v1/')
    second = client.get('/api/v1/')
    assert first.status_code == 200, first.get_json()
    assert second.status_code == 200, second.get_json()

    first_count = int(re.search(r'Pinged (\d+)', first.get_json()['response']).group(1))
    second_count = int(re.search(r'Pinged (\d+)', second.get_json()['response']).group(1))

    with client.application.app_context():
        committed_count = Counter.snapshot('Test')

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_count == 1
    assert second_count == committed_count == 2


def test_route_enqueue_failure_does_not_report_success(app, client):
    task = app.celery.tasks['src.tasks.ping_once']

    with mock.patch.object(task, 'apply_async', side_effect=Reject('broker unavailable')):
        response = client.get('/api/v1/')

    with app.app_context():
        committed_count = Counter.snapshot('Test')

    assert response.status_code == 503
    assert committed_count == 0


def test_worker_retries_are_bounded_with_exponential_backoff(app, increment_task):
    assert increment_task.max_retries == 5
    assert increment_task.autoretry_for == (SQLAlchemyError,)
    assert increment_task.retry_backoff == 1
    assert increment_task.retry_backoff_max == 60
