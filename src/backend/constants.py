"""
Application constants for the Sagrada Familia Parts Manager.

This module centralizes all hardcoded values used across the backend
to improve maintainability and avoid magic strings.
"""

# ===== Storage Configuration =====
STORAGE_BUCKET_RAW_UPLOADS = "raw-uploads"
STORAGE_BUCKET_PROCESSED = "processed-geometry"
STORAGE_PATH_PREFIX_MODELS = "models"  # NEW (T-1502-INFRA): Hierarchical prefix for organized storage
STORAGE_PATH_SUBDIR_LOW_POLY = "low-poly"  # NEW (T-1502-INFRA): Subdirectory for low-poly GLB files

# ===== Event Types =====
EVENT_TYPE_UPLOAD_CONFIRMED = "upload.confirmed"
EVENT_TYPE_PROCESSING_STARTED = "processing.started"
EVENT_TYPE_PROCESSING_COMPLETED = "processing.completed"
EVENT_TYPE_PROCESSING_FAILED = "processing.failed"
EVENT_TYPE_VALIDATION_PASSED = "validation.passed"
EVENT_TYPE_VALIDATION_FAILED = "validation.failed"

# ===== Database Tables =====
TABLE_EVENTS = "events"
TABLE_FILES = "files"
TABLE_PARTS = "parts"
TABLE_BLOCKS = "blocks"

# ===== File Validation =====
ALLOWED_EXTENSION = ".3dm"
MAX_FILE_SIZE_MB = 500
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 500MB converted to bytes for Pydantic validation

# ===== Upload Configuration =====
STORAGE_UPLOAD_PATH_PREFIX = "uploads"
PRESIGNED_URL_EXPIRATION_SECONDS = 300  # 5 minutes

# ===== Celery Task Names =====
TASK_VALIDATE_FILE = "agent.tasks.validate_file"
TASK_REGISTER_3DM_BLOCKS = "agent.tasks.register_3dm_blocks"

# ===== Block Defaults =====
BLOCK_TIPOLOGIA_PENDING = "pending"
BLOCK_ISO_CODE_PREFIX = "PENDING"

# ===== Parts Listing Query Fields =====
PARTS_LIST_SELECT_FIELDS = "id, iso_code, status, tipologia, low_poly_url, bbox"
QUERY_FIELD_IS_ARCHIVED = "is_archived"
QUERY_FIELD_CREATED_AT = "created_at"
QUERY_ORDER_DESC = True

# ===== Element API Query Fields (T-1504-BACK + US-015 LOD) =====
ELEMENTS_LIST_SELECT_FIELDS = "id, iso_code, status, material_type, high_poly_url, mid_poly_url, low_poly_url, bbox"
ELEMENT_DETAIL_SELECT_FIELDS = ("id, iso_code, status, material_type, created_at, updated_at, "
                                 "high_poly_url, mid_poly_url, low_poly_url, bbox, validation_report, rhino_metadata")

# ===== Validation Error Messages =====
ERROR_MSG_INVALID_STATUS = "Invalid status value. Must be one of: {valid_values}"
ERROR_MSG_INVALID_UUID = "Invalid workshop_id format. Must be a valid UUID."
ERROR_MSG_FETCH_PARTS_FAILED = "Failed to fetch parts: {error}"
ERROR_MSG_ELEMENT_NOT_FOUND = "Element not found"
ERROR_MSG_INVALID_UUID_FORMAT = "Invalid UUID format"
ERROR_MSG_DATABASE_ERROR = "Database error: {error}"
ERROR_MSG_FETCH_ELEMENTS_FAILED = "Failed to fetch elements: {error}"
