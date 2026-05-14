"""
Celery tasks package for SF-PM Agent.

This package contains all async tasks executed by the Celery worker.
"""

# Lazy imports to avoid conflicts between Celery worker and pytest contexts
# Tasks can be imported directly: from src.agent.tasks.file_validation import ...
try:
    from .file_validation import health_check, validate_file
    from .geometry_processing import generate_low_poly_glb
    __all__ = ['health_check', 'validate_file', 'generate_low_poly_glb']
except ImportError:
    # In test context, import directly from modules instead
    __all__ = []
