"""
Celery client singleton for the backend.

This module provides a Celery client for sending tasks to the agent worker.
The backend does NOT run tasks — it only sends them via send_task().
"""

from celery import Celery
from typing import Optional

# Import backend config to get properly constructed Redis URLs with password
try:
    from config import settings
except ModuleNotFoundError:
    # Fallback for tests or when backend is not in path
    from config import settings


_celery_client: Optional[Celery] = None


def get_celery_client() -> Celery:
    """
    Get or create a singleton Celery client for sending tasks.

    Returns:
        Celery: Configured Celery client
    """
    global _celery_client

    if _celery_client is None:
        _celery_client = Celery(
            "sf-pm-backend",
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND,
        )
        _celery_client.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
        )

    return _celery_client
