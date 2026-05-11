"""
StateGraph Definition for LangGraph Validation Pipeline (US-018 / T-1801)

WHY A STATEGRAPH?
=================
LangGraph's StateGraph is a directed graph where:
  - Each node is a Python function that receives state and returns a partial update
  - Edges connect nodes and can be:
    • Normal edges: always go from A → B
    • Conditional edges: go to B or C depending on state
  - The graph has a START node and can have multiple END nodes

This file wires together the 8 validation nodes defined in nodes.py with
conditional edges that implement fail-fast behavior.

FAIL-FAST ARCHITECTURE (T-1801 requirement)
===========================================
The graph is designed to stop early when validation fails:

  1. ValidateNomenclature (FIRST gatekeeper)
     → If nomenclature_valid == False → skip everything, go to MarkRejected
     → If nomenclature_valid == True → continue to ExtractGeometry

  2. ValidateGeometry (SECOND gatekeeper)
     → If geometry_valid == False → skip LLM, go to MarkRejected
     → If geometry_valid == True → continue to ClassifyTipologia

This architecture saves:
  - API costs (no LLM call if nomenclature/geometry fails)
  - Processing time (early rejection in 3 events instead of 8+)
  - Storage I/O (no .3dm download if filename is invalid)

GRAPH STRUCTURE (Happy Path):
==============================
START
  → ValidateNomenclature
    → ExtractGeometry
      → ValidateGeometry
        → ClassifyTipologia (LLM or fallback)
          → EnrichMetadata
            → GenerateReport
              → MarkValidated
                → END

GRAPH STRUCTURE (Fail-Fast Path):
==================================
START
  → ValidateNomenclature
    → [FAIL] → MarkRejected → END
  
OR:

START
  → ValidateNomenclature
    → ExtractGeometry
      → ValidateGeometry
        → [FAIL] → MarkRejected → END

IMPLEMENTATION (T-1801 skeleton):
==================================
  - All 8 nodes are stubs (real logic in T-1802, T-1803, T-1804)
  - Conditional edges use simple boolean checks
  - Graph compiles and executes without errors
  - 10 unit tests verify structure (see tests/agent/unit/test_stategraph.py)

Author: AI Agent (T-1801-AGENT)
Created: 2026-05-04
"""

import structlog
from langgraph.graph import StateGraph, END
from typing import Literal

try:
    from src.agent.graph.state import ValidationState, make_initial_state
    from src.agent.graph.nodes import (
        node_validate_nomenclature,
        node_extract_geometry,
        node_validate_geometry,
        node_classify_tipologia,
        node_enrich_metadata,
        node_generate_report,
        node_mark_validated,
        node_mark_rejected,
    )
except ImportError:
    from graph.state import ValidationState, make_initial_state
    from graph.nodes import (
        node_validate_nomenclature,
        node_extract_geometry,
        node_validate_geometry,
        node_classify_tipologia,
        node_enrich_metadata,
        node_generate_report,
        node_mark_validated,
        node_mark_rejected,
    )

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# CONDITIONAL EDGE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def should_continue_after_extract_geometry(state: ValidationState) -> Literal["ValidateNomenclature", "MarkRejected"]:
    """
    Conditional edge after ExtractGeometry node.

    Returns:
        "ValidateNomenclature" if file_exists_in_storage == True (continue happy path)
        "MarkRejected" if file download/parse failed (fail-fast)
    
    This is the FIRST gatekeeper — if file doesn't exist or parse fails,
    we skip all downstream validation and reject immediately.
    """
    geometry_metadata = state.get("geometry_metadata", {})
    file_exists = geometry_metadata.get("file_exists_in_storage", False)
    next_node = "ValidateNomenclature" if file_exists else "MarkRejected"
    
    # T-1805: Insert TRANSITION_CONDITIONAL event
    block_id = state.get("block_id", "unknown")
    try:
        from src.agent.graph.nodes import insert_event
        from src.agent.constants import EventType
        
        # Create updated state with transition metadata
        transition_state = {
            **state,
            "transition_condition": f"file_exists_in_storage == {file_exists}",
            "next_node": next_node,
        }
        
        insert_event(block_id, EventType.TRANSITION_CONDITIONAL, "ExtractGeometry", transition_state)
    except Exception as e:
        logger.warning(
            "audit.transition_event_failed",
            block_id=block_id,
            edge="extract_geometry",
            error=str(e)
        )
    
    logger.info(
        "edge.extract_geometry_decision",
        file_exists_in_storage=file_exists,
        next_node=next_node,
    )
    
    return next_node


def should_continue_after_nomenclature(state: ValidationState) -> Literal["ValidateGeometry", "MarkRejected"]:
    """
    Conditional edge after ValidateNomenclature node.

    Returns:
        "ValidateGeometry" if nomenclature_valid == True (continue happy path)
        "MarkRejected" if nomenclature_valid == False (fail-fast)
    
    This is the SECOND gatekeeper — if nomenclature fails, we skip all downstream
    processing (geometry validation, LLM classification) and reject immediately.
    """
    is_valid = state.get("nomenclature_valid", False)
    next_node = "ValidateGeometry" if is_valid else "MarkRejected"
    
    # T-1805: Insert TRANSITION_CONDITIONAL event
    block_id = state.get("block_id", "unknown")
    try:
        from src.agent.graph.nodes import insert_event
        from src.agent.constants import EventType
        
        transition_state = {
            **state,
            "transition_condition": f"nomenclature_valid == {is_valid}",
            "next_node": next_node,
        }
        
        insert_event(block_id, EventType.TRANSITION_CONDITIONAL, "ValidateNomenclature", transition_state)
    except Exception as e:
        logger.warning(
            "audit.transition_event_failed",
            block_id=block_id,
            edge="nomenclature",
            error=str(e)
        )
    
    logger.info(
        "edge.nomenclature_decision",
        nomenclature_valid=is_valid,
        next_node=next_node,
    )
    
    return next_node


def should_continue_after_geometry(state: ValidationState) -> Literal["ClassifyTipologia", "MarkRejected"]:
    """
    Conditional edge after ValidateGeometry node.

    Returns:
        "ClassifyTipologia" if geometry_valid == True (continue to LLM/fallback)
        "MarkRejected" if geometry_valid == False (fail-fast)
    
    This is the THIRD gatekeeper — if geometry fails, we skip LLM classification
    (no point classifying a malformed mesh) and reject immediately.
    """
    is_valid = state.get("geometry_valid", False)
    next_node = "ClassifyTipologia" if is_valid else "MarkRejected"
    
    # T-1805: Insert TRANSITION_CONDITIONAL event
    block_id = state.get("block_id", "unknown")
    try:
        from src.agent.graph.nodes import insert_event
        from src.agent.constants import EventType
        
        transition_state = {
            **state,
            "transition_condition": f"geometry_valid == {is_valid}",
            "next_node": next_node,
        }
        
        insert_event(block_id, EventType.TRANSITION_CONDITIONAL, "ValidateGeometry", transition_state)
    except Exception as e:
        logger.warning(
            "audit.transition_event_failed",
            block_id=block_id,
            edge="geometry",
            error=str(e)
        )
    
    logger.info(
        "edge.geometry_decision",
        geometry_valid=is_valid,
        next_node=next_node,
    )
    
    return next_node


# ─────────────────────────────────────────────────────────────────────────────
# STATEGRAPH BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def create_validation_graph() -> StateGraph:
    """
    Factory function: creates and compiles the LangGraph StateGraph.

    Returns:
        Compiled StateGraph ready to execute with .invoke(initial_state)
    
    Workflow structure (T-1801):
        - 8 nodes (6 processing + 2 terminal)
        - 2 conditional edges (fail-fast gatekeepers)
        - 6 normal edges (happy path linear flow)
    
    Example usage:
        >>> graph = create_validation_graph()
        >>> initial_state = make_initial_state(block_id="uuid-123")
        >>> final_state = graph.invoke(initial_state)
        >>> final_state["overall_status"]
        ValidationStatus.VALIDATED
    """
    logger.info("graph.building", nodes=8, conditional_edges=2)

    # ── STEP 1: Create the graph builder ──────────────────────────────────
    # StateGraph is parameterized with our ValidationState TypedDict
    workflow = StateGraph(ValidationState)

    # ── STEP 2: Add nodes ──────────────────────────────────────────────────
    # Each node is a function that receives ValidationState and returns a dict
    workflow.add_node("ExtractGeometry", node_extract_geometry)
    workflow.add_node("ValidateNomenclature", node_validate_nomenclature)
    workflow.add_node("ValidateGeometry", node_validate_geometry)
    workflow.add_node("ClassifyTipologia", node_classify_tipologia)
    workflow.add_node("EnrichMetadata", node_enrich_metadata)
    workflow.add_node("GenerateReport", node_generate_report)
    workflow.add_node("MarkValidated", node_mark_validated)
    workflow.add_node("MarkRejected", node_mark_rejected)

    # ── STEP 3: Set entry point ───────────────────────────────────────────
    # T-1803: Changed entry point to ExtractGeometry (must download .3dm before validating layers)
    # Every execution starts at ExtractGeometry (downloads .3dm, extracts layers/geometry)
    workflow.set_entry_point("ExtractGeometry")

    # ── STEP 4: Add conditional edges (fail-fast gatekeepers) ─────────────
    # Conditional edge #1: After ExtractGeometry
    # → If file_exists_in_storage == True → ValidateNomenclature
    # → If file download/parse failed → MarkRejected (fail-fast)
    workflow.add_conditional_edges(
        "ExtractGeometry",
        should_continue_after_extract_geometry,
        {
            "ValidateNomenclature": "ValidateNomenclature",
            "MarkRejected": "MarkRejected",
        }
    )

    # Conditional edge #2: After ValidateNomenclature
    # → If nomenclature_valid == True → ValidateGeometry
    # → If nomenclature_valid == False → MarkRejected (fail-fast)
    workflow.add_conditional_edges(
        "ValidateNomenclature",
        should_continue_after_nomenclature,
        {
            "ValidateGeometry": "ValidateGeometry",
            "MarkRejected": "MarkRejected",
        }
    )

    # Conditional edge #3: After ValidateGeometry
    # → If geometry_valid == True → ClassifyTipologia
    # → If geometry_valid == False → MarkRejected (fail-fast)
    workflow.add_conditional_edges(
        "ValidateGeometry",
        should_continue_after_geometry,
        {
            "ClassifyTipologia": "ClassifyTipologia",
            "MarkRejected": "MarkRejected",
        }
    )

    # ── STEP 5: Add normal edges (happy path linear flow) ─────────────────
    # After ClassifyTipologia → always → EnrichMetadata
    workflow.add_edge("ClassifyTipologia", "EnrichMetadata")
    
    # After EnrichMetadata → always → GenerateReport
    workflow.add_edge("EnrichMetadata", "GenerateReport")
    
    # After GenerateReport → always → MarkValidated (all checks passed)
    workflow.add_edge("GenerateReport", "MarkValidated")

    # ── STEP 6: Terminal nodes → END ──────────────────────────────────────
    # Both terminal nodes lead to END (graph execution stops)
    workflow.add_edge("MarkValidated", END)
    workflow.add_edge("MarkRejected", END)

    # ── STEP 7: Compile the graph ─────────────────────────────────────────
    # Compilation validates:
    #   - No unreachable nodes
    #   - No cycles (unless explicitly allowed)
    #   - All conditional edge paths are defined
    compiled_graph = workflow.compile()

    logger.info(
        "graph.compiled",
        nodes=8,
        edges=9,  # 3 conditional + 6 normal
        entry_point="ExtractGeometry",
        terminal_nodes=["MarkValidated", "MarkRejected"],
    )

    return compiled_graph


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

# Pre-compile the graph at module load time for production use
# Tests can create their own graphs if they need custom configurations
validation_graph = create_validation_graph()

__all__ = [
    "create_validation_graph",
    "validation_graph",
    "should_continue_after_nomenclature",
    "should_continue_after_geometry",
]
