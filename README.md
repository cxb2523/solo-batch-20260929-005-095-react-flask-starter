# The React + Flask Template &middot; [![Version Badge](https://img.shields.io/badge/version-1.0.0-brightgreen)](#)

A React starter project with Flask backend that works with [Docker](https://www.docker.com), [Docker Compose](https://docs.docker.com/compose),
and [Shipyard](https://shipyard.build) out of the box.

## Includes

- [React](https://github.com/facebook/react) - JavaScript library for building user interfaces
- [Material-UI](https://github.com/mui-org/material-ui) - React components for faster and simpler web development
- [Flask](https://github.com/pallets/flask) - lightweight WSGI web application framework
- [Jinja](https://github.com/pallets/jinja) + [Bootstrap](https://pythonhosted.org/Flask-Bootstrap) (from CDN)
- [uWSGI](https://github.com/unbit/uwsgi) - entrypoint
- [Celery](https://github.com/celery/celery) (with example heartbeat task configured) - distributed task queue
- [Flask-SQLAlchemy](https://github.com/pallets/flask-sqlalchemy) - ORM toolkit
- [LocalStack](https://github.com/localstack/localstack) - fully functional local AWS cloud stack

## Counter consistency

The counter uses Celery as the only write path: `backend/src/routes/counter.py` reads the committed
counter snapshot and enqueues `src.tasks.ping_once`, while `backend/src/tasks.py` executes the
database update through `backend/src/models/counter.py`. The HTTP JSON shape and URL are unchanged.

**Chosen approach:** persist the Celery task id as an idempotency key. The counter update and
insertion into `counter_event` happen in one database transaction, and `(task_id, counter_id)` has
a unique constraint. A redelivered task after a worker crash is recognized by the same task id and
does not add another increment.

**Rejected approach:** database row locks plus an atomic increment. This serializes all writes to
the single demo counter and turns increment SQL plus event bookkeeping into a hot-row bottleneck.
It fails first under burst traffic concentrated on one counter: lock waits and queue depth grow,
tail latency approaches the transaction timeout, and timeouts cause retries. More importantly, a
crash after commit but before the broker ack still looks like a new delivery, so a lock alone does
not make retries idempotent.

**Failure semantics:** worker failures use asynchronous Celery retry, not a second synchronous write
from the route. Tasks retry at most 5 times after the initial attempt, with exponential backoff
starting at 1 second and capped at 60 seconds. The route waits briefly for the task transaction;
if enqueue or bounded completion fails it returns HTTP 503 and leaves the count unchanged for that
request, so a successful response always matches a committed database snapshot after refresh.

Web and worker use the same `DATABASE_URL` and `REDIS_URL` Compose environment anchor, so the queue,
result store, and durable counter state are shared. LocalStack endpoints remain independent S3
operations and expose their committed snapshot on the existing files API; they are not mixed with
the counter database transaction.

## Dependencies

- [Docker](https://www.docker.com) & [Docker Compose](https://docs.docker.com/compose) - to build and run the app
- [Make](https://www.gnu.org/software/make/manual/make.html) - to easily run commands needed for development

## Getting Started

- Run `make develop` at the root of this project.
- Visit the app at http://localhost:3000.
- Visit http://localhost:8080/api/v1/files to list objects in LocalStack s3 bucket.
- Make your code changes! The app will reload whenever you save.
