"""
Celery application configuration for SF-PM Agent.

This module initializes the Celery application instance with secure
configurations for distributed task processing.
"""

import os
from celery import Celery


# RAILWAY FIX: Remove template env vars that Celery can't parse.
# Railway injects CELERY_BROKER_URL=${REDIS_PASSWORD} which takes precedence
# over constructor parameters. Delete them so config.py settings are used.
if 'CELERY_BROKER_URL' in os.environ and '${' in os.environ['CELERY_BROKER_URL']:
    del os.environ['CELERY_BROKER_URL']
if 'CELERY_RESULT_BACKEND' in os.environ and '${' in os.environ['CELERY_RESULT_BACKEND']:
    del os.environ['CELERY_RESULT_BACKEND']


# Conditional import: support both direct execution and module import
try:
    from config import settings  # When executed as worker from /app
except ModuleNotFoundError:
    from src.agent.config import settings  # When imported as module in tests

# Import constants - check for agent-specific constants to avoid backend/constants.py collision
try:
    import constants
    # Verify this is agent constants by checking for agent-specific attribute
    if hasattr(constants, 'CELERY_APP_NAME'):
        from constants import (
            CELERY_APP_NAME,
            TASK_TIME_LIMIT_SECONDS,
            TASK_SOFT_TIME_LIMIT_SECONDS,
            WORKER_PREFETCH_MULTIPLIER,
            RESULT_EXPIRES_SECONDS,
        )
    else:
        # Backend constants loaded, fallback to full path
        raise ImportError("Wrong constants module")
except (ImportError, ModuleNotFoundError):
    # Use full module path when imported as module in tests or when wrong constants found
    from src.agent.constants import (
        CELERY_APP_NAME,
        TASK_TIME_LIMIT_SECONDS,
        TASK_SOFT_TIME_LIMIT_SECONDS,
        WORKER_PREFETCH_MULTIPLIER,
        RESULT_EXPIRES_SECONDS,
    )

# Initialize Celery application
celery_app = Celery(
    CELERY_APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Do NOT use include=[] - causes circular import
    # Tasks will be imported explicitly after app initialization
)

# Configuration
celery_app.conf.update(
    # Serialization (Security: no pickle to prevent code injection)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task tracking
    task_track_started=True,

    # Timeouts (protection against OOM with large .3dm files)
    task_time_limit=TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT_SECONDS,

    # Worker behavior
    worker_prefetch_multiplier=WORKER_PREFETCH_MULTIPLIER,

    # Result expiration
    result_expires=RESULT_EXPIRES_SECONDS,

    # Task acknowledgment
    task_acks_late=True,  # Acknowledge after task completion

    # Celery 6.0 compatibility
    broker_connection_retry_on_startup=True,
)

# Import tasks AFTER celery_app is fully initialized to avoid circular imports
# This registers the @celery_app.task decorated functions with the Celery instance
try:
    from tasks import file_validation, geometry_processing  # noqa: F401
except ImportError:
    # In test/dev context with full module paths
    from src.agent.tasks import file_validation, geometry_processing  # noqa: F401
