"""
LangGraph Node Functions (US-018 / T-1601 skeleton + T-1803 integration)

WHAT IS A NODE?
===============
In LangGraph, a "node" is just a Python function with a very specific signature:

    def my_node(state: ValidationState) -> dict:
        # 1. Read whatever you need from `state`
        # 2. Do some work
        # 3. Return a PARTIAL dict with only the fields you changed

LangGraph calls each node with the current state, collects the returned dict,
and merges it back. The next node then receives the updated state.

This is called the "reducer" pattern — same idea as React's useReducer().

WHY STUBS FOR T-1601?
=====================
T-1601's job is to prove the STRUCTURE works:
  - The state can be created and passed around
  - The graph compiles without errors
  - The conditional edges (fail-fast) work correctly
  - All 10 unit tests pass

The real logic (rhino3dm parsing, LLM calls, Jinja2 reports) is implemented
in subsequent tickets. The stubs log what they *would* do and return minimal
state updates so the graph can flow from START to END in tests.

NODE NAMING CONVENTION
======================
Each function is named after its position in the validation pipeline:
  node_validate_nomenclature   → checks layer names against ISO-19650
  node_extract_geometry        → downloads .3dm and reads geometry
  node_validate_geometry       → checks mesh integrity
  node_classify_tipologia      → LLM: what architectural type is this?
  node_enrich_metadata         → extracts user strings (material, iso_code)
  node_generate_report         → compiles Jinja2 JSON report
  node_mark_validated          → sets overall_status = "validated"
  node_mark_rejected           → sets overall_status = "rejected"

The "mark" nodes are terminal — they always lead to END.
"""

import structlog
from datetime import datetime
from typing import Dict, Any

try:
    from src.agent.graph.state import ValidationState, ValidationStatus, ClassificationMethod
except ImportError:
    from graph.state import ValidationState, ValidationStatus, ClassificationMethod

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# HELPER: append the current node name to the validation_path breadcrumbs
# ─────────────────────────────────────────────────────────────────────────────

def _append_to_path(state: ValidationState, node_name: str) -> list:
    """
    Returns a new list with node_name appended to the current validation_path.

    We never mutate the state directly — we return a new list. LangGraph will
    merge this into the running state via its update mechanism.

    Args:
        state     : Current ValidationState
        node_name : Name of the node currently executing

    Returns:
        New list with node_name added at the end.
    """
    current_path = state.get("validation_path", [])
    return current_path + [node_name]


# ─────────────────────────────────────────────────────────────────────────────
# NODE 1: ValidateNomenclature
# ─────────────────────────────────────────────────────────────────────────────

def node_validate_nomenclature(state: ValidationState) -> Dict[str, Any]:
    """
    Node 1: Validate that all layer names in the file comply with ISO-19650.

    This is the FIRST node in the graph and acts as a gatekeeper.
    If nomenclature fails, the conditional edge routes directly to REJECTED
    without running the expensive nodes (geometry parsing, LLM calls).

    Current implementation (T-1601 stub):
        Looks at state["filename"] and does a simple regex check on the name.
        Returns nomenclature_valid=True if filename matches ISO-19650 pattern.

    Full implementation (T-1803):
        Will use NomenclatureValidator service (already exists from US-002)
        wrapped as a LangGraph adapter to validate every layer in the .3dm file.

    Args:
        state: Current ValidationState (reads: filename, block_id)

    Returns:
        Partial state update with:
          - nomenclature_valid (bool)
          - nomenclature_errors (list)
          - validation_path (list with "ValidateNomenclature" appended)
          - overall_status set to PROCESSING
    """
    import re

    node_name = "ValidateNomenclature"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    filename = state.get("filename", "")
    # Strip extension to check base name (e.g. "SF-C12-D-001.3dm" → "SF-C12-D-001")
    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

    # ISO-19650 pattern: e.g. SF-C12-D-001 (same regex used by NomenclatureValidator)
    ISO_PATTERN = r"^[A-Z]{2,3}-[A-Z0-9]{3,4}-[A-Z]{1,2}-\d{3}$"
    is_valid = bool(re.match(ISO_PATTERN, base_name))

    errors = []
    if not is_valid:
        errors.append({
            "layer": base_name,
            "message": f"Filename does not match ISO-19650 pattern. Expected: SF-XXX-YY-ZZZ, got: '{base_name}'",
            "category": "nomenclature",
        })

    logger.info(
        "node.complete",
        node=node_name,
        nomenclature_valid=is_valid,
        error_count=len(errors),
    )

    return {
        "nomenclature_valid": is_valid,
        "nomenclature_errors": errors,
        "overall_status": ValidationStatus.PROCESSING.value,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2: ExtractGeometry
# ─────────────────────────────────────────────────────────────────────────────

def node_extract_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 2: Download the .3dm file from Supabase Storage and extract geometry.

    Only reached if nomenclature passed (conditional edge from Node 1).

    Current implementation (T-1601 stub):
        Returns placeholder geometry metadata so the graph can continue.

    Full implementation (T-1803):
        Will use FileDownloadService + RhinoParserService (both exist in US-002).
        Downloads the actual .3dm, calls rhino3dm.File3dm.Read(), and extracts
        layers, object list, bounding box, and volume.

    Args:
        state: Current ValidationState (reads: file_key, block_id)

    Returns:
        Partial state update with:
          - rhino_layers (list)
          - geometry_objects (int)
          - geometry_metadata (dict with bbox, volume, triangle_count)
          - validation_path (updated breadcrumbs)
    """
    node_name = "ExtractGeometry"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # Stub: placeholder geometry metadata
    # In T-1803, this will call RhinoParserService.parse_file()
    geometry_metadata = {
        "volume": 0.0,
        "bbox": {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
        "triangle_count": 0,
        "layer_count": 0,
        "stub": True,  # Flag to detect stub execution in tests
    }

    logger.info("node.complete", node=node_name, stub=True)

    return {
        "rhino_layers": [],
        "geometry_objects": 0,
        "geometry_metadata": geometry_metadata,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3: ValidateGeometry
# ─────────────────────────────────────────────────────────────────────────────

def node_validate_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 3: Validate geometric integrity of the extracted geometry.

    Checks for:
      - Null/missing geometry objects
      - Invalid geometry (Rhino's internal IsValid flag)
      - Degenerate bounding boxes (zero-size)
      - Zero-volume solids

    Current implementation (T-1601 stub):
        Passes validation automatically (geometry_valid=True) so the graph
        can flow to the classification node in tests.

    Full implementation (T-1803):
        Will use GeometryValidator service (already exists from US-002),
        wrapped as a LangGraph adapter.

    Args:
        state: Current ValidationState (reads: geometry_metadata, rhino_layers)

    Returns:
        Partial state update with:
          - geometry_valid (bool)
          - geometry_errors (list)
          - validation_path (updated breadcrumbs)
    """
    node_name = "ValidateGeometry"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # Stub: always passes
    # In T-1803, this will call GeometryValidator.validate_geometry()
    is_valid = True
    errors = []

    logger.info("node.complete", node=node_name, geometry_valid=is_valid, stub=True)

    return {
        "geometry_valid": is_valid,
        "geometry_errors": errors,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4: ClassifyTipologia
# ─────────────────────────────────────────────────────────────────────────────

def node_classify_tipologia(state: ValidationState) -> Dict[str, Any]:
    """
    Node 4: Classify the architectural type (tipologia) of the piece.

    Uses GPT-4 Turbo to reason about the geometry metadata and determine
    whether the piece is a dovela, capitel, columna, clave, imposta, etc.
    Falls back to regex pattern matching if the LLM is unavailable.

    Current implementation (T-1601 stub):
        Returns a hardcoded "other" classification with confidence=0.5 and
        classification_method=NOT_CLASSIFIED. This lets the full graph run
        in tests without requiring an OpenAI API key.

    Full implementation (T-1602):
        Will implement GPT-4 Turbo with JSON Mode, Tenacity retries (3 attempts),
        Circuit Breaker (Redis flag after 5 consecutive failures), and fallback
        regex (filename pattern matching).

    Args:
        state: Current ValidationState (reads: geometry_metadata, filename)

    Returns:
        Partial state update with:
          - tipologia (str)
          - classification_confidence (float)
          - classification_method (str)
          - classification_reasoning (str)
          - circuit_breaker_tripped (bool)
          - validation_path (updated breadcrumbs)
    """
    node_name = "ClassifyTipologia"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # Stub: placeholder classification
    # In T-1602, this will call OpenAI GPT-4 Turbo with JSON Mode
    result = {
        "tipologia": "other",
        "classification_confidence": 0.5,
        "classification_method": ClassificationMethod.NOT_CLASSIFIED.value,
        "classification_reasoning": "Stub implementation — LLM not yet connected (T-1602)",
        "circuit_breaker_tripped": False,
        "validation_path": _append_to_path(state, node_name),
    }

    logger.info("node.complete", node=node_name, tipologia="other", stub=True)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NODE 5: EnrichMetadata
# ─────────────────────────────────────────────────────────────────────────────

def node_enrich_metadata(state: ValidationState) -> Dict[str, Any]:
    """
    Node 5: Extract and enrich user strings from the Rhino file.

    Reads document-level, layer-level, and object-level user strings
    from the .3dm file. Extracts:
      - material_type (from UserString key "Material")
      - iso_code      (from UserString key "Codi" or layer name)
      - Any other custom properties the architect attached

    Current implementation (T-1601 stub):
        Returns empty user strings and derives iso_code from the filename.

    Full implementation (T-1803):
        Will use UserStringExtractor service (already exists from US-002).

    Args:
        state: Current ValidationState (reads: filename, rhino_layers)

    Returns:
        Partial state update with:
          - user_strings (dict)
          - material_type (str)
          - iso_code (str)
          - validation_path (updated breadcrumbs)
    """
    node_name = "EnrichMetadata"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    filename = state.get("filename", "")
    iso_code = filename.rsplit(".", 1)[0] if "." in filename else filename

    logger.info("node.complete", node=node_name, iso_code=iso_code, stub=True)

    return {
        "user_strings": {},
        "material_type": "",
        "iso_code": iso_code,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 6: GenerateReport
# ─────────────────────────────────────────────────────────────────────────────

def node_generate_report(state: ValidationState) -> Dict[str, Any]:
    """
    Node 6: Compile all validation results into a structured JSON report.

    Assembles the final report from all previous node outputs.
    The report is stored in blocks.validation_report (JSONB column already
    exists from US-002 migration T-020-DB). The frontend ValidationReportModal
    component reads this exact structure, so the schema is fixed.

    Current implementation (T-1601 stub):
        Returns a minimal report dict with the essential fields.

    Full implementation (T-1604):
        Will render a Jinja2 template (validation_report.json.j2) with
        richer structure: geometry_summary, semantic_data, validation_path
        timeline, per-node timing, etc.

    Args:
        state: Current ValidationState (reads: all previous node outputs)

    Returns:
        Partial state update with:
          - validation_report (dict)
          - validation_path (updated breadcrumbs)
    """
    node_name = "GenerateReport"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # Collect all errors from all validation nodes
    all_errors = (
        state.get("nomenclature_errors", []) +
        state.get("geometry_errors", [])
    )

    report = {
        "overall_status": state.get("overall_status", ValidationStatus.PROCESSING.value),
        "errors": all_errors,
        "metadata": {
            "iso_code": state.get("iso_code", ""),
            "material_type": state.get("material_type", ""),
            "tipologia": state.get("tipologia", ""),
        },
        "semantic_data": {
            "tipologia": state.get("tipologia", ""),
            "confidence": state.get("classification_confidence", 0.0),
            "classification_method": state.get("classification_method", ""),
            "reasoning": state.get("classification_reasoning", ""),
        },
        "geometry_summary": state.get("geometry_metadata", {}),
        "validation_path": state.get("validation_path", []),
        "validated_by": "sf-pm-agent-v1",
        "timestamp": datetime.utcnow().isoformat(),
        "stub": True,  # Removed in T-1604 when Jinja2 renders real template
    }

    logger.info("node.complete", node=node_name, error_count=len(all_errors))

    return {
        "validation_report": report,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 7: MarkValidated  (terminal node — happy path)
# ─────────────────────────────────────────────────────────────────────────────

def node_mark_validated(state: ValidationState) -> Dict[str, Any]:
    """
    Terminal node: all checks passed → mark element as VALIDATED.

    This node always leads to END. It sets the final status and timestamp.
    The Celery task reads overall_status after graph.invoke() returns and
    calls db_service.update_block_status() to persist the outcome.

    Args:
        state: Current ValidationState

    Returns:
        Partial state update with:
          - overall_status = "validated"
          - completed_at (ISO-8601 timestamp)
          - validation_path (updated breadcrumbs)
    """
    node_name = "MarkValidated"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    completed_at = datetime.utcnow().isoformat()

    logger.info(
        "validation.completed",
        node=node_name,
        block_id=state.get("block_id"),
        status="validated",
    )

    return {
        "overall_status": ValidationStatus.VALIDATED.value,
        "completed_at": completed_at,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 8: MarkRejected  (terminal node — validation failure)
# ─────────────────────────────────────────────────────────────────────────────

def node_mark_rejected(state: ValidationState) -> Dict[str, Any]:
    """
    Terminal node: at least one check failed → mark element as REJECTED.

    This node can be reached from:
      - ValidateNomenclature (fail-fast: bad ISO-19650 name)
      - ValidateGeometry (geometry check failed)

    Crucially, if rejection happens at ValidateNomenclature, the nodes
    ExtractGeometry, ClassifyTipologia, EnrichMetadata, GenerateReport are
    SKIPPED. This is the "fail-fast" behaviour that saves processing time
    and avoids unnecessary LLM costs.

    Args:
        state: Current ValidationState (reads: nomenclature_errors, geometry_errors)

    Returns:
        Partial state update with:
          - overall_status = "rejected"
          - validation_report (summary of why it was rejected)
          - completed_at (ISO-8601 timestamp)
          - validation_path (updated breadcrumbs)
    """
    node_name = "MarkRejected"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    all_errors = (
        state.get("nomenclature_errors", []) +
        state.get("geometry_errors", [])
    )

    report = {
        "overall_status": ValidationStatus.REJECTED.value,
        "errors": all_errors,
        "metadata": {
            "iso_code": state.get("iso_code", ""),
        },
        "validation_path": state.get("validation_path", []),
        "validated_by": "sf-pm-agent-v1",
        "timestamp": datetime.utcnow().isoformat(),
    }

    completed_at = datetime.utcnow().isoformat()

    logger.info(
        "validation.rejected",
        node=node_name,
        block_id=state.get("block_id"),
        error_count=len(all_errors),
    )

    return {
        "overall_status": ValidationStatus.REJECTED.value,
        "validation_report": report,
        "completed_at": completed_at,
        "validation_path": _append_to_path(state, node_name),
    }
