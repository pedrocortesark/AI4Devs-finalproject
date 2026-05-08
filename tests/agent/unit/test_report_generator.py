"""
Unit Tests for node_generate_report (T-1804)

WHAT WE'RE TESTING
==================
These tests verify the GenerateReport node which uses Jinja2 templates to create
structured JSON validation reports. The node:
  1. Renders validation_report.json.j2 template with state data
  2. Validates generated JSON is parseable
  3. Persists report to Supabase blocks.validation_report JSONB column
  4. Handles errors gracefully (template not found, invalid JSON, DB failures)

We're validating:
  - Report structure matches backend ValidationReport schema
  - NULL-safe rendering (semantic_data can be None)
  - Error arrays combine nomenclature + geometry errors
  - Material defaults to "Unknown" if missing from user_strings
  - Special characters in iso_code are handled correctly
  - Boolean values render as JSON true/false (not Python True/False)
  - Database persistence is best-effort (node succeeds even if DB fails)

T-1804 REQUIREMENTS (8 test scenarios)
=======================================
  HP-01: Happy path complete report (nomenclature OK + geometry OK + LLM classification)
  HP-02: Semantic_data present when classification_method = LLM_GPT4
  EC-01: Report without LLM (semantic_data=null, early rejection path)
  EC-02: Rejected by nomenclature (errors populated with nomenclature_errors)
  EC-03: Rejected by geometry (errors populated with geometry failure message)
  EC-04: Material = "Unknown" if user_strings missing Material key
  INT-01: JSONB schema compliance (ValidationReport.model_validate() succeeds)
  INT-02: Special characters in iso_code (accents, spaces, hyphens)

Author: AI Agent (T-1804-AGENT)
Created: 2026-05-08
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

try:
    from src.agent.graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from src.agent.graph.nodes import node_generate_report
except ImportError:
    from graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from graph.nodes import node_generate_report


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_supabase():
    """
    Mock Supabase client for all report generator tests.
    
    The node calls get_supabase_client().table("blocks").update(...).eq(...).execute()
    We mock this to avoid real DB calls and verify persistence logic.
    """
    with patch("src.agent.graph.nodes.get_supabase_client") as mock_get_supabase:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        
        # Setup call chain: client.table("blocks").update({...}).eq("block_id", "...").execute()
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        
        # Default: successful update returns 1 row
        mock_eq.execute.return_value = MagicMock(data=[{"block_id": "test-block"}])
        
        mock_get_supabase.return_value = mock_client
        
        yield mock_client


@pytest.fixture
def happy_path_state():
    """
    Happy path state: nomenclature OK + geometry OK + LLM classification.
    
    Expected report:
      - is_valid: true
      - errors: []
      - semantic_data: {tipologia, material, confidence}
      - geometry_summary: {volume, bbox, vertices_count, faces_count, has_mesh}
    """
    state = make_initial_state(block_id="GLPER.B-PAE0720.0701")
    
    # Override created_at
    state["created_at"] = datetime(2026, 5, 8, 10, 30).isoformat()
    
    # Simulate successful validation pipeline
    state.update({
        "overall_status": ValidationStatus.VALIDATED.value,
        "nomenclature_valid": True,
        "nomenclature_errors": [],
        "geometry_valid": True,
        "geometry_metadata": {
            "volume": 1234.567,
            "bbox": {"min": [0, 0, 0], "max": [100, 50, 80]},
            "vertices_count": 8542,
            "faces_count": 16380,
            "has_mesh": True,
        },
        "semantic_data": {
            "tipologia": "dovela",
            "material": "Piedra de Montjuïc",
            "confidence": 0.87,
            "reasoning": "Classified by GPT-4",
        },
        "classification_method": ClassificationMethod.LLM_GPT4.value,
        "validation_path": ["ValidateNomenclature", "ExtractGeometry", "ValidateGeometry", "ClassifyTipologia", "EnrichMetadata"],
        "circuit_breaker_tripped": False,
        "retry_count": 0,
    })
    
    return state


@pytest.fixture
def rejected_nomenclature_state():
    """
    Rejected by nomenclature: invalid layer name.
    
    Expected report:
      - is_valid: false
      - errors: [{category: "nomenclature", message: "..."}]
      - semantic_data: null (LLM never called)
      - classification_method: null
    """
    state = make_initial_state(block_id="GLPER.B-INVALID.NAME")
    
    # Override created_at
    state["created_at"] = datetime(2026, 5, 8, 10, 35).isoformat()
    
    state.update({
        "overall_status": ValidationStatus.REJECTED.value,
        "nomenclature_valid": False,
        "nomenclature_errors": [
            "Layer 'invalid-name' does not match ISO-19650 pattern",
            "Layer 'wrong-format' missing project code"
        ],
        "geometry_valid": False,  # Never validated (early rejection)
        "geometry_metadata": {},
        "semantic_data": None,
        "classification_method": None,
        "validation_path": ["ValidateNomenclature"],
        "circuit_breaker_tripped": False,
        "retry_count": 0,
    })
    
    return state


@pytest.fixture
def rejected_geometry_state():
    """
    Rejected by geometry: nomenclature OK but mesh invalid.
    
    Expected report:
      - is_valid: false
      - errors: [{category: "geometry", message: "Geometry validation failed..."}]
      - semantic_data: null (LLM never called because geometry failed)
    """
    state = make_initial_state(block_id="GLPER.B-PAE0720.0999")
    
    # Override created_at
    state["created_at"] = datetime(2026, 5, 8, 10, 40).isoformat()
    
    state.update({
        "overall_status": ValidationStatus.REJECTED.value,
        "nomenclature_valid": True,
        "nomenclature_errors": [],
        "geometry_valid": False,
        "geometry_metadata": {
            "volume": 0.0,
            "bbox": {},
            "vertices_count": 0,
            "faces_count": 0,
            "has_mesh": False,
        },
        "semantic_data": None,
        "classification_method": None,
        "validation_path": ["ValidateNomenclature", "ExtractGeometry", "ValidateGeometry"],
        "circuit_breaker_tripped": False,
        "retry_count": 0,
    })
    
    return state


@pytest.fixture
def material_unknown_state():
    """
    Material = "Unknown" because user_strings missing Material key.
    
    Expected report:
      - semantic_data.material: "Unknown" (default from template)
    """
    state = make_initial_state(block_id="GLPER.B-PAE0720.0702")
    
    # Override created_at
    state["created_at"] = datetime(2026, 5, 8, 10, 45).isoformat()
    
    state.update({
        "overall_status": ValidationStatus.VALIDATED.value,
        "nomenclature_valid": True,
        "nomenclature_errors": [],
        "geometry_valid": True,
        "geometry_metadata": {
            "volume": 890.123,
            "bbox": {"min": [0, 0, 0], "max": [50, 50, 50]},
            "vertices_count": 4200,
            "faces_count": 8100,
            "has_mesh": True,
        },
        "semantic_data": {
            "tipologia": "capitel",
            # Material key missing
            "confidence": 0.78,
        },
        "classification_method": ClassificationMethod.LLM_GPT4.value,
        "validation_path": ["ValidateNomenclature", "ExtractGeometry", "ValidateGeometry", "ClassifyTipologia", "EnrichMetadata"],
    })
    
    return state


@pytest.fixture
def special_chars_state():
    """
    Special characters in iso_code: accents, hyphens, spaces.
    
    Expected report:
      - Handles UTF-8 correctly
      - JSON escaping of special chars
    """
    state = make_initial_state(block_id="GLPER.B-PÀE0720.07-03")  # Accent + hyphen
    
    # Override created_at
    state["created_at"] = datetime(2026, 5, 8, 10, 50).isoformat()
    
    state.update({
        "overall_status": ValidationStatus.VALIDATED.value,
        "nomenclature_valid": True,
        "nomenclature_errors": [],
        "geometry_valid": True,
        "geometry_metadata": {
            "volume": 456.789,
            "bbox": {"min": [0, 0, 0], "max": [30, 30, 30]},
            "vertices_count": 2100,
            "faces_count": 4050,
            "has_mesh": True,
        },
        "semantic_data": {
            "tipologia": "arcó",  # Accent in tipologia
            "material": "Pedra de Montjuïc",  # Accent in material
            "confidence": 0.91,
        },
        "classification_method": ClassificationMethod.LLM_GPT4.value,
        "validation_path": ["ValidateNomenclature", "ExtractGeometry", "ValidateGeometry", "ClassifyTipologia", "EnrichMetadata"],
    })
    
    return state


# ─────────────────────────────────────────────────────────────────────────────
# HP-01: Happy Path Complete Report
# ─────────────────────────────────────────────────────────────────────────────

def test_hp01_happy_path_complete_report(happy_path_state, mock_supabase):
    """
    HP-01: Generate complete report for fully validated block.
    
    Verifies:
      - is_valid: true
      - errors: [] (empty)
      - semantic_data present
      - geometry_summary present
      - validation_path correct
      - Report is valid JSON
      - Database persistence called
    """
    result = node_generate_report(happy_path_state)
    
    # Node should succeed (no errors)
    assert "validation_path" in result
    assert result["validation_path"][-1] == "GenerateReport"
    assert "error_messages" not in result or result["error_messages"] == []
    
    # Verify database persistence was called
    mock_supabase.table.assert_called_once_with("blocks")
    mock_table = mock_supabase.table.return_value
    
    # Extract report_dict from update call
    update_call = mock_table.update.call_args
    assert update_call is not None
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify report structure
    assert report_dict["is_valid"] is True
    assert report_dict["overall_status"] == "validated"
    assert report_dict["errors"] == []
    
    # Verify metadata
    assert report_dict["metadata"]["iso_code"] == "PAE0720.0701"
    assert report_dict["metadata"]["block_id"] == "GLPER.B-PAE0720.0701"
    assert report_dict["metadata"]["material"] == "Piedra de Montjuïc"
    assert report_dict["metadata"]["tipologia"] == "dovela"
    
    # Verify semantic_data
    assert report_dict["semantic_data"] is not None
    assert report_dict["semantic_data"]["tipologia"] == "dovela"
    assert report_dict["semantic_data"]["confidence"] == 0.87
    
    # Verify geometry_summary
    assert report_dict["geometry_summary"]["volume"] == 1234.567
    assert report_dict["geometry_summary"]["vertices_count"] == 8542
    assert report_dict["geometry_summary"]["has_mesh"] is True


# ─────────────────────────────────────────────────────────────────────────────
# HP-02: Semantic Data Present When LLM Used
# ─────────────────────────────────────────────────────────────────────────────

def test_hp02_semantic_data_present_when_llm_used(happy_path_state, mock_supabase):
    """
    HP-02: semantic_data field is NOT null when classification_method = LLM_GPT4.
    
    Verifies:
      - semantic_data: {tipologia, material, confidence, reasoning}
      - classification_method: "llm_gpt4"
    """
    result = node_generate_report(happy_path_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify semantic_data is present
    assert report_dict["semantic_data"] is not None
    assert "tipologia" in report_dict["semantic_data"]
    assert "material" in report_dict["semantic_data"]
    assert "confidence" in report_dict["semantic_data"]
    
    # Verify classification_method
    assert report_dict["metadata"]["classification_method"] == "llm_gpt4"


# ─────────────────────────────────────────────────────────────────────────────
# EC-01: Report Without LLM (Early Rejection)
# ─────────────────────────────────────────────────────────────────────────────

def test_ec01_report_without_llm_early_rejection(rejected_nomenclature_state, mock_supabase):
    """
    EC-01: semantic_data = null when block rejected early (before LLM classification).
    
    Verifies:
      - semantic_data: null
      - classification_method: null
      - is_valid: false
    """
    result = node_generate_report(rejected_nomenclature_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify semantic_data is null
    assert report_dict["semantic_data"] is None
    
    # Verify classification_method is null
    assert report_dict["metadata"]["classification_method"] is None
    
    # Verify is_valid is false
    assert report_dict["is_valid"] is False


# ─────────────────────────────────────────────────────────────────────────────
# EC-02: Rejected by Nomenclature (Errors Populated)
# ─────────────────────────────────────────────────────────────────────────────

def test_ec02_rejected_by_nomenclature_errors_populated(rejected_nomenclature_state, mock_supabase):
    """
    EC-02: errors array populated with nomenclature_errors when nomenclature_valid = False.
    
    Verifies:
      - errors: [{category: "nomenclature", message: "..."}]
      - Error count = len(nomenclature_errors)
    """
    result = node_generate_report(rejected_nomenclature_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify errors array
    assert len(report_dict["errors"]) == 2
    
    # Verify all errors have category "nomenclature"
    for error in report_dict["errors"]:
        assert error["category"] == "nomenclature"
        assert "message" in error
        assert error["target"] is None
    
    # Verify error messages match state
    error_messages = [e["message"] for e in report_dict["errors"]]
    assert "Layer 'invalid-name' does not match ISO-19650 pattern" in error_messages
    assert "Layer 'wrong-format' missing project code" in error_messages


# ─────────────────────────────────────────────────────────────────────────────
# EC-03: Rejected by Geometry (Geometry Error)
# ─────────────────────────────────────────────────────────────────────────────

def test_ec03_rejected_by_geometry(rejected_geometry_state, mock_supabase):
    """
    EC-03: errors array contains geometry error when geometry_valid = False.
    
    Verifies:
      - errors: [{category: "geometry", message: "Geometry validation failed..."}]
      - nomenclature_errors empty (nomenclature was OK)
    """
    result = node_generate_report(rejected_geometry_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify errors array has 1 geometry error
    assert len(report_dict["errors"]) == 1
    
    error = report_dict["errors"][0]
    assert error["category"] == "geometry"
    assert "Geometry validation failed" in error["message"]
    assert error["target"] is None


# ─────────────────────────────────────────────────────────────────────────────
# EC-04: Material = "Unknown" If Missing
# ─────────────────────────────────────────────────────────────────────────────

def test_ec04_material_defaults_to_unknown(material_unknown_state, mock_supabase):
    """
    EC-04: material = "Unknown" if user_strings missing Material key.
    
    Verifies:
      - semantic_data.material: "Unknown" (template default)
    """
    result = node_generate_report(material_unknown_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify material defaults to "Unknown"
    assert report_dict["semantic_data"]["material"] == "Unknown"
    
    # But tipologia should still be present
    assert report_dict["semantic_data"]["tipologia"] == "capitel"


# ─────────────────────────────────────────────────────────────────────────────
# INT-01: JSONB Schema Compliance
# ─────────────────────────────────────────────────────────────────────────────

def test_int01_jsonb_schema_compliance(happy_path_state, mock_supabase):
    """
    INT-01: Generated report conforms to backend ValidationReport schema structure.
    
    Verifies:
      - All required fields present: is_valid, errors, metadata, validated_at, validated_by
      - Field types correct: is_valid (bool), errors (list), metadata (dict)
    """
    result = node_generate_report(happy_path_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify required fields present
    required_fields = ["is_valid", "errors", "metadata", "validated_at", "validated_by"]
    for field in required_fields:
        assert field in report_dict, f"Missing required field: {field}"
    
    # Verify field types
    assert isinstance(report_dict["is_valid"], bool)
    assert isinstance(report_dict["errors"], list)
    assert isinstance(report_dict["metadata"], dict)
    assert isinstance(report_dict["validated_by"], str)
    
    # Verify metadata subfields
    assert "iso_code" in report_dict["metadata"]
    assert "block_id" in report_dict["metadata"]
    assert "tipologia" in report_dict["metadata"]
    assert "material" in report_dict["metadata"]


# ─────────────────────────────────────────────────────────────────────────────
# INT-02: Special Characters Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_int02_special_characters_in_iso_code(special_chars_state, mock_supabase):
    """
    INT-02: Special characters (accents, hyphens) in iso_code handled correctly.
    
    Verifies:
      - UTF-8 encoding preserved
      - JSON escaping correct
      - Report is valid JSON
    """
    result = node_generate_report(special_chars_state)
    
    # Extract report from DB call
    update_call = mock_supabase.table.return_value.update.call_args
    report_dict = update_call[0][0]["validation_report"]
    
    # Verify special characters preserved
    assert report_dict["metadata"]["iso_code"] == "PÀE0720.07-03"
    assert report_dict["semantic_data"]["tipologia"] == "arcó"
    assert report_dict["semantic_data"]["material"] == "Pedra de Montjuïc"
    
    # Verify report can be serialized to JSON (UTF-8 compatible)
    try:
        json_str = json.dumps(report_dict, ensure_ascii=False)
        reparsed = json.loads(json_str)
        
        # Verify special chars survived round-trip
        assert reparsed["metadata"]["iso_code"] == "PÀE0720.07-03"
        
    except (TypeError, ValueError) as e:
        pytest.fail(f"Report with special characters is not valid JSON: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLING: Template Not Found
# ─────────────────────────────────────────────────────────────────────────────

def test_error_template_not_found(happy_path_state, mock_supabase):
    """
    Error handling: TemplateNotFound exception logged and node returns error.
    
    Verifies:
      - error_messages appended
      - validation_path still updated
      - Database NOT called (report generation failed)
    """
    from jinja2 import TemplateNotFound
    
    with patch("src.agent.graph.nodes.Environment") as mock_env_class:
        # Create a mock environment that raises TemplateNotFound
        mock_env = MagicMock()
        mock_env.get_template.side_effect = TemplateNotFound("validation_report.json.j2")
        mock_env_class.return_value = mock_env
        
        result = node_generate_report(happy_path_state)
    
    # Verify error handling
    assert "error_messages" in result
    assert len(result["error_messages"]) > 0
    assert "Template not found" in result["error_messages"][-1]
    
    # Verify validation_path still updated
    assert "validation_path" in result
    assert result["validation_path"][-1] == "GenerateReport"
    
    # Verify database NOT called (report generation failed)
    mock_supabase.table.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLING: Database Persistence Failure (Non-Fatal)
# ─────────────────────────────────────────────────────────────────────────────

def test_error_database_persistence_non_fatal(happy_path_state, mock_supabase):
    """
    Error handling: Database persistence failure does NOT fail the node (best-effort).
    
    Verifies:
      - Report generation succeeds
      - Database error logged as WARNING
      - error_messages NOT appended (DB failure is non-fatal)
      - validation_path updated normally
    """
    # Simulate database error
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("DB connection timeout")
    
    result = node_generate_report(happy_path_state)
    
    # Verify node succeeded despite DB failure
    assert "validation_path" in result
    assert result["validation_path"][-1] == "GenerateReport"
    
    # Verify error_messages NOT set (DB failure is non-fatal)
    assert "error_messages" not in result or result["error_messages"] == []
