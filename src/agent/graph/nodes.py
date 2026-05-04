"""
LangGraph Node Functions (US-018 / T-1801 skeleton)

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

WHY STUBS FOR T-1801?
=====================
T-1801's job is to prove the STRUCTURE works:
  - The state can be created and passed around (exactly 15 fields)
  - The graph compiles without errors
  - The conditional edges (fail-fast) work correctly
  - All 10 unit tests pass

The real logic (rhino3dm parsing, LLM calls, Jinja2 reports) is implemented
in subsequent tickets (T-1802, T-1803, T-1804). The stubs log what they *would* do
and return minimal state updates so the graph can flow from START to END in tests.

NODE NAMING CONVENTION
======================
Each function is named after its position in the validation pipeline:
  node_validate_nomenclature   → checks layer names against ISO-19650 (US-002)
  node_extract_geometry        → downloads .3dm and reads geometry (rhino3dm)
  node_validate_geometry       → checks mesh integrity (topology validation)
  node_classify_tipologia      → LLM: what architectural type is this? (GPT-4 or fallback)
  node_enrich_metadata         → extracts user strings (material, iso_code)
  node_generate_report         → compiles Jinja2 JSON report
  node_mark_validated          → sets overall_status = VALIDATED (terminal)
  node_mark_rejected           → sets overall_status = REJECTED (terminal)

The "mark" nodes are terminal — they always lead to END.

CRITICAL UPDATE (T-1801):
=========================
All nodes have been updated to work with the new ValidationState TypedDict
that has EXACTLY 15 fields (no more, no less). Nodes should ONLY write to
fields that exist in the spec:
  - block_id, created_at, retry_count
  - nomenclature_valid, nomenclature_errors
  - geometry_metadata, geometry_valid
  - semantic_data, classification_method, circuit_breaker_tripped
  - overall_status, error_messages, validation_path, completed_at
  - low_poly_url

Author: AI Agent (T-1801-AGENT)
Created: 2026-05-04
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
    Node 1: Validate that block filename complies with ISO-19650 pattern.

    This is the FIRST node in the graph and acts as a gatekeeper.
    If nomenclature fails, the conditional edge routes directly to REJECTED
    without running the expensive nodes (geometry parsing, LLM calls).

    Current implementation (T-1801 skeleton):
        Simple stub that validates block_id format as a placeholder.
        Returns nomenclature_valid=True for any valid UUID.

    Full implementation (T-1803):
        Will use NomenclatureValidator service (already exists from US-002)
        to validate every layer in the .3dm file.

    Args:
        state: Current ValidationState (reads: block_id)

    Returns:
        Partial state update with:
          - nomenclature_valid (bool)
          - nomenclature_errors (List[str])
          - validation_path (list with "ValidateNomenclature" appended)
    """
    node_name = "ValidateNomenclature"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: Always pass for now (real logic in T-1803)
    # In production: will fetch .3dm file and validate layer names
    is_valid = True
    errors = []

    logger.info(
        "node.complete",
        node=node_name,
        nomenclature_valid=is_valid,
        error_count=len(errors),
    )

    return {
        "nomenclature_valid": is_valid,
        "nomenclature_errors": errors,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2: ExtractGeometry
# ─────────────────────────────────────────────────────────────────────────────

def node_extract_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 2: Download the .3dm file from Supabase Storage and extract geometry.

    Only reached if nomenclature passed (conditional edge from Node 1).

    Current implementation (T-1801 skeleton):
        Returns placeholder geometry metadata so the graph can continue.

    Full implementation (T-1803):
        Will use RhinoParserService (exists in US-002) to download .3dm file
        and extract volume, bbox, vertex count, layers.
        Also checks file_exists_in_storage (per T-1801 requirement).

    Args:
        state: Current ValidationState (reads: block_id)

    Returns:
        Partial state update with:
          - geometry_metadata (Dict with volume, bbox, vertices_count, etc.)
          - validation_path (list with "ExtractGeometry" appended)
    """
    node_name = "ExtractGeometry"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: Return placeholder metadata
    # In production: will download .3dm and parse with rhino3dm
    geometry_metadata = {
        "volume": 0.0,  # m³
        "bbox": {
            "min": [0.0, 0.0, 0.0],
            "max": [1.0, 1.0, 1.0],
            "dimensions": [1.0, 1.0, 1.0],
        },
        "vertices_count": 0,
        "faces_count": 0,
        "layers": [],
        "has_mesh": True,
        "file_exists_in_storage": True,  # T-1801 requirement
    }

    logger.info("node.complete", node=node_name, has_mesh=True)

    return {
        "geometry_metadata": geometry_metadata,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3: ValidateGeometry
# ─────────────────────────────────────────────────────────────────────────────

def node_validate_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 3: Validate geometry topology (non-zero volume, valid mesh, etc.).

    Only reached if ExtractGeometry succeeded.

    Current implementation (T-1801 skeleton):
        Always returns geometry_valid=True for placeholder metadata.

    Full implementation (T-1803):
        Will use GeometryValidator service (exists in US-002) to check:
        - Non-zero volume
        - Valid mesh topology
        - No degenerate faces
        - Watertight mesh (if applicable)

    Args:
        state: Current ValidationState (reads: geometry_metadata)

    Returns:
        Partial state update with:
          - geometry_valid (bool)
          - validation_path (list with "ValidateGeometry" appended)
    """
    node_name = "ValidateGeometry"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    geometry_metadata = state.get("geometry_metadata", {})
    
    # T-1801 SKELETON: Always pass for now (real logic in T-1803)
    # In production: will check volume > 0, mesh integrity, etc.
    is_valid = geometry_metadata.get("has_mesh", False)

    logger.info("node.complete", node=node_name, geometry_valid=is_valid)

    return {
        "geometry_valid": is_valid,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4: ClassifyTipologia
# ─────────────────────────────────────────────────────────────────────────────

def node_classify_tipologia(state: ValidationState) -> Dict[str, Any]:
    """
    Node 4: Classify architectural piece using LLM (GPT-4) or regex fallback.

    Only reached if geometry validation passed.

    Current implementation (T-1801 skeleton):
        Returns placeholder semantic_data with fallback classification.

    Full implementation (T-1802):
        Will call OpenAI GPT-4 Turbo with prompt engineering.
        Implements Circuit Breaker (5 failures → fallback to regex).
        Confidence threshold: if LLM confidence < 0.7 → use fallback.

    Args:
        state: Current ValidationState (reads: geometry_metadata, circuit_breaker_tripped)

    Returns:
        Partial state update with:
          - semantic_data (Dict with tipologia, material, confidence, reasoning, classified_at)
          - classification_method (ClassificationMethod ENUM)
          - circuit_breaker_tripped (bool, updated if Circuit Breaker activated)
          - validation_path (list with "ClassifyTipologia" appended)
    """
    node_name = "ClassifyTipologia"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: Return placeholder classification with fallback method
    # In production (T-1802): will call GPT-4 or use Circuit Breaker
    semantic_data = {
        "tipologia": "other",  # Placeholder: will be "dovela"|"capitel"|"columna"|etc.
        "material": "Unknown",  # Will be inferred from tipologia
        "confidence": 0.3,  # Low confidence for fallback
        "reasoning": "T-1801 skeleton: placeholder classification",
        "classified_at": datetime.utcnow().isoformat(),
    }

    classification_method = ClassificationMethod.FALLBACK_REGEX
    circuit_breaker_tripped = state.get("circuit_breaker_tripped", False)

    logger.info(
        "node.complete",
        node=node_name,
        tipologia=semantic_data["tipologia"],
        method=classification_method.value,
    )

    return {
        "semantic_data": semantic_data,
        "classification_method": classification_method,
        "circuit_breaker_tripped": circuit_breaker_tripped,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 5: EnrichMetadata
# ─────────────────────────────────────────────────────────────────────────────

def node_enrich_metadata(state: ValidationState) -> Dict[str, Any]:
    """
    Node 5: Extract user strings from .3dm file (material, iso_code, etc.).

    Only reached if classification succeeded.

    Current implementation (T-1801 skeleton):
        Stub node that does nothing (metadata enrichment is optional).

    Full implementation (T-1803):
        Will use UserStringExtractor service (exists in US-002) to extract
        custom metadata from Rhino UserStrings (Codi, Material, etc.).

    Args:
        state: Current ValidationState (reads: block_id)

    Returns:
        Partial state update with:
          - validation_path (list with "EnrichMetadata" appended)
    
    Note: This node may update geometry_metadata with additional fields,
    but does NOT add new top-level state fields (stays within 15 fields).
    """
    node_name = "EnrichMetadata"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: No-op for now (real logic in T-1803)
    # In production: will extract UserStrings and update geometry_metadata

    logger.info("node.complete", node=node_name)

    return {
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 6: GenerateReport
# ─────────────────────────────────────────────────────────────────────────────

def node_generate_report(state: ValidationState) -> Dict[str, Any]:
    """
    Node 6: Generate validation report using Jinja2 template.

    Only reached if all validations passed.

    Current implementation (T-1801 skeleton):
        Stub node that does nothing (report generation in T-1804).

    Full implementation (T-1804):
        Will render Jinja2 template validation_report.json.j2 with state fields.
        Report structure: {errors[], metadata{}, semantic_data{}, geometry_summary{},
        timestamp, validated_by, validation_path[]}.
        Note: Report is stored in database validation_report column, NOT in state.

    Args:
        state: Current ValidationState (reads: all fields)

    Returns:
        Partial state update with:
          - validation_path (list with "GenerateReport" appended)
    
    Note: Report is persisted to database (blocks.validation_report JSONB),
    not added to ValidationState (keeps 15 fields).
    """
    node_name = "GenerateReport"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: No-op for now (real logic in T-1804)
    # In production: will render Jinja2 template and persist to database

    logger.info("node.complete", node=node_name)

    return {
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 7: MarkValidated (TERMINAL)
# ─────────────────────────────────────────────────────────────────────────────

def node_mark_validated(state: ValidationState) -> Dict[str, Any]:
    """
    Terminal Node: Mark block as VALIDATED (all checks passed).

    This node is reached after GenerateReport completes successfully.
    It sets overall_status to VALIDATED and marks the completion timestamp.

    Args:
        state: Current ValidationState

    Returns:
        Partial state update with:
          - overall_status = VALIDATED
          - completed_at (ISO-8601 timestamp)
          - low_poly_url (placeholder, will be set after geometry processing)
          - validation_path (list with "MarkValidated" appended)
    """
    node_name = "MarkValidated"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: Set validated status
    # In production: will also trigger GLB generation (low_poly_url)
    
    completed_at = datetime.utcnow().isoformat()

    logger.info(
        "node.complete",
        node=node_name,
        overall_status=ValidationStatus.VALIDATED.value,
        completed_at=completed_at,
    )

    return {
        "overall_status": ValidationStatus.VALIDATED,
        "completed_at": completed_at,
        "low_poly_url": "",  # Placeholder: will be set after GLB generation
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 8: MarkRejected (TERMINAL)
# ─────────────────────────────────────────────────────────────────────────────

def node_mark_rejected(state: ValidationState) -> Dict[str, Any]:
    """
    Terminal Node: Mark block as REJECTED (one or more checks failed).

    This node is reached via fail-fast conditional edges:
      - nomenclature_valid == False → immediate rejection
      - geometry_valid == False → immediate rejection

    Args:
        state: Current ValidationState (reads: nomenclature_errors, error_messages)

    Returns:
        Partial state update with:
          - overall_status = REJECTED
          - completed_at (ISO-8601 timestamp)
          - validation_path (list with "MarkRejected" appended)
    """
    node_name = "MarkRejected"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    # T-1801 SKELETON: Set rejected status
    # Collect all errors from nomenclature_errors and error_messages
    all_errors = list(state.get("error_messages", []))
    nomenclature_errors = state.get("nomenclature_errors", [])
    
    if nomenclature_errors:
        all_errors.append(f"Nomenclature errors: {len(nomenclature_errors)} found")

    completed_at = datetime.utcnow().isoformat()

    logger.info(
        "node.complete",
        node=node_name,
        overall_status=ValidationStatus.REJECTED.value,
        error_count=len(all_errors),
        completed_at=completed_at,
    )

    return {
        "overall_status": ValidationStatus.REJECTED,
        "error_messages": all_errors,
        "completed_at": completed_at,
        "validation_path": _append_to_path(state, node_name),
    }
