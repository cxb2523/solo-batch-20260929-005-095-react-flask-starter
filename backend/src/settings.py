import os


class Parse:
    """Class of utility functions to parse environment variables"""

    @staticmethod
    def bool(field):
        """Parse booleans (defaults to False)"""
        return os.getenv(field, '').lower() in ['true', '1']


class Settings:

    # General
    DEV = Parse.bool('DEV')
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_URL = os.getenv('REDIS_URL', f'redis://{REDIS_HOST}:6379')

    # Database
    AES_SECRET_KEY = os.getenv('AES_SECRET_KEY', 'fake-aes-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    COUNTER_TASK_TIMEOUT = float(os.getenv('COUNTER_TASK_TIMEOUT', '2.0'))

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_CONFIG = {
        'task_acks_late': True,
        'task_reject_on_worker_lost': True
    }
