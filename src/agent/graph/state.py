"""
ValidationState — Shared State for the LangGraph Agent (US-018 / T-1801)

WHY THIS FILE EXISTS
====================
LangGraph works like a relay race where each runner (node) reads from, and
writes to, a shared baton (the state). Every node receives the full state as
input and returns a *partial* dictionary with only the fields it changed.
LangGraph then merges those changes back into the state automatically.

This file defines:
  1. ValidationStatus   — an enum for the overall validation outcome
  2. ClassificationMethod — how tipologia was determined (LLM or fallback)  
  3. ValidationState    — the TypedDict that holds ALL information about
                          one validation run (one .3dm file being processed)

One ValidationState instance is created when the Celery task starts and lives
until the graph reaches a terminal node (VALIDATED or REJECTED). The final
state is persisted to Supabase before the task completes.

DESIGN DECISIONS (T-1801)
=========================
- TypedDict instead of Pydantic because LangGraph requires plain Python dicts.
  LangGraph does NOT accept Pydantic models as the state container directly.
- EXACTLY 15 fields as specified in T-1801 tech spec (no more, no less).
- All fields are Optional (total=False) so nodes can be written without knowing
  what previous nodes set. Each node only fills what it knows.
- The `validation_path` list acts as a breadcrumb trail: every node appends
  its own name. This lets us reconstruct the execution path from the final state.
- ClassificationMethod ENUM prevents typos (gap analysis recommendation).

Author: AI Agent (T-1801-AGENT)
Created: 2026-05-04
"""

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ValidationStatus(str, Enum):
    """
    Overall outcome of the validation pipeline (maps to blocks.status PostgreSQL ENUM).

    Values:
        PROCESSING  — graph is currently running
        VALIDATED   — all checks passed, element is valid
        REJECTED    — at least one check failed (nomenclature or geometry)
        ERROR_PROCESSING — unexpected runtime error (not a validation failure)

    Note: we use (str, Enum) so the value serializes to a plain string in JSON.
    This matters when persisting state_snapshot to Supabase JSONB columns.
    
    Added in T-1801, refined from PoC Spike to match database schema.
    """
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR_PROCESSING = "error_processing"


class ClassificationMethod(str, Enum):
    """
    How the tipologia classification was determined.

    Values:
        LLM_GPT4        — GPT-4 Turbo answered with high confidence (>=0.7)
        FALLBACK_REGEX  — LLM failed or circuit breaker tripped; regex used
        MANUAL_OVERRIDE — Manual classification by user (future feature)

    Having this field in the state (and in the final report) is important
    for transparency: users can see whether the AI or the regex classified
    their piece, and how confident the system was.
    
    ENUM added in T-1801 per gap analysis recommendation (prevents typos).
    """
    LLM_GPT4 = "llm_gpt4"
    FALLBACK_REGEX = "fallback_regex"
    MANUAL_OVERRIDE = "manual_override"


class ValidationState(TypedDict, total=False):
    """
    Shared state for the entire LangGraph validation pipeline (T-1801).

    All nodes read from this dict and return a partial update.
    LangGraph merges the returned dict into the running state automatically.

    CRITICAL: This TypedDict has 16 fields (updated from 15 in T-1806 to include geometry_errors).
    Do NOT add or remove fields without updating the spec first.

    Fields are grouped by the node that primarily writes to them:

    ── Set at task start (before graph runs) ──────────────────────────────
    block_id        : str           UUID of the blocks row in Supabase
    created_at      : str           ISO-8601 timestamp when the run started
    retry_count     : int           Celery task retry counter (0 on first attempt)

    ── Written by ValidateNomenclature (US-002 reused) ────────────────────
    nomenclature_valid  : bool      True if all layer names pass ISO-19650
    nomenclature_errors : List[str] Human-readable error messages

    ── Written by ExtractGeometry + ValidateGeometry ──────────────────────
    geometry_metadata: Dict[str, Any]  
        Structure: {
            "volume": float,           # m³
            "bbox": {                   # Bounding box
                "min": [x, y, z],
                "max": [x, y, z],
                "dimensions": [w, h, d]
            },
            "vertices_count": int,
            "faces_count": int,
            "layers": List[str],
            "has_mesh": bool,
            "file_exists_in_storage": bool  # Added per T-1801 requirement
        }
    
    geometry_valid  : bool          True if geometry passes validation

    ── Written by ClassifyTipologia (LLM or fallback) ─────────────────────
    semantic_data: Dict[str, Any]
        Structure: {
            "tipologia": str,           # "dovela"|"capitel"|"columna"|"clave"|"imposta"|"other"
            "material": str,            # Inferred from tipologia (e.g., "Montjuïc Stone")
            "confidence": float,        # 0.0-1.0 (LLM confidence or 0.3 for regex fallback)
            "reasoning": str,           # LLM reasoning (empty for regex)
            "classified_at": str        # ISO-8601 timestamp
        }
    
    classification_method : ClassificationMethod  # ENUM: LLM_GPT4|FALLBACK_REGEX|MANUAL_OVERRIDE
    circuit_breaker_tripped : bool              # True if Circuit Breaker activated

    ── Written by any node (overall bookkeeping) ──────────────────────────
    overall_status  : ValidationStatus    # ENUM: PROCESSING|VALIDATED|REJECTED|ERROR_PROCESSING
    error_messages  : List[str]           # Runtime errors (not validation failures)
    validation_path : List[str]           # Node names in execution order (breadcrumbs)
    completed_at    : str                 # ISO-8601 timestamp when all nodes finished

    ── Written by END node (after geometry processing) ────────────────────
    low_poly_url    : str                 # URL to low-poly LOD asset in Supabase Storage
    """

    # ── Core identifiers (1-3 of 15) ───────────────────────────────────────
    block_id: str
    created_at: str
    retry_count: int

    # ── Nomenclature (4-5 of 16) — VESTIGIAL ───────────────────────────────
    # ISO-19650 nomenclature validation was removed (real SF layer names never
    # follow ISO-19650; see memory-bank/decisions.md). These fields are kept
    # only so the report/snapshot schema and field-count tests stay stable;
    # nothing populates them anymore. nomenclature_valid defaults True.
    nomenclature_valid: bool
    nomenclature_errors: List[str]

    # ── Geometry extraction and validation (6-8 of 16) ─────────────────────
    geometry_metadata: Dict[str, Any]
    geometry_valid: bool
    geometry_errors: List  # List[ValidationErrorItem] — validation errors from GeometryValidator

    # ── Semantic classification (9-11 of 16) ───────────────────────────────
    semantic_data: Dict[str, Any]
    classification_method: ClassificationMethod
    circuit_breaker_tripped: bool

    # ── Global bookkeeping (12-15 of 16) ───────────────────────────────────
    overall_status: ValidationStatus
    error_messages: List[str]
    validation_path: List[str]
    completed_at: str

    # ── Output assets (16 of 16) ───────────────────────────────────────────
    low_poly_url: str


def make_initial_state(block_id: str, retry_count: int = 0) -> ValidationState:
    """
    Factory function: creates a fresh ValidationState before the graph starts.

    WHY A FACTORY FUNCTION
    ======================
    We need to initialise the state with sensible defaults before the first
    node runs. Without defaults, the first node would need to check whether
    every field exists before reading it — noisy and error-prone.

    This function provides ONE place where defaults are defined. If you add a
    new field to ValidationState, you add its default here too.

    Args:
        block_id : UUID string of the blocks row in Supabase
        retry_count : Celery task retry counter (default 0 for first attempt)

    Returns:
        A ValidationState dict with all 15 required fields initialised.

    Example:
        >>> state = make_initial_state("uuid-123", retry_count=0)
        >>> state["overall_status"]
        ValidationStatus.PROCESSING
        >>> state["validation_path"]
        []
        >>> len(state.keys())
        16
    
    Added in T-1801, updated to 16 fields in T-1806 (added geometry_errors).
    """
    return ValidationState(
        # Core identifiers (1-3 of 16)
        block_id=block_id,
        created_at=datetime.utcnow().isoformat(),
        retry_count=retry_count,

        # Nomenclature (4-5 of 16) — VESTIGIAL: validation removed, nothing
        # populates these. Default True so reports show "no nomenclature issue".
        nomenclature_valid=True,
        nomenclature_errors=[],

        # Geometry (6-8 of 16) — set by ExtractGeometry + ValidateGeometry nodes
        geometry_metadata={},
        geometry_valid=False,
        geometry_errors=[],  # T-1806: Add geometry errors list

        # Semantic classification (9-11 of 16) — set by ClassifyTipologia node
        semantic_data={},
        classification_method=ClassificationMethod.FALLBACK_REGEX,  # Default to fallback
        circuit_breaker_tripped=False,

        # Global bookkeeping (12-15 of 16) — updated by any node
        overall_status=ValidationStatus.PROCESSING,
        error_messages=[],
        validation_path=[],
        completed_at="",

        # Output assets (16 of 16) — set by END node after geometry processing
        low_poly_url="",
    )

