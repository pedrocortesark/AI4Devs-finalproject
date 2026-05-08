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
    Node 1: Validate that all layer names comply with ISO-19650 pattern.

    This is the FIRST node in the graph and acts as a gatekeeper.
    If nomenclature fails, the conditional edge routes directly to REJECTED
    without running the expensive nodes (geometry parsing, LLM calls).

    Implementation (T-1803 Adapter Pattern):
        Uses NomenclatureValidator service (US-002) via adapter wrapper.
        Adapter pattern: Extract layers from state → call validator → update state.
        Zero regression: NomenclatureValidator code remains 100% unchanged.

    Flow:
        1. Extract geometry_metadata.layers from state (populated by ExtractGeometry)
        2. Call NomenclatureValidator.validate_nomenclature(layers)
        3. Update state with nomenclature_valid (bool) and nomenclature_errors (list)

    Note: This node depends on ExtractGeometry running FIRST to populate layers.
    Graph ordering ensures ExtractGeometry → ValidateNomenclature sequence.

    Args:
        state: Current ValidationState (reads: geometry_metadata.layers)

    Returns:
        Partial state update with:
          - nomenclature_valid (bool): True if all layers match ISO-19650 pattern
          - nomenclature_errors (List[ValidationErrorItem]): Errors for invalid layers
          - validation_path (list with "ValidateNomenclature" appended)

    Example:
        >>> state = {"geometry_metadata": {"layers": [LayerInfo(name="SF-C12-D-001", index=0)]}}
        >>> result = node_validate_nomenclature(state)
        >>> result["nomenclature_valid"]
        True
    """
    from src.agent.services.nomenclature_validator import NomenclatureValidator
    
    node_name = "ValidateNomenclature"
    block_id = state.get("block_id", "unknown")
    logger.info("node.enter", node=node_name, block_id=block_id)

    # T-1803 ADAPTER: Extract layers from state (populated by ExtractGeometry)
    geometry_metadata = state.get("geometry_metadata", {})
    layers = geometry_metadata.get("layers", [])
    
    logger.debug(
        "nomenclature_adapter.layer_count",
        node=node_name,
        block_id=block_id,
        layer_count=len(layers),
    )

    # Call NomenclatureValidator (US-002 service, UNCHANGED code)
    validator = NomenclatureValidator()
    errors = validator.validate_nomenclature(layers)
    
    is_valid = len(errors) == 0

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
                    obj_bbox = obj.Geometry.GetBoundingBox(False)
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
        "validation_path": _append_to_path(state, node_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4: ClassifyTipologia
# ─────────────────────────────────────────────────────────────────────────────

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
    
    # Sanitize iso_code (prevent prompt injection)
    iso_code = sanitize_user_string(block_id)
    
    # Check if Circuit Breaker is OPEN
    if circuit_breaker.is_open():
        logger.warning(
            "circuit_breaker_open_using_fallback",
            node=node_name,
            block_id=block_id,
        )
        
        # Use fallback regex classification
        semantic_data = fallback_classify_by_regex(iso_code)
        semantic_data = merge_llm_with_metadata(semantic_data, geometry_metadata)
        classification_method = ClassificationMethod.FALLBACK_REGEX
        circuit_breaker_tripped = True
        
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
        
    except LLMClassificationError as e:
        # LLM failed → record failure and use fallback
        logger.error(
            "llm_classification_failed",
            node=node_name,
            block_id=block_id,
            error=str(e),
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
            logger.error(
                "circuit_breaker_newly_tripped",
                node=node_name,
                block_id=block_id,
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

    # T-1803 ADAPTER: Extract user_strings from geometry_metadata
    geometry_metadata = state.get("geometry_metadata", {})
    user_strings = geometry_metadata.get("user_strings")
    
    # Get current semantic_data (from ClassifyTipologia node)
    semantic_data = state.get("semantic_data", {})
    
    # Parse material from UserStrings
    material = "Unknown"
    
    if user_strings:
        # Try document-level user strings first
        if hasattr(user_strings, 'document') and user_strings.document:
            material = user_strings.document.get("Material", material)
            logger.debug(
                "enrich_metadata.material_from_document",
                node=node_name,
                block_id=block_id,
                material=material,
            )
        
        # Fallback to first object's user strings if document-level not found
        if material == "Unknown" and hasattr(user_strings, 'objects') and user_strings.objects:
            # Get first object's user strings
            for obj_id, obj_strings in user_strings.objects.items():
                if "Material" in obj_strings:
                    material = obj_strings["Material"]
                    logger.debug(
                        "enrich_metadata.material_from_object",
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
