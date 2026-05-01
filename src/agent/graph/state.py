"""
ValidationState — Shared State for the LangGraph Agent (US-018 / T-1601)

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

DESIGN DECISIONS
================
- TypedDict instead of Pydantic because LangGraph requires plain Python dicts.
  LangGraph does NOT accept Pydantic models as the state container directly.
- All fields are Optional so that nodes can be written without knowing what
  previous nodes set. Each node only fills what it knows.
- The `validation_path` list acts as a breadcrumb trail: every node appends
  its own name. This lets us reconstruct the execution path from the final state.
"""

from typing import TypedDict, Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ValidationStatus(str, Enum):
    """
    Overall outcome of the validation pipeline.

    Values:
        PENDING     — just created, no processing started yet
        PROCESSING  — graph is currently running
        VALIDATED   — all checks passed, element is valid
        REJECTED    — at least one check failed (nomenclature or geometry)
        ERROR       — unexpected runtime error (not a validation failure)

    Note: we use (str, Enum) so the value serializes to a plain string in JSON.
    This matters when persisting state_snapshot to Supabase JSONB columns.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR = "error"


class ClassificationMethod(str, Enum):
    """
    How the tipologia classification was determined.

    Values:
        LLM_GPT4        — GPT-4 Turbo answered with high confidence (>=0.7)
        FALLBACK_REGEX  — LLM failed or circuit breaker tripped; regex used
        NOT_CLASSIFIED  — the classification node was never reached
                          (e.g., nomenclature failed before LLM could run)

    Having this field in the state (and in the final report) is important
    for transparency: users can see whether the AI or the regex classified
    their piece, and how confident the system was.
    """
    LLM_GPT4 = "llm_gpt4"
    FALLBACK_REGEX = "fallback_regex"
    NOT_CLASSIFIED = "not_classified"


class ValidationState(TypedDict, total=False):
    """
    Shared state for the entire LangGraph validation pipeline.

    All nodes read from this dict and return a partial update.
    LangGraph merges the returned dict into the running state automatically.

    Fields are grouped by the node that primarily writes to them:

    ── Set at task start (before graph runs) ──────────────────────────────
    block_id        : str           UUID of the blocks row in Supabase
    file_key        : str           Storage path of the .3dm file
    filename        : str           Original filename (used for regex fallback)
    created_at      : str           ISO-8601 timestamp when the run started

    ── Written by ValidateNomenclature ────────────────────────────────────
    nomenclature_valid  : bool      True if all layer names pass ISO-19650
    nomenclature_errors : List[dict] Each dict: {layer, message, category}

    ── Written by ExtractGeometry ─────────────────────────────────────────
    rhino_layers    : List[dict]    Layers found in the .3dm file
    geometry_objects: int           Number of geometry objects in the file
    geometry_metadata: dict         volume, bbox {min, max}, triangle_count, etc.

    ── Written by ValidateGeometry ────────────────────────────────────────
    geometry_valid  : bool          True if geometry passes all checks
    geometry_errors : List[dict]    Each dict: {object_id, message, category}

    ── Written by ClassifyTipologia (LLM or fallback) ─────────────────────
    tipologia       : str           e.g. "dovela", "capitel", "columna", ...
    classification_confidence: float 0.0–1.0 (lower for fallback)
    classification_method    : str   ClassificationMethod value
    classification_reasoning : str   LLM's explanation (empty for fallback)
    circuit_breaker_tripped  : bool  True if OpenAI failed 5+ times

    ── Written by EnrichMetadata ──────────────────────────────────────────
    user_strings    : dict          Raw user strings from the .3dm file
    material_type   : str           Extracted material (e.g. "Montjuïc")
    iso_code        : str           e.g. "SF-C12-D-001" from UserString "Codi"

    ── Written by GenerateReport ──────────────────────────────────────────
    validation_report: dict         Structured report persisted to Supabase

    ── Written by any node (overall bookkeeping) ──────────────────────────
    overall_status  : str           ValidationStatus value
    error_messages  : List[str]     Runtime errors (not validation failures)
    validation_path : List[str]     Node names in execution order (breadcrumbs)
    completed_at    : str           ISO-8601 timestamp when all nodes finished
    """

    # ── Task identity ──────────────────────────────────────────────────────
    block_id: str
    file_key: str
    filename: str
    created_at: str

    # ── Nomenclature node ──────────────────────────────────────────────────
    nomenclature_valid: bool
    nomenclature_errors: List[Dict[str, Any]]

    # ── Geometry extraction node ───────────────────────────────────────────
    rhino_layers: List[Dict[str, Any]]
    geometry_objects: int
    geometry_metadata: Dict[str, Any]

    # ── Geometry validation node ───────────────────────────────────────────
    geometry_valid: bool
    geometry_errors: List[Dict[str, Any]]

    # ── Tipologia classification node (LLM or fallback) ────────────────────
    tipologia: str
    classification_confidence: float
    classification_method: str
    classification_reasoning: str
    circuit_breaker_tripped: bool

    # ── Metadata enrichment node ───────────────────────────────────────────
    user_strings: Dict[str, Any]
    material_type: str
    iso_code: str

    # ── Report generation node ─────────────────────────────────────────────
    validation_report: Dict[str, Any]

    # ── Global bookkeeping (any node can write these) ──────────────────────
    overall_status: str
    error_messages: List[str]
    validation_path: List[str]
    completed_at: str


def make_initial_state(block_id: str, file_key: str, filename: str) -> ValidationState:
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
        file_key : Storage path of the .3dm file (e.g. "uploads/abc.3dm")
        filename : Human-readable filename (used by regex fallback classifier)

    Returns:
        A ValidationState dict with all required fields initialised.

    Example:
        >>> state = make_initial_state("uuid-123", "uploads/SF-C12-D-001.3dm", "SF-C12-D-001.3dm")
        >>> state["overall_status"]
        'pending'
        >>> state["validation_path"]
        []
    """
    return ValidationState(
        block_id=block_id,
        file_key=file_key,
        filename=filename,
        created_at=datetime.utcnow().isoformat(),

        # Nomenclature — will be set by ValidateNomenclature node
        nomenclature_valid=False,
        nomenclature_errors=[],

        # Geometry extraction — will be set by ExtractGeometry node
        rhino_layers=[],
        geometry_objects=0,
        geometry_metadata={},

        # Geometry validation — will be set by ValidateGeometry node
        geometry_valid=False,
        geometry_errors=[],

        # Classification — will be set by ClassifyTipologia node
        tipologia="",
        classification_confidence=0.0,
        classification_method=ClassificationMethod.NOT_CLASSIFIED.value,
        classification_reasoning="",
        circuit_breaker_tripped=False,

        # Metadata enrichment — will be set by EnrichMetadata node
        user_strings={},
        material_type="",
        iso_code="",

        # Report — will be set by GenerateReport node
        validation_report={},

        # Global bookkeeping
        overall_status=ValidationStatus.PENDING.value,
        error_messages=[],
        validation_path=[],
        completed_at="",
    )
