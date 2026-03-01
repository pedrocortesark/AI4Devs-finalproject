from celery import Celery
from config import settings

_celery: Celery | None = None


def get_celery_client() -> Celery:
    global _celery
    if _celery is None:
        _celery = Celery(
            "sfpm",
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND,
        )
    return _celery
