from flask import (
    Blueprint,
    current_app,
    jsonify
)

from src.models import Counter

import datetime


blueprint = Blueprint('counter', __name__)

RESPONSE_TEMPLATE = 'Flask server running on port 8080. Pinged {count} {times}, \
most recently on {date}.'


@blueprint.route('/')
def index():
    response = 'Flask server'
    return jsonify(response=response)


@blueprint.route('/api/v1/reset/')
def reset():
    counter = Counter.get_or_create(label='Test')
    counter.reset()
    return jsonify(response=counter.count)


@blueprint.route('/api/v1/')
def api():
    Counter.get_or_create(label='Test')
    task = current_app.celery.tasks['src.tasks.ping_once']
    result = None
    try:
        result = task.apply_async(args=(1,), kwargs={'label': 'Test'})
        result.get(
            timeout=current_app.config['COUNTER_TASK_TIMEOUT'],
            interval=0.05,
            propagate=True,
            disable_sync_subtasks=False
        )
    except Exception:
        return jsonify(response='Counter service temporarily unavailable'), 503
    finally:
        if result is not None:
            result.forget()

    count = Counter.snapshot('Test')
    date = datetime.datetime.now()
    dateStr = date.strftime('%c')
    times = 'time' if count == 1 else 'times'
    response = RESPONSE_TEMPLATE.format(
        count=count,
        times=times,
        date=dateStr)
    return jsonify(response=response)
