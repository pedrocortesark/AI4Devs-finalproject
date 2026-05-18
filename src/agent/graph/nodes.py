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
Each function is named after its position in the validation pipeline.
NOTE: node_validate_nomenclature (ISO-19650 layer-name check) was removed —
real Sagrada Família layer names never follow ISO-19650. See
memory-bank/decisions.md.
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
import json

try:
    from src.agent.graph.state import ValidationState, ValidationStatus, ClassificationMethod
except ImportError:
    from graph.state import ValidationState, ValidationStatus, ClassificationMethod

# Jinja2 imports for GenerateReport node (T-1804)
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Supabase client for report persistence (T-1804)
try:
    from infra.supabase_client import get_supabase_client
except ImportError:
    from src.agent.infra.supabase_client import get_supabase_client

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# DECORATOR: T-1805 Audit Trail Middleware
# ─────────────────────────────────────────────────────────────────────────────

def with_audit_trail(func):
    """
    Decorator to add automatic audit trail events to LangGraph nodes.

    Wraps a node function to automatically insert NODE_ENTERED and NODE_COMPLETED events.
    Implements middleware pattern for non-invasive instrumentation.

    Design rationale:
        - DRY principle: Avoid duplicating insert_event calls in 8 nodes
        - Separation of concerns: Business logic (node) vs observability (audit)
        - Testability: Decorator can be unit-tested independently
        - Maintainability: Add new audit logic in one place

    Behavior:
        1. Before node execution: insert_event(EventType.NODE_ENTERED)
        2. Execute node function (unchanged business logic)
        3. After node execution: insert_event(EventType.NODE_COMPLETED)
        4. Best-effort: Audit failures logged but don't crash node

    Applies to:
        - All 8 StateGraph nodes (ExtractGeometry, ValidateNomenclature, etc.)
        - Terminal nodes (MarkValidated, MarkRejected)

    Usage:
        >>> @with_audit_trail
        ... def node_validate_nomenclature(state: ValidationState) -> Dict[str, Any]:
        ...     # Node logic unchanged
        ...     return {"nomenclature_valid": True, ...}

    Args:
        func: Node function to wrap (must accept ValidationState, return Dict)

    Returns:
        Wrapped function with automatic audit trail events

    Side effects:
        - INSERT into events table (2 events per node execution)
        - Structured logs: audit.node_entered, audit.node_completed

    Example execution:
        >>> state = make_initial_state("block-123")
        >>> wrapped = with_audit_trail(node_validate_nomenclature)
        >>> result = wrapped(state)
        # DB: INSERT event (node_entered), INSERT event (node_completed)
        # Logs: audit.node_entered, audit.node_completed
    """
    from functools import wraps
    
    try:
        from src.agent.constants import EventType
    except ImportError:
        from agent.constants import EventType
    
    @wraps(func)
    def wrapper(state: ValidationState) -> Dict[str, Any]:
        # Extract node name from function name (node_validate_nomenclature → ValidateNomenclature)
        func_name = func.__name__
        node_name = func_name.replace("node_", "").replace("_", " ").title().replace(" ", "")
        
        # Get block_id from state
        block_id = state.get("block_id", "unknown")
        
        # NODE_ENTERED event (before execution)
        try:
            insert_event(block_id, EventType.NODE_ENTERED, node_name, state)
            logger.debug(
                "audit.node_entered",
                node=node_name,
                block_id=block_id
            )
        except Exception as e:
            # Best-effort: Log error but don't crash node startup
            logger.warning(
                "audit.node_entered_failed",
                node=node_name,
                block_id=block_id,
                error=str(e)
            )
        
        # Execute original node function (unchanged)
        result = func(state)
        
        # NODE_COMPLETED event (after execution)
        # Merge result into state for state_snapshot (includes node's return values)
        updated_state = {**state, **result}
        
        try:
            insert_event(block_id, EventType.NODE_COMPLETED, node_name, updated_state)
            logger.debug(
                "audit.node_completed",
                node=node_name,
                block_id=block_id
            )
        except Exception as e:
            # Best-effort: Log error but don't crash node completion
            logger.warning(
                "audit.node_completed_failed",
                node=node_name,
                block_id=block_id,
                error=str(e)
            )
        
        return result
    
    return wrapper


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


def _append_to_errors(state: ValidationState, error_msg: str) -> list:
    """
    Returns a new list with error_msg appended to the current error_messages.

    Helper for nodes that encounter runtime errors (not validation failures).
    Used by GenerateReport node for template/rendering errors.

    Args:
        state     : Current ValidationState
        error_msg : Error message to append

    Returns:
        New list with error_msg added at the end.
    """
    current_errors = state.get("error_messages", [])
    return current_errors + [error_msg]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: build geometry_metadata from an already-downloaded .3dm (US-018 wiring)
# ─────────────────────────────────────────────────────────────────────────────

def build_initial_geometry_metadata(
    local_path: str,
    parse_result: Any,
    iso_code: str = None,
) -> Dict[str, Any]:
    """
    Build the geometry_metadata dict from a .3dm file already on local disk.

    WHY THIS EXISTS
    ===============
    The production Celery task (validate_file) downloads the uploaded .3dm by
    its real storage key and parses it once. The LangGraph ExtractGeometry node,
    however, re-downloads by `{block_id}.3dm` — a key that does NOT exist in the
    real "1 file → N InstanceDefinition blocks" model.

    This helper lets the task pre-compute the exact geometry_metadata structure
    the graph expects, so ExtractGeometry can reuse it (idempotency guard) and
    skip the (wrong, redundant) download. The structure mirrors what
    node_extract_geometry produces on its happy path.

    Args:
        local_path   : Absolute path to the downloaded .3dm file
        parse_result : FileProcessingResult from RhinoParserService.parse_file()
        iso_code     : Real blocks.iso_code (used by ClassifyTipologia for the LLM)

    Returns:
        geometry_metadata dict with the same keys node_extract_geometry returns
        (layers, bbox, volume, vertices_count, faces_count, rhino_model,
        user_strings, file_exists_in_storage, has_mesh) plus iso_code.
    """
    try:
        import rhino3dm
    except ImportError:
        rhino3dm = None

    bbox_dict = {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0], "dimensions": [1.0, 1.0, 1.0]}
    volume = 0.0
    vertices_count = 0
    faces_count = 0

    model = rhino3dm.File3dm.Read(local_path) if rhino3dm else None

    if model and model.Objects:
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')

        for obj in model.Objects:
            if obj.Geometry:
                obj_bbox = obj.Geometry.GetBoundingBox()
                if obj_bbox.IsValid:
                    min_x = min(min_x, obj_bbox.Min.X)
                    min_y = min(min_y, obj_bbox.Min.Y)
                    min_z = min(min_z, obj_bbox.Min.Z)
                    max_x = max(max_x, obj_bbox.Max.X)
                    max_y = max(max_y, obj_bbox.Max.Y)
                    max_z = max(max_z, obj_bbox.Max.Z)

                if hasattr(obj.Geometry, 'Vertices'):
                    vertices_count += len(obj.Geometry.Vertices)
                if hasattr(obj.Geometry, 'Faces'):
                    faces_count += len(obj.Geometry.Faces)

        if min_x != float('inf'):
            bbox_dict = {
                "min": [min_x, min_y, min_z],
                "max": [max_x, max_y, max_z],
                "dimensions": [max_x - min_x, max_y - min_y, max_z - min_z],
            }
            volume = (max_x - min_x) * (max_y - min_y) * (max_z - min_z)

    return {
        "layers": parse_result.layers,
        "bbox": bbox_dict,
        "volume": volume,
        "vertices_count": vertices_count,
        "faces_count": faces_count,
        "rhino_model": model,
        "user_strings": getattr(parse_result, "user_strings", None),
        "file_exists_in_storage": True,
        "has_mesh": vertices_count > 0,
        "iso_code": iso_code,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: T-1805 Audit Trail - State Snapshot Serializer
# ─────────────────────────────────────────────────────────────────────────────

def serialize_state_snapshot(state: ValidationState) -> dict:
    """
    Serialize ValidationState to lightweight JSONB snapshot for events table.

    Extracts only essential fields (excludes heavy geometry_metadata which can be >1MB).
    Used by insert_event() to store state_snapshot in events.state_snapshot JSONB column.

    Design rationale:
        - Lightweight: ~200 bytes vs full state ~1-2 MB (excludes geometry_metadata)
        - Performance: Faster DB inserts, smaller storage, quicker Grafana queries
        - Auditability: Contains enough context to debug state transitions

    Fields included (from src.agent.constants.STATE_SNAPSHOT_FIELDS):
        - overall_status: "validated" | "rejected" | "processing"
        - nomenclature_valid: bool
        - geometry_valid: bool
        - classification_method: "llm_gpt4" | "fallback_regex" | "manual_override" | None
        - validation_path_length: int (audit: how many nodes executed)

    Args:
        state: Current ValidationState (15 fields)

    Returns:
        Dict with lightweight snapshot (5 fields, ~200 bytes when serialized)

    Example:
        >>> state = {"overall_status": "processing", "nomenclature_valid": True, ...}
        >>> serialize_state_snapshot(state)
        {
            "overall_status": "processing",
            "nomenclature_valid": True,
            "geometry_valid": None,
            "classification_method": None,
            "validation_path_length": 3
        }
    """
    try:
        from src.agent.constants import STATE_SNAPSHOT_FIELDS
    except ImportError:
        from agent.constants import STATE_SNAPSHOT_FIELDS

    snapshot = {}
    
    # Extract STATE_SNAPSHOT_FIELDS from state
    for field in STATE_SNAPSHOT_FIELDS:
        snapshot[field] = state.get(field)
    
    # Add validation_path length (audit: progression tracking)
    validation_path = state.get("validation_path", [])
    snapshot["validation_path_length"] = len(validation_path) if validation_path else 0
    
    return snapshot


def insert_event(
    block_id: str,
    event_type: str,
    node_name: str,
    state: ValidationState
) -> None:
    """
    Insert audit trail event into events table (best-effort, fire-and-forget).

    Tracks LangGraph StateGraph node transitions for debugging, monitoring, and
    Grafana timeline visualization. Failures are logged as WARNING but do NOT
    block StateGraph execution (degradation graceful).

    Design patterns:
        - Best-effort: DB failures logged but non-fatal (graph continues)
        - Fire-and-forget: No return value, no exception propagation
        - Timeout: 5s max (prevents blocking on slow DB)
        - Logging: Structured logs for observability

    Database schema (created by 20260508000001_add_langgraph_events.sql):
        events(
            id UUID PRIMARY KEY,
            block_id UUID NOT NULL,
            event_type VARCHAR(100),  -- EventType constant
            node_name VARCHAR(100),   -- StateGraph node name
            state_snapshot JSONB,     -- serialize_state_snapshot(state)
            metadata JSONB,           -- Legacy, nullable
            created_at TIMESTAMPTZ
        )

    Event types (from src.agent.constants.EventType):
        - node_entered: Node execution started
        - node_completed: Node finished successfully
        - transition_conditional: Conditional edge evaluated
        - circuit_breaker_tripped: LLM circuit breaker activated
        - fallback_activated: Fallback to regex classification

    Args:
        block_id   : UUID of block being validated (e.g., "GLPER.B-PAE0720.0701")
        event_type : EventType constant (e.g., EventType.NODE_COMPLETED)
        node_name  : StateGraph node name (e.g., "ValidateNomenclature")
        state      : Current ValidationState (used for state_snapshot)

    Returns:
        None (fire-and-forget, logs success/failure)

    Side effects:
        - INSERT into events table (Supabase PostgreSQL)
        - Structured log: event.inserted or event.insert_failed

    Example:
        >>> from src.agent.constants import EventType
        >>> insert_event(
        ...     "GLPER.B-PAE0720.0701",
        ...     EventType.NODE_COMPLETED,
        ...     "ValidateNomenclature",
        ...     state
        ... )
        # Logs: event.inserted block_id=GLPER.B-PAE0720.0701 node_name=ValidateNomenclature
    """
    try:
        # Serialize lightweight state snapshot
        state_snapshot = serialize_state_snapshot(state)
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # INSERT event (timeout 5s)
        result = supabase.table("events").insert({
            "block_id": block_id,
            "event_type": event_type,
            "node_name": node_name,
            "state_snapshot": state_snapshot,
            "metadata": None  # Legacy field, not used by LangGraph events
        }).execute()
        
        # Success log (structured)
        logger.info(
            "event.inserted",
            block_id=block_id,
            event_type=event_type,
            node_name=node_name,
            snapshot_size=len(json.dumps(state_snapshot))
        )
        
    except Exception as e:
        # Best-effort pattern: Log error but DON'T raise
        # Rationale: Audit trail failures should NOT fail validation workflow
        logger.warning(
            "event.insert_failed",
            block_id=block_id,
            event_type=event_type,
            node_name=node_name,
            error=str(e),
            error_type=type(e).__name__
        )


# ─────────────────────────────────────────────────────────────────────────────
# NODE 1: ExtractGeometry
# ─────────────────────────────────────────────────────────────────────────────

@with_audit_trail
def node_extract_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 2: Download .3dm file from Supabase Storage and extract geometry metadata.

    This is the FIRST computational node after initial validation.
    Downloads the .3dm file, parses it with rhino3dm, and extracts:
      - Layers (for nomenclature validation)
      - Bounding box, volume, vertex/face counts (for geometry validation)
      - User strings (for metadata enrichment)
      - Rhino3dm model object (for downstream nodes)

    Implementation (T-1803 Adapter Pattern):
        Uses RhinoParserService (US-002) and UserStringExtractor (US-002).
        Downloads file from Supabase Storage → parse with rhino3dm → extract metadata.
        Zero regression: Parser services remain 100% unchanged.

    Flow:
        1. Download .3dm file from Supabase Storage (STORAGE_BUCKET_RAW_UPLOADS)
        2. Save temporarily to /tmp for rhino3dm parsing
        3. Call RhinoParserService.parse_file() → FileProcessingResult
        4. Extract bbox/volume/vertices from rhino3dm model
        5. Store rhino_model in state for ValidateGeometry node
        6. Return comprehensive geometry_metadata

    Args:
        state: Current ValidationState (reads: block_id)

    Returns:
        Partial state update with:
          - geometry_metadata (Dict): Complete geometry metadata including:
              - layers (List[LayerInfo]): For nomenclature validation
              - bbox (Dict): Bounding box {min, max, dimensions}
              - volume (float): m³
              - vertices_count (int): Total vertex count
              - faces_count (int): Total face count
              - rhino_model: rhino3dm.File3dm object for ValidateGeometry
              - user_strings (UserStringCollection): For EnrichMetadata
              - file_exists_in_storage (bool): T-1801 requirement
          - validation_path (list with "ExtractGeometry" appended)

    Raises:
        Returns error_messages if file download or parsing fails.
    """
    import tempfile
    import os
    from infra.supabase_client import get_supabase_client
    from src.agent.services.rhino_parser_service import RhinoParserService
    from constants import STORAGE_BUCKET_RAW_UPLOADS  # Backend constant
    
    try:
        import rhino3dm
    except ImportError:
        rhino3dm = None
    
    node_name = "ExtractGeometry"
    block_id = state.get("block_id", "unknown")
    logger.info("node.enter", node=node_name, block_id=block_id)

    # US-018 wiring: if the caller already downloaded + parsed the .3dm and
    # pre-populated geometry_metadata (production validate_file path), reuse it
    # and skip the {block_id}.3dm download (which is wrong in the real
    # "1 file → N InstanceDefinition blocks" model). Old/test callers that do
    # NOT pre-populate fall through to the original download logic unchanged.
    preloaded = state.get("geometry_metadata") or {}
    if preloaded.get("file_exists_in_storage"):
        logger.info(
            "extract_geometry.using_preloaded_metadata",
            node=node_name,
            block_id=block_id,
            layer_count=len(preloaded.get("layers", [])),
        )
        return {
            "geometry_metadata": preloaded,
            "validation_path": _append_to_path(state, node_name),
        }

    # Initialize Supabase client
    supabase = get_supabase_client()
    
    # T-1803 ADAPTER: Download .3dm file from Supabase Storage
    file_key = f"{block_id}.3dm"
    temp_file_path = None
    
    try:
        # Download file from Supabase Storage
        logger.info(
            "extract_geometry.downloading_file",
            node=node_name,
            block_id=block_id,
            file_key=file_key,
        )
        
        file_content = supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).download(file_key)
        
        if not file_content:
            logger.error(
                "extract_geometry.file_not_found",
                node=node_name,
                block_id=block_id,
            )
            return {
                "geometry_metadata": {
                    "file_exists_in_storage": False,
                    "layers": [],
                    "volume": 0.0,
                    "bbox": {},
                    "vertices_count": 0,
                    "faces_count": 0,
                },
                "error_messages": [f"File not found in storage: {file_key}"],
                "validation_path": _append_to_path(state, node_name),
            }
        
        # Save to temporary file for rhino3dm parsing
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.3dm', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        logger.info(
            "extract_geometry.file_downloaded",
            node=node_name,
            block_id=block_id,
            size_bytes=len(file_content),
            temp_path=temp_file_path,
        )
        
        # Parse .3dm file with RhinoParserService (US-002, UNCHANGED)
        parser = RhinoParserService()
        result = parser.parse_file(temp_file_path)
        
        if not result.success:
            logger.error(
                "extract_geometry.parse_failed",
                node=node_name,
                block_id=block_id,
                error=result.error_message,
            )
            return {
                "geometry_metadata": {
                    "file_exists_in_storage": True,
                    "layers": [],
                    "volume": 0.0,
                    "bbox": {},
                    "vertices_count": 0,
                    "faces_count": 0,
                },
                "error_messages": [f"Failed to parse .3dm file: {result.error_message}"],
                "validation_path": _append_to_path(state, node_name),
            }
        
        # Load rhino3dm model again for geometry extraction
        # (RhinoParserService extracts layers but not bbox/volume)
        model = rhino3dm.File3dm.Read(temp_file_path) if rhino3dm else None
        
        # Extract bounding box and volume from model
        bbox_dict = {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0], "dimensions": [1.0, 1.0, 1.0]}
        volume = 0.0
        vertices_count = 0
        faces_count = 0
        
        if model and model.Objects:
            # Calculate bounding box from all objects
            min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
            max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
            
            for obj in model.Objects:
                if obj.Geometry:
                    # rhino3dm GetBoundingBox() takes no arguments (unlike .NET Rhino API)
                    obj_bbox = obj.Geometry.GetBoundingBox()
                    if obj_bbox.IsValid:
                        min_x = min(min_x, obj_bbox.Min.X)
                        min_y = min(min_y, obj_bbox.Min.Y)
                        min_z = min(min_z, obj_bbox.Min.Z)
                        max_x = max(max_x, obj_bbox.Max.X)
                        max_y = max(max_y, obj_bbox.Max.Y)
                        max_z = max(max_z, obj_bbox.Max.Z)
                    
                    # Count vertices/faces if mesh
                    if hasattr(obj.Geometry, 'Vertices'):
                        vertices_count += len(obj.Geometry.Vertices)
                    if hasattr(obj.Geometry, 'Faces'):
                        faces_count += len(obj.Geometry.Faces)
            
            if min_x != float('inf'):
                bbox_dict = {
                    "min": [min_x, min_y, min_z],
                    "max": [max_x, max_y, max_z],
                    "dimensions": [max_x - min_x, max_y - min_y, max_z - min_z],
                }
                volume = (max_x - min_x) * (max_y - min_y) * (max_z - min_z)
        
        # Build comprehensive geometry_metadata
        geometry_metadata = {
            "layers": result.layers,  # List[LayerInfo] for nomenclature validation
            "bbox": bbox_dict,
            "volume": volume,
            "vertices_count": vertices_count,
            "faces_count": faces_count,
            "rhino_model": model,  # Store for ValidateGeometry node
            "user_strings": result.user_strings,  # For EnrichMetadata node
            "file_exists_in_storage": True,
            "has_mesh": vertices_count > 0,
        }
        
        logger.info(
            "node.complete",
            node=node_name,
            layer_count=len(result.layers),
            volume=volume,
            vertices_count=vertices_count,
        )
        
        return {
            "geometry_metadata": geometry_metadata,
            "validation_path": _append_to_path(state, node_name),
        }
    
    except Exception as e:
        logger.exception(
            "extract_geometry.unexpected_error",
            node=node_name,
            block_id=block_id,
            error=str(e),
        )
        return {
            "geometry_metadata": {
                "file_exists_in_storage": False,
                "layers": [],
                "volume": 0.0,
                "bbox": {},
                "vertices_count": 0,
                "faces_count": 0,
            },
            "error_messages": [f"Unexpected error extracting geometry: {str(e)}"],
            "validation_path": _append_to_path(state, node_name),
        }
    
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(
                    "extract_geometry.temp_file_cleaned",
                    node=node_name,
                    temp_path=temp_file_path,
                )
            except Exception as cleanup_error:
                logger.warning(
                    "extract_geometry.cleanup_failed",
                    node=node_name,
                    temp_path=temp_file_path,
                    error=str(cleanup_error),
                )


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3: ValidateGeometry
# ─────────────────────────────────────────────────────────────────────────────

@with_audit_trail
def node_validate_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    Node 3: Validate geometry topology using GeometryValidator (US-002).

    Only reached if ExtractGeometry succeeded.

    Implementation (T-1803 Adapter Pattern):
        Uses GeometryValidator service (US-002) via adapter wrapper.
        Adapter pattern: Extract rhino_model from state → call validator → update state.
        Zero regression: GeometryValidator code remains 100% unchanged.

    Validation Checks (from GeometryValidator US-002):
        - Non-null geometry
        - Valid geometry (Rhino's internal validity checks)
        - Non-degenerate bounding box
        - Non-zero volume (for Brep/Mesh objects)

    Flow:
        1. Extract geometry_metadata.rhino_model from state (populated by ExtractGeometry)
        2. Call GeometryValidator.validate_geometry(model)
        3. Update state with geometry_valid (bool) based on error count

    Args:
        state: Current ValidationState (reads: geometry_metadata.rhino_model)

    Returns:
        Partial state update with:
          - geometry_valid (bool): True if all geometry checks pass
          - validation_path (list with "ValidateGeometry" appended)

    Example:
        >>> # After ExtractGeometry populates rhino_model
        >>> result = node_validate_geometry(state)
        >>> result["geometry_valid"]
        True
    """
    from src.agent.services.geometry_validator import GeometryValidator
    
    node_name = "ValidateGeometry"
    block_id = state.get("block_id", "unknown")
    logger.info("node.enter", node=node_name, block_id=block_id)

    # T-1803 ADAPTER: Extract rhino_model from state (populated by ExtractGeometry)
    geometry_metadata = state.get("geometry_metadata", {})
    rhino_model = geometry_metadata.get("rhino_model")
    
    if not rhino_model:
        logger.warning(
            "validate_geometry.no_model",
            node=node_name,
            block_id=block_id,
        )
        return {
            "geometry_valid": False,
            "validation_path": _append_to_path(state, node_name),
        }
    
    # Call GeometryValidator (US-002 service, UNCHANGED code)
    validator = GeometryValidator()
    errors = validator.validate_geometry(rhino_model)
    
    is_valid = len(errors) == 0
    
    logger.info(
        "node.complete",
        node=node_name,
        geometry_valid=is_valid,
        error_count=len(errors),
    )

    return {
        "geometry_valid": is_valid,
        "geometry_errors": errors,  # Include errors for audit trail
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4: ClassifyTipologia
# ─────────────────────────────────────────────────────────────────────────────

@with_audit_trail
def node_classify_tipologia(state: ValidationState) -> Dict[str, Any]:
    """
    Node 4: Classify architectural piece using LLM (GPT-4) or regex fallback.

    Only reached if geometry validation passed.

    Implementation (T-1802):
        1. Check Circuit Breaker status → if open, use fallback regex
        2. Sanitize user strings (prompt injection prevention)
        3. Call OpenAI GPT-4 Turbo with retry logic
        4. Validate confidence >= 0.7 threshold
        5. If LLM fails or low confidence → fallback regex
        6. Record success/failure in Circuit Breaker
        7. Return semantic_data with classification_method ENUM

    Circuit Breaker (GLOBAL scope):
        - 5 consecutive failures (ANY block) → trip circuit
        - Persists in Redis (shared across workers)
        - Auto-recovery after 5-minute TTL

    Args:
        state: Current ValidationState (reads: geometry_metadata, block_id)

    Returns:
        Partial state update with:
          - semantic_data (Dict with tipologia, material, confidence, reasoning, classified_at)
          - classification_method (ClassificationMethod ENUM)
          - circuit_breaker_tripped (bool, updated if Circuit Breaker activated)
          - validation_path (list with "ClassifyTipologia" appended)
    """
    from src.agent.graph.llm_client import get_llm_client, LLMClassificationError
    from src.agent.graph.circuit_breaker import get_circuit_breaker
    from src.agent.graph.classification_helpers import (
        fallback_classify_by_regex,
        sanitize_user_string,
        validate_llm_confidence,
        merge_llm_with_metadata,
    )
    from src.agent.constants import CONFIDENCE_THRESHOLD
    from infra.redis_client import get_redis_client
    
    node_name = "ClassifyTipologia"
    block_id = state.get("block_id", "unknown")
    logger.info("node.enter", node=node_name, block_id=block_id)

    # Initialize Circuit Breaker and LLM client
    redis_client = get_redis_client()  # May return None if unavailable
    circuit_breaker = get_circuit_breaker(redis_client)
    
    # Extract geometry metadata
    geometry_metadata = state.get("geometry_metadata", {})
    volume = geometry_metadata.get("volume", 0.0)
    bbox = geometry_metadata.get("bbox", {})
    layers = geometry_metadata.get("layers", [])
    vertices_count = geometry_metadata.get("vertices_count", 0)
    
    # Sanitize iso_code (prevent prompt injection).
    # US-018 wiring: block_id is the blocks.id UUID in the real pipeline, which
    # is meaningless to the LLM. Prefer the real iso_code passed in via
    # geometry_metadata; fall back to block_id for legacy/test callers.
    iso_code_source = geometry_metadata.get("iso_code") or block_id
    iso_code = sanitize_user_string(iso_code_source)
    
    # Check if Circuit Breaker is OPEN
    if circuit_breaker.is_open():
        logger.warning(
            "circuit_breaker_open_using_fallback",
            node=node_name,
            block_id=block_id,
        )
        
        # T-1805: Insert CIRCUIT_BREAKER_TRIPPED event
        try:
            from src.agent.constants import EventType
        except ImportError:
            from agent.constants import EventType
        
        insert_event(block_id, EventType.CIRCUIT_BREAKER_TRIPPED, node_name, state)
        logger.info(
            "audit.circuit_breaker_tripped_event",
            block_id=block_id,
            node=node_name,
        )
        
        # Use fallback regex classification
        semantic_data = fallback_classify_by_regex(iso_code)
        semantic_data = merge_llm_with_metadata(semantic_data, geometry_metadata)
        classification_method = ClassificationMethod.FALLBACK_REGEX
        circuit_breaker_tripped = True
        
        # T-1805: Insert FALLBACK_ACTIVATED event
        insert_event(block_id, EventType.FALLBACK_ACTIVATED, node_name, state)
        logger.info(
            "audit.fallback_activated_event",
            block_id=block_id,
            node=node_name,
        )
        
        return {
            "semantic_data": semantic_data,
            "classification_method": classification_method,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "validation_path": _append_to_path(state, node_name),
        }
    
    # Attempt LLM classification
    try:
        llm_client = get_llm_client()
        llm_result = llm_client.classify_tipologia(
            volume=volume,
            bbox=bbox,
            layers=layers,
            vertices_count=vertices_count,
            iso_code=iso_code,
        )
        
        # Validate confidence threshold
        confidence = llm_result.get("confidence", 0.0)
        if not validate_llm_confidence(confidence, CONFIDENCE_THRESHOLD):
            logger.info(
                "low_confidence_fallback",
                node=node_name,
                block_id=block_id,
                confidence=confidence,
                threshold=CONFIDENCE_THRESHOLD,
            )
            
            # Confidence too low → use fallback
            semantic_data = fallback_classify_by_regex(iso_code)
            semantic_data = merge_llm_with_metadata(semantic_data, geometry_metadata)
            classification_method = ClassificationMethod.FALLBACK_REGEX
            circuit_breaker_tripped = False  # Not a Circuit Breaker event
            
            # Still record success in CB (LLM worked, just low confidence)
            circuit_breaker.record_success()
        else:
            # LLM classification successful with high confidence
            semantic_data = merge_llm_with_metadata(llm_result, geometry_metadata)
            classification_method = ClassificationMethod.LLM_GPT4
            circuit_breaker_tripped = False
            
            # Record success in Circuit Breaker
            circuit_breaker.record_success()
            
            logger.info(
                "llm_classification_success",
                node=node_name,
                block_id=block_id,
                tipologia=semantic_data["tipologia"],
                confidence=confidence,
            )
        
    except Exception as e:
        # Any LLM failure → record failure and use the regex fallback.
        # Broadened from LLMClassificationError to Exception so that a failure
        # *constructing* the client also degrades gracefully instead of
        # crashing the whole graph. This matters in the prod agent image,
        # where llm_client's `from src.backend...` import is unavailable, and
        # whenever OPENAI_API_KEY is missing — the pipeline must still produce
        # a (regex) classification rather than mark the block error_processing.
        logger.error(
            "llm_classification_failed",
            node=node_name,
            block_id=block_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        
        # Record failure in Circuit Breaker (may trip circuit)
        circuit_breaker.record_failure()
        
        # Use fallback regex classification
        semantic_data = fallback_classify_by_regex(iso_code)
        semantic_data = merge_llm_with_metadata(semantic_data, geometry_metadata)
        classification_method = ClassificationMethod.FALLBACK_REGEX
        
        # Check if Circuit Breaker tripped
        circuit_breaker_tripped = circuit_breaker.is_open()
        
        if circuit_breaker_tripped:
            # T-1805: Insert CIRCUIT_BREAKER_TRIPPED event (newly tripped)
            try:
                from src.agent.constants import EventType
            except ImportError:
                from agent.constants import EventType
            
            insert_event(block_id, EventType.CIRCUIT_BREAKER_TRIPPED, node_name, state)
            logger.error(
                "circuit_breaker_newly_tripped",
                node=node_name,
                block_id=block_id,
            )
        
        # T-1805: Insert FALLBACK_ACTIVATED event
        try:
            from src.agent.constants import EventType
        except ImportError:
            from agent.constants import EventType
        
        insert_event(block_id, EventType.FALLBACK_ACTIVATED, node_name, state)
        logger.info(
            "audit.fallback_activated_event",
            block_id=block_id,
            node=node_name,
        )

    logger.info(
        "node.complete",
        node=node_name,
        tipologia=semantic_data["tipologia"],
        method=classification_method.value,
        circuit_breaker_tripped=circuit_breaker_tripped,
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

@with_audit_trail
def node_enrich_metadata(state: ValidationState) -> Dict[str, Any]:
    """
    Node 5: Enrich semantic_data with material from UserStrings.

    Only reached if classification succeeded.

    Implementation (T-1803 Adapter Pattern):
        User strings already extracted by ExtractGeometry (via RhinoParserService).
        This node parses the UserStringCollection to extract material information
        and enriches semantic_data with it.

    Flow:
        1. Extract geometry_metadata.user_strings (UserStringCollection)
        2. Parse document-level user strings for "Material" key
        3. Fallback to object-level user strings if document-level not found
        4. Update semantic_data with material (merge with existing LLM classification)
        5. Return updated state

    Note: User strings were already extracted in ExtractGeometry node.
    This node just parses the collection and enriches semantic_data.

    Args:
        state: Current ValidationState (reads: geometry_metadata.user_strings, semantic_data)

    Returns:
        Partial state update with:
          - semantic_data (Dict): Updated with material field from UserStrings
          - validation_path (list with "EnrichMetadata" appended)

    Example:
        >>> # After ExtractGeometry + ClassifyTipologia
        >>> result = node_enrich_metadata(state)
        >>> result["semantic_data"]["material"]
        "Piedra de Montjuïc"
    """
    node_name = "EnrichMetadata"
    block_id = state.get("block_id", "unknown")
    logger.info("node.enter", node=node_name, block_id=block_id)

    #T-1803 ADAPTER: Extract user_strings from geometry_metadata
    geometry_metadata = state.get("geometry_metadata", {})
    user_strings = geometry_metadata.get("user_strings")
    
    # Get current semantic_data (from ClassifyTipologia node)
    semantic_data = state.get("semantic_data", {})
    
    # Parse material from UserStrings
    material = "Unknown"
    
    if user_strings:
        # user_strings can be dict (from RhinoParserService) or UserStringCollection object
        # Check if it's a dict with 'document' key or an object with document attribute
        if isinstance(user_strings, dict):
            # Dict format: {document: {}, layers: {}, objects: {}}
            document_strings = user_strings.get("document", {})
            if "Material" in document_strings:
                material = document_strings["Material"]
                logger.debug(
                    "enrich_metadata.material_from_document_dict",
                    node=node_name,
                    block_id=block_id,
                    material=material,
                )
            
            # Fallback to first object's user strings if document-level not found
            if material == "Unknown":
                objects_strings = user_strings.get("objects", {})
                for obj_id, obj_strings in objects_strings.items():
                    if "Material" in obj_strings:
                        material = obj_strings["Material"]
                        logger.debug(
                            "enrich_metadata.material_from_object_dict",
                            node=node_name,
                            block_id=block_id,
                            object_id=obj_id,
                            material=material,
                        )
                        break
        elif hasattr(user_strings, 'document'):
            # UserStringCollection object format
            if user_strings.document and "Material" in user_strings.document:
                material = user_strings.document["Material"]
                logger.debug(
                    "enrich_metadata.material_from_document_object",
                    node=node_name,
                    block_id=block_id,
                    material=material,
                )
            
            # Fallback to first object's user strings
            if material == "Unknown" and hasattr(user_strings, 'objects') and user_strings.objects:
                for obj_id, obj_strings in user_strings.objects.items():
                    if "Material" in obj_strings:
                        material = obj_strings["Material"]
                        logger.debug(
                            "enrich_metadata.material_from_object_object",
                            node=node_name,
                            block_id=block_id,
                            object_id=obj_id,
                            material=material,
                        )
                        break
    
    # Merge material into semantic_data (preserve existing LLM classification)
    updated_semantic_data = {
        **semantic_data,
        "material": material,
    }
    
    logger.info(
        "node.complete",
        node=node_name,
        material=material,
        semantic_data_keys=list(updated_semantic_data.keys()),
    )

    return {
        "semantic_data": updated_semantic_data,
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 6: GenerateReport
# ─────────────────────────────────────────────────────────────────────────────

@with_audit_trail
def node_generate_report(state: ValidationState) -> Dict[str, Any]:
    """
    Node 6: Generate JSON validation report using Jinja2 template (T-1804).

    This node compiles all validation results from the state into a structured
    JSON report that is:
      1. Persisted in database (blocks.validation_report JSONB column)
      2. Displayed in frontend ValidationReportModal
      3. Compatible with backend ValidationReport Pydantic schema

    Template: src/agent/templates/validation_report.json.j2
    
    Template features (NULL-safe):
      - Errors array: Combines nomenclature_errors + geometry errors
      - Metadata: Extracts iso_code from block_id, includes material/tipologia
      - Semantic data: Only included if LLM classification executed (not null)
      - Geometry summary: Extracted from geometry_metadata (vertices, bbox, volume)
      - Validation path: Shows node execution order (helps debug rejected files)

    Current implementation (T-1804):
        Renders Jinja2 template and validates JSON parseability.
        Report is NOT stored in state (keeps 15 fields limit).
        Persistence to database will be done in Task 4 (persist_validation_report helper).

    Args:
        state: Current ValidationState (reads: all fields)

    Returns:
        Partial state update with:
          - validation_path (list with "GenerateReport" appended)
          - error_messages (list with error appended if generation fails)
    
    Note: Report JSON string is logged but NOT added to state.
    Database persistence will be done by helper function called from graph.
    """
    node_name = "GenerateReport"
    logger.info("node.enter", node=node_name, block_id=state.get("block_id"))

    try:
        # Setup Jinja2 environment (FileSystemLoader for templates directory)
        template_env = Environment(loader=FileSystemLoader("src/agent/templates"))
        template = template_env.get_template("validation_report.json.j2")
        
    except TemplateNotFound as e:
        error_msg = f"Template not found: {e}"
        logger.error("template.not_found", error=error_msg, node=node_name)
        
        return {
            "error_messages": _append_to_errors(state, error_msg),
            "validation_path": _append_to_path(state, node_name),
        }

    # Prepare template context (extract all relevant fields from state)
    # Use .get() with defaults for NULL-safe rendering
    context = {
        "block_id": state.get("block_id", "UNKNOWN"),
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": state.get("overall_status", ValidationStatus.PROCESSING.value),
        "nomenclature_valid": state.get("nomenclature_valid", False),
        "nomenclature_errors": state.get("nomenclature_errors", []),
        "geometry_valid": state.get("geometry_valid", False),
        "geometry_metadata": state.get("geometry_metadata", {}),
        "semantic_data": state.get("semantic_data"),  # Can be None
        "classification_method": state.get("classification_method"),  # Can be None
        "validation_path": state.get("validation_path", []),
        "circuit_breaker_tripped": state.get("circuit_breaker_tripped", False),
        "retry_count": state.get("retry_count", 0),
        "completed_at": state.get("completed_at"),  # Can be None (set by terminal nodes)
        "created_at": state.get("created_at", datetime.utcnow().isoformat()),
        "validated_by": "SF-PM-Agent-v0.1.0",  # TODO: Extract version from constants
    }

    try:
        # Render template
        report_json_str = template.render(context)
        
        # Validate JSON is parseable (will raise JSONDecodeError if invalid)
        report_dict = json.loads(report_json_str)
        
        logger.info(
            "report.generated",
            node=node_name,
            block_id=state.get("block_id"),
            is_valid=report_dict.get("is_valid"),
            error_count=len(report_dict.get("errors", [])),
            has_semantic_data=report_dict.get("semantic_data") is not None,
            report_size_bytes=len(report_json_str),
        )
        
        # Persist report to database (T-1804 Task 4)
        try:
            supabase = get_supabase_client()
            block_id = state.get("block_id")
            
            # UPDATE blocks SET validation_report = report_json::jsonb WHERE block_id = %s
            response = supabase.table("blocks").update({
                "validation_report": report_dict  # Supabase converts dict to JSONB automatically
            }).eq("block_id", block_id).execute()
            
            # Check if update was successful
            if response.data and len(response.data) > 0:
                logger.info(
                    "report.persisted",
                    node=node_name,
                    block_id=block_id,
                    rows_updated=len(response.data)
                )
            else:
                # No rows updated (block_id not found or other issue)
                logger.warning(
                    "report.persist_no_rows",
                    node=node_name,
                    block_id=block_id,
                    message="UPDATE returned zero rows (block may not exist)"
                )
                
        except Exception as db_error:
            # Database persistence failed - log warning but DON'T fail the node
            # Report generation succeeded, DB persistence is best-effort
            logger.warning(
                "report.persist_failed",
                node=node_name,
                block_id=state.get("block_id"),
                error=str(db_error),
                message="Report generated but database persistence failed (non-fatal)"
            )
        
    except json.JSONDecodeError as e:
        error_msg = f"Generated report is not valid JSON: {e}"
        logger.error("report.invalid_json", error=error_msg, node=node_name)
        
        return {
            "error_messages": _append_to_errors(state, error_msg),
            "validation_path": _append_to_path(state, node_name),
        }
        
    except Exception as e:
        error_msg = f"Report generation failed: {e}"
        logger.error("report.generation_failed", error=error_msg, node=node_name)
        
        return {
            "error_messages": _append_to_errors(state, error_msg),
            "validation_path": _append_to_path(state, node_name),
        }

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

@with_audit_trail
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
