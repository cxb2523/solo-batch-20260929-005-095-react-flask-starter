from celery import Celery
from sqlalchemy.exc import SQLAlchemyError

from src.models import Counter
from src.settings import Settings as S


def make_celery(app):
    # Create and configure the celery app
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config.get('CELERY_CONFIG', S.CELERY_CONFIG))

    # Subclass the base Task so that tasks run in a Flask app context
    TaskBase = celery.Task
    class ContextTask(TaskBase):  # noqa
        abstract = True

        def __call__(self, *args, **kwargs):  # noqa
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask

    bind_tasks(celery)

    return celery


class Tasks:
    ping_once = None


def bind_tasks(celery):
    @celery.task(
        bind=True,
        name='src.tasks.ping_once',
        autoretry_for=(SQLAlchemyError,),
        retry_backoff=1,
        retry_backoff_max=60,
        retry_jitter=False,
        max_retries=5
    )
    def ping_once(task, amount, label=None):
        Counter.apply_task_increment(
            task_id=task.request.id,
            amount=amount,
            label=label
        )
        return None

    Tasks.ping_once = ping_once
