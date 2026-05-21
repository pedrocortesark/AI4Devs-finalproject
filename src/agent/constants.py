"""
Agent Worker Constants

Centralized configuration values for Celery worker and task execution.
Following Clean Architecture pattern (separation from config.py which handles env vars).
"""

# Celery Worker Configuration
CELERY_APP_NAME = "sf_pm_agent"

# Task Execution Timeouts
# Large .3dm files (up to 500MB) can take several minutes to parse with rhino3dm
TASK_TIME_LIMIT_SECONDS = 600  # 10 minutes hard kill
TASK_SOFT_TIME_LIMIT_SECONDS = 540  # 9 minutes warning (allows cleanup)

# Worker Behavior
WORKER_PREFETCH_MULTIPLIER = 1  # One task at a time (isolate large file processing)

# Result Storage
RESULT_EXPIRES_SECONDS = 3600  # 1 hour (results cleaned up automatically)

# Task Retry Policy (with exponential backoff: 30s → 60s → 120s → 240s → 480s)
TASK_MAX_RETRIES = 5
TASK_RETRY_DELAY_SECONDS = 30  # Base delay (exponential backoff applied in task)

# Task Names (for type safety and refactoring)
TASK_HEALTH_CHECK = "agent.tasks.health_check"
TASK_VALIDATE_FILE = "agent.tasks.validate_file"
TASK_REGISTER_3DM_BLOCKS = "agent.tasks.register_3dm_blocks"
# RAG: single-block embedding upsert. Auto-fired by validate_file after a
# successful validation so The Archivist can find newly-ingested pieces
# immediately (no manual backfill required for the demo flow).
TASK_EMBED_BLOCK = "agent.tasks.embed_block"

# Validation Patterns
# ISO-19650 nomenclature:  [PREFIX]-[ZONE/CODE]-[TYPE]-[ID]
# Examples: SF-NAV-CO-001, SFC-NAV1-A-999, AB-CD12-XY-123
# Pattern breakdown:
#   - [A-Z]{2,3}: 2-3 uppercase letters (project prefix)
#   - [A-Z0-9]{3,4}: 3-4 alphanumeric uppercase (zone/code)
#   - [A-Z]{1,2}: 1-2 uppercase letters (element type)
#   - \d{3}: exactly 3 digits (sequential ID)
ISO_19650_LAYER_NAME_PATTERN = r"^[A-Z]{2,3}-[A-Z0-9]{3,4}-[A-Z]{1,2}-\d{3}$"
ISO_19650_PATTERN_DESCRIPTION = "[PREFIX]-[ZONE]-[TYPE]-[ID] (e.g., SF-NAV-CO-001)"

# Geometry Validation
GEOMETRY_CATEGORY_NAME = "geometry"
MIN_VALID_VOLUME = 1e-6  # Minimum volume in cubic units (avoid near-zero volumes)
MAX_3DM_FILE_SIZE_MB = 500  # Maximum file size for .3dm files (prevent zip bomb DoS)
MAX_FILE_SIZE_BYTES = MAX_3DM_FILE_SIZE_MB * 1024 * 1024  # 500MB converted to bytes for Pydantic validation

# Geometry Error Messages Templates
GEOMETRY_ERROR_INVALID = "Geometry is marked as invalid by Rhino (obj.Geometry.IsValid = False)"
GEOMETRY_ERROR_NULL = "Geometry is null or missing"
GEOMETRY_ERROR_DEGENERATE_BBOX = "Bounding box is degenerate or invalid"
GEOMETRY_ERROR_ZERO_VOLUME = "Solid geometry has zero or near-zero volume (< {min_volume} cubic units)"

# ===== T-1805-AGENT: LangGraph Audit Trail Events =====

# Event types for LangGraph StateGraph node transitions
# Used in events table for granular audit trail and Grafana timeline visualization
class EventType:
    """
    Event types for LangGraph StateGraph audit trail.
    
    Used in `insert_event()` helper to categorize events in the events table.
    Enables granular tracking of validation workflow execution for debugging,
    monitoring, and Grafana timeline dashboards.
    
    Usage:
        insert_event(block_id, EventType.NODE_ENTERED, "ValidateNomenclature", state)
        insert_event(block_id, EventType.CIRCUIT_BREAKER_TRIPPED, "ClassifyTipologia", state)
    """
    NODE_ENTERED = "node_entered"           # Node execution started
    NODE_COMPLETED = "node_completed"       # Node execution finished successfully
    TRANSITION_CONDITIONAL = "transition_conditional"  # Conditional edge evaluated
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"  # LLM circuit breaker activated
    FALLBACK_ACTIVATED = "fallback_activated"  # Fallback to regex classification

# Event batch insert threshold (performance optimization)
# If >10 events accumulated, insert as single batch query
EVENT_BUFFER_THRESHOLD = 10

# State snapshot fields (lightweight, excludes heavy geometry_metadata)
# Serialized to JSONB in events.state_snapshot column
STATE_SNAPSHOT_FIELDS = [
    "overall_status",        # "validated" | "rejected" | "processing"
    "nomenclature_valid",    # bool
    "geometry_valid",        # bool
    "classification_method", # ClassificationMethod ENUM value
]

# ===== T-0502-AGENT: Geometry Processing =====

# Task Names
TASK_GENERATE_LOW_POLY_GLB = "agent.generate_low_poly_glb"

# LOD System - Multi-Level Decimation Targets (US-015)
# 3-level LOD + BBox proxy for optimal performance/quality balance
LOD_DECIMATION_TARGETS = {
    'high': None,    # High-poly: no decimation (~5000-8000 faces, <5m viewing distance)
    'mid': 2000,     # Mid-poly: moderate decimation (~1500-2000 faces, 5-20m viewing distance)
    'low': 500,      # Low-poly: aggressive decimation (~400-600 faces, 20-50m viewing distance)
}

# Legacy constant (deprecated - use LOD_DECIMATION_TARGETS['low'])
DECIMATION_TARGET_FACES = LOD_DECIMATION_TARGETS['low']  # Backward compatibility

MAX_ORIGINAL_FACES_WARNING = 100_000  # Log warning if geometry exceeds 100K faces (timeout risk)

# File Size Limits (updated for LOD system)
MAX_GLB_SIZE_KB = {
    'high': 800,   # High-poly target: ~600-800KB with Draco
    'mid': 400,    # Mid-poly target: ~300-400KB with Draco
    'low': 200,    # Low-poly target: ~150-200KB with Draco
}
MAX_3DM_DOWNLOAD_SIZE_MB = 500  # Reject .3dm files >500MB (timeout risk)

# S3/Storage Configuration
PROCESSED_GEOMETRY_BUCKET = "processed-geometry"
LOD_PREFIXES = {
    'high': 'high-poly/',
    'mid': 'mid-poly/',
    'low': 'low-poly/',
}
# MTL companion files (per-face Rhino layer colors, generated for high-poly only)
MATERIALS_PREFIX = 'materials/'
# Legacy (deprecated - use LOD_PREFIXES['low'])
LOW_POLY_PREFIX = LOD_PREFIXES['low']

RAW_UPLOADS_BUCKET = "raw-uploads"

# Temp File Paths
TEMP_DIR = "/tmp"  # Docker container temp directory

# ===== Draco Compression (via gltf-pipeline CLI — mirrors POC export_gltf_draco.py) =====
DRACO_COMPRESSION_LEVEL = 7         # 0-10 scale (POC used 10; 7 = good quality/size balance)
DRACO_QUANTIZE_POSITION_BITS = 14   # ~0.1mm precision at Sagrada Família scale (POC value)
DRACO_QUANTIZE_NORMAL_BITS = 10
DRACO_QUANTIZE_TEXCOORD_BITS = 12

# Bbox Centering Validation
BBOX_CENTROID_TOLERANCE_MM = 1.0    # Centroid must be within 1mm of origin after centering

# Error Messages
ERROR_MSG_NO_MESHES_FOUND = "No meshes found in {iso_code}"
ERROR_MSG_BLOCK_NOT_FOUND = "Block {block_id} not found in database"
ERROR_MSG_FAILED_PARSE_3DM = "Failed to parse .3dm file for {iso_code}"
ERROR_MSG_S3_DOWNLOAD_FAILED = "S3 download failed after {retries} retries"

# ===== T-1802-AGENT: LLM Classification + Circuit Breaker GLOBAL =====

# OpenAI LLM Configuration
LLM_MODEL = "gpt-4-turbo"  # GPT-4 Turbo for semantic classification
LLM_TEMPERATURE = 0.2  # Low temperature for deterministic/conservative classification
LLM_MAX_TOKENS = 500  # Sufficient for JSON response {tipologia, confidence, reasoning}
LLM_TIMEOUT_SECONDS = 10  # Hard timeout to prevent hanging
LLM_RETRY_ATTEMPTS = 3  # Tenacity retry policy: 3 attempts with exponential backoff
LLM_RETRY_WAIT_EXPONENTIAL_MULTIPLIER = 2  # Wait times: 2s, 4s, 8s
LLM_RETRY_WAIT_EXPONENTIAL_MAX = 8  # Max wait time 8 seconds

# Classification Confidence Threshold
# If LLM returns valid JSON BUT confidence < threshold → trigger fallback regex
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence score (0.0-1.0) to trust LLM classification

# Classification Prompt (Versioned)
# Version: 1.0 (2026-05-04)
# Schema: {tipologia: str, confidence: float, reasoning: str}
CLASSIFICATION_PROMPTS = {
    "v1": """You are an expert architectural classifier for Sagrada Família construction elements.

**Task:** Classify the architectural piece based on metadata extracted from a 3D model (.3dm file).

**Input Metadata:**
- Volume: {volume} m³
- Bounding Box: {bbox}
- Layers: {layers}
- Vertices Count: {vertices_count}
- ISO Code: {iso_code}

**Classification Categories (tipologia):**
1. **dovela**: Voussoir stone (trapezoidal block in arches/vaults, typically small volume <0.5 m³)
2. **capitel**: Capital (decorative top of column, complex geometry, medium volume 0.3-2 m³)
3. **columna**: Column (cylindrical/prismatic vertical support, large volume >2 m³, height >> width)
4. **clave**: Keystone (central wedge in arch, distinctive trapezoidal shape, small volume <0.3 m³)
5. **imposta**: Impost (transition element between column and arch, horizontal, medium volume 0.5-1.5 m³)
6. **other**: Unknown/ambiguous category (use this if uncertain)

**Instructions:**
- BE CONSERVATIVE: If you are uncertain or the metadata is ambiguous, classify as "other" with low confidence.
- DO NOT invent details not present in the metadata.
- Provide confidence score (0.0-1.0): 0.0-0.5 = uncertain, 0.5-0.7 = moderate, 0.7-1.0 = high confidence.
- Provide brief reasoning (max 100 characters) explaining your classification.

**Output Format (JSON only, no markdown):**
{{
  "tipologia": "dovela",
  "confidence": 0.85,
  "reasoning": "Small trapezoidal volume typical of voussoir stones"
}}

Classify now:"""
}

# Prompt version selector (allows A/B testing or rollback)
CLASSIFICATION_PROMPT_VERSION = "v1"

# Prompt Injection Prevention - Forbidden Patterns
# Sanitize user strings (rhino_metadata, iso_code) to prevent prompt injection attacks
FORBIDDEN_PATTERNS = [
    r"ignore\s+previous\s+instructions?",
    r"you\s+are\s+now",
    r"disregard\s+(all|previous|above)",
    r"forget\s+(everything|all|previous)",
    r"new\s+instructions?:",
    r"system\s+prompt",
    r"admin\s+mode",
    r"developer\s+mode",
]
# Replacement text for detected injection patterns
PROMPT_INJECTION_REDACTED_TEXT = "[REDACTED_SECURITY]"

# Fallback Regex Classification Patterns
# Used when: (1) LLM fails, (2) Circuit Breaker trips, (3) Confidence < threshold
# Pattern -> tipologia mapping (ISO-19650 nomenclature)
FALLBACK_REGEX_PATTERNS = {
    r"SF-C\d{2}-D-\d{3}": "dovela",         # Example: SF-C12-D-001
    r"SF-C\d{2}-CA-\d{3}": "capitel",       # Example: SF-C12-CA-015
    r"SF-C\d{2}-CO-\d{3}": "columna",       # Example: SF-C12-CO-008
    r"SF-C\d{2}-CL-\d{3}": "clave",         # Example: SF-C12-CL-003
    r"SF-C\d{2}-IM-\d{3}": "imposta",       # Example: SF-C12-IM-012
}
# Default fallback if no pattern matches (catch-all, never fails)
FALLBACK_DEFAULT_TIPOLOGIA = "other"
FALLBACK_DEFAULT_CONFIDENCE = 0.3  # Low confidence indicates regex classification

# Circuit Breaker Configuration (GLOBAL scope - applies to ALL blocks)
# Key: circuit_breaker:openai:global (Redis)
# Rationale: If OpenAI API is down (HTTP 503), no point retrying for each block
CB_REDIS_KEY = "circuit_breaker:openai:global"
CB_FAILURE_THRESHOLD = 5  # Open circuit after 5 consecutive failures (any block)
CB_RECOVERY_TIMEOUT_SECONDS = 300  # 5 minutes - close circuit after this TTL (allow retry)
CB_HALF_OPEN_MAX_RETRIES = 3  # In half-open state, allow 3 retry attempts before re-opening

# Circuit Breaker Fallback (in-memory if Redis unavailable)
# Warning: In-memory CB is NOT shared across Celery workers (degraded resilience)
CB_MEMORY_FALLBACK_ENABLED = True

# ===== T-1810-INFRA: OpenAI Rate Limiting (Client-Side Token Bucket) =====

# Rate Limiter Configuration
# Prevents HTTP 429 errors during batch uploads by limiting OpenAI API request rate
# Implementation: Token bucket algorithm with Redis backend

import os

# Rate limit (requests per minute)
# Production: 5 req/min for free tier (3 RPM official + buffer)
# Can override via environment variable for different OpenAI tiers
OPENAI_RATE_LIMIT_PER_MIN = int(os.getenv("OPENAI_RATE_LIMIT_PER_MIN", "5"))

# Max concurrent LLM requests
# Prevents burst requests that could trigger rate limits
OPENAI_MAX_CONCURRENT = int(os.getenv("OPENAI_MAX_CONCURRENT", "3"))

# Token bucket size (max tokens that can accumulate)
# Default: same as rate_limit (no burst allowance)
# Set higher to allow burst processing after idle periods
OPENAI_RATE_LIMIT_BUCKET_SIZE = int(
    os.getenv("OPENAI_RATE_LIMIT_BUCKET_SIZE", str(OPENAI_RATE_LIMIT_PER_MIN))
)

# Rate limiter timeout (seconds)
# How long acquire_token() should wait before giving up and falling back
OPENAI_RATE_LIMITER_TIMEOUT = float(os.getenv("OPENAI_RATE_LIMITER_TIMEOUT", "30.0"))

# Retry policy for HTTP 429 (rate limit errors)
# Exponential backoff: 2s → 5s → 15s (3 attempts total)
# Note: This is ADDITIONAL to tenacity retry in llm_client.py
OPENAI_RETRY_BACKOFF_SECONDS = [2, 5, 15]
OPENAI_MAX_RETRIES_ON_429 = 3

# Redis keys for rate limiter
RATE_LIMITER_REDIS_KEY_PREFIX = "rate_limiter:openai"
