"""
Integration Tests for StateGraph Validators (T-1803)

WHAT WE'RE TESTING
==================
These tests verify that the Adapter Pattern integration works correctly:
  - Adapters call US-002 validators correctly
  - State transformations preserve data integrity
  - Fail-fast routing works with real validators
  - Full happy path populates semantic_data correctly

Focus: Integration between StateGraph adapters and US-002 validators.

T-1803 TEST SCENARIOS (5 integration tests)
============================================
  INT-01: Nomenclature OK → extract_geometry executed (validates flow)
  INT-02: Nomenclature FAIL → extract_geometry NO ejecutado (fail-fast skip)
  INT-03: Geometry OK → enrich_metadata executed
  INT-04: Geometry FAIL → enrich_metadata NO ejecutado (fail-fast skip)
  INT-05: Full happy path → estado VALIDATED, semantic_data populated

These tests use MOCKED Supabase Storage and rhino3dm to avoid external dependencies,
but use REAL validators (NomenclatureValidator, GeometryValidator, UserStringExtractor).

Author: AI Agent (T-1803-AGENT)
Created: 2026-05-08
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
from uuid import uuid4

try:
    from src.agent.graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from src.agent.graph.graph import create_validation_graph
    from src.agent.models import LayerInfo, UserStringCollection
except ImportError:
    from graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from graph.graph import create_validation_graph
    from models import LayerInfo, UserStringCollection


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_valid_3dm_file():
    """
    Mock .3dm file content (bytes) for Supabase Storage download.
    Returns valid .3dm file signature for tests.
    """
    # Real .3dm files start with this signature
    return b'\x00\x00\x00\x00\x00\x00\x00\x00' + b'\x00' * 1000


@pytest.fixture
def mock_rhino_model_valid():
    """
    Mock rhino3dm.File3dm object with VALID geometry.
    
    Returns a mock model with:
      - 2 valid layers (SF-C12-D-001, SF-C12-CA-002)
      - 2 objects with valid geometry (non-null, valid, non-degenerate bbox)
      - User strings with Material="Piedra de Montjuïc"
    """
    mock_model = MagicMock()
    
    # Mock layers (VALID nomenclature)
    layer1 = MagicMock()
    layer1.Name = "SF-C12-D-001"
    layer1.Visible = True
    layer1.Color = (255, 128, 0, 255)  # ARGB tuple
    
    layer2 = MagicMock()
    layer2.Name = "SF-C12-CA-002"
    layer2.Visible = True
    layer2.Color = (255, 64, 128, 255)
    
    mock_model.Layers = [layer1, layer2]
    
    # Mock objects with VALID geometry
    obj1 = MagicMock()
    obj1.Attributes.LayerIndex = 0
    obj1.Geometry = MagicMock()
    obj1.Geometry.IsValid = True  # VALID geometry
    
    # Mock bounding box (VALID, non-degenerate)
    bbox1 = MagicMock()
    bbox1.IsValid = True
    bbox1.Min = MagicMock(X=0.0, Y=0.0, Z=0.0)
    bbox1.Max = MagicMock(X=10.0, Y=10.0, Z=10.0)
    obj1.Geometry.GetBoundingBox.return_value = bbox1
    
    # Mock mesh with vertices/faces
    obj1.Geometry.Vertices = [MagicMock() for _ in range(100)]
    obj1.Geometry.Faces = [MagicMock() for _ in range(50)]
    # GeometryValidator validates BLOCK INSTANCES only (see decisions.md)
    obj1.Geometry.__class__.__name__ = 'InstanceReference'
    
    obj2 = MagicMock()
    obj2.Attributes.LayerIndex = 1
    obj2.Geometry = MagicMock()
    obj2.Geometry.IsValid = True
    
    bbox2 = MagicMock()
    bbox2.IsValid = True
    bbox2.Min = MagicMock(X=5.0, Y=5.0, Z=5.0)
    bbox2.Max = MagicMock(X=15.0, Y=15.0, Z=15.0)
    obj2.Geometry.GetBoundingBox.return_value = bbox2
    obj2.Geometry.Vertices = [MagicMock() for _ in range(80)]
    obj2.Geometry.Faces = [MagicMock() for _ in range(40)]
    # GeometryValidator now requires the model to contain ONLY block instances
    obj2.Geometry.__class__.__name__ = 'InstanceReference'

    mock_model.Objects = [obj1, obj2]
    
    # Mock user strings (document-level)
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material", "Project"]
    mock_strings.__getitem__ = lambda self, key: {
        "Material": "Piedra de Montjuïc",
        "Project": "SF-Sagrada-Familia",
    }.get(key)
    mock_model.Strings = mock_strings
    
    # Mock settings
    mock_model.Settings.ModelUnitSystem = "Meters"
    mock_model.Settings.ModelAbsoluteTolerance = 0.001
    mock_model.ApplicationName = "Rhinoceros"
    mock_model.ApplicationVersion = "7.0"
    
    return mock_model


@pytest.fixture
def mock_rhino_model_invalid_nomenclature():
    """
    Mock rhino3dm.File3dm with INVALID nomenclature (layer names don't match ISO-19650).
    """
    mock_model = MagicMock()
    
    # Mock layers with INVALID names
    layer1 = MagicMock()
    layer1.Name = "bloque_test"  # INVALID: underscores, lowercase
    layer1.Visible = True
    layer1.Color = (255, 128, 0, 255)
    
    layer2 = MagicMock()
    layer2.Name = "SF_NAV_COL_001"  # INVALID: underscores
    layer2.Visible = True
    layer2.Color = (255, 64, 128, 255)
    
    mock_model.Layers = [layer1, layer2]
    mock_model.Objects = []
    
    return mock_model


@pytest.fixture
def mock_rhino_model_invalid_geometry():
    """
    Mock rhino3dm.File3dm with INVALID geometry (null geometry, degenerate bbox).
    """
    mock_model = MagicMock()
    
    # Valid layers
    layer1 = MagicMock()
    layer1.Name = "SF-C12-D-001"
    layer1.Visible = True
    layer1.Color = (255, 128, 0, 255)
    
    mock_model.Layers = [layer1]
    
    # INVALID object: null geometry
    obj1 = MagicMock()
    obj1.Attributes.LayerIndex = 0
    obj1.Geometry = None  # NULL GEOMETRY (fails validation)
    
    mock_model.Objects = [obj1]
    
    return mock_model


@pytest.fixture(autouse=True)
def mock_llm_client():
    """Mock LLM client (reuse from test_stategraph.py)."""
    with patch("src.agent.graph.llm_client.get_llm_client") as mock_get_llm:
        mock_client = MagicMock()
        mock_client.classify_tipologia.return_value = {
            "tipologia": "dovela",
            "confidence": 0.85,
            "reasoning": "Test classification (mocked)",
            "classified_at": datetime.utcnow().isoformat() + "Z",
        }
        mock_get_llm.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def mock_circuit_breaker():
    """Mock Circuit Breaker (reuse from test_stategraph.py)."""
    with patch("src.agent.graph.circuit_breaker.get_circuit_breaker") as mock_get_cb:
        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False
        mock_cb.record_success.return_value = None
        mock_cb.record_failure.return_value = None
        mock_get_cb.return_value = mock_cb
        yield mock_cb


@pytest.fixture(autouse=True)
def mock_redis_client():
    """Mock Redis client (reuse from test_stategraph.py)."""
    with patch("infra.redis_client.get_redis_client") as mock_get_redis:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        yield mock_redis


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests (T-1803)
# ─────────────────────────────────────────────────────────────────────────────

class TestStateGraphValidatorsIntegration:
    """Integration tests for Adapter Pattern validators."""
    
    # NOTE: INT-01/INT-02 (nomenclature OK / nomenclature FAIL fail-fast) were
    # removed together with the ISO-19650 nomenclature node — real Sagrada
    # Família layer names never follow ISO-19650. See memory-bank/decisions.md.

    def test_geometry_valid_executes_enrich_metadata(
        self, mock_valid_3dm_file, mock_rhino_model_valid
    ):
        """
        INT-03: Geometry OK → enrich_metadata executed.
        
        GIVEN a .3dm file with VALID geometry (non-null, valid, non-degenerate)
        WHEN the graph runs
        THEN ValidateGeometry returns geometry_valid=True
        AND EnrichMetadata is executed (validation_path includes it)
        """
        with patch("infra.supabase_client.get_supabase_client") as mock_supabase:
            mock_storage = MagicMock()
            mock_storage.download.return_value = mock_valid_3dm_file
            mock_supabase.return_value.storage.from_.return_value = mock_storage
            
            with patch("rhino3dm.File3dm.Read", return_value=mock_rhino_model_valid):
                graph = create_validation_graph()
                block_id = str(uuid4())
                initial_state = make_initial_state(block_id)
                
                final_state = graph.invoke(initial_state)
                
                # Verify geometry_valid=True (VALID geometry)
                assert final_state["geometry_valid"] is True
                
                # Verify EnrichMetadata was executed
                assert "EnrichMetadata" in final_state["validation_path"]
                
                # Verify semantic_data has material from UserStrings
                assert "material" in final_state["semantic_data"]
                assert final_state["semantic_data"]["material"] == "Piedra de Montjuïc"
    
    def test_geometry_fail_skips_enrich_metadata(
        self, mock_valid_3dm_file, mock_rhino_model_invalid_geometry
    ):
        """
        INT-04: Geometry FAIL → enrich_metadata NO ejecutado (fail-fast skip).
        
        GIVEN a .3dm file with INVALID geometry (null geometry)
        WHEN the graph runs
        THEN ValidateGeometry returns geometry_valid=False
        AND graph routes directly to MarkRejected (fail-fast)
        AND EnrichMetadata is NOT in validation_path (skipped)
        """
        with patch("infra.supabase_client.get_supabase_client") as mock_supabase:
            mock_storage = MagicMock()
            mock_storage.download.return_value = mock_valid_3dm_file
            mock_supabase.return_value.storage.from_.return_value = mock_storage
            
            with patch("rhino3dm.File3dm.Read", return_value=mock_rhino_model_invalid_geometry):
                graph = create_validation_graph()
                block_id = str(uuid4())
                initial_state = make_initial_state(block_id)
                
                final_state = graph.invoke(initial_state)
                
                # Verify geometry_valid=False (INVALID geometry)
                assert final_state["geometry_valid"] is False
                
                # Verify EnrichMetadata was SKIPPED (fail-fast)
                assert "EnrichMetadata" not in final_state["validation_path"]
                
                # Verify routed to MarkRejected
                assert "MarkRejected" in final_state["validation_path"]
                assert final_state["overall_status"] == ValidationStatus.REJECTED
    
    def test_full_happy_path_with_real_validators(
        self, mock_valid_3dm_file, mock_rhino_model_valid
    ):
        """
        INT-05: Full happy path → estado VALIDATED, semantic_data populated.
        
        GIVEN a .3dm file with VALID geometry
        WHEN the graph runs to completion
        THEN geometry validation passes (geometry_valid=True)
        AND semantic_data is populated with LLM classification + Material
        AND overall_status=VALIDATED
        AND validation_path includes all nodes (ExtractGeometry, ValidateGeometry,
            ClassifyTipologia, EnrichMetadata, GenerateReport, MarkValidated)
        """
        with patch("infra.supabase_client.get_supabase_client") as mock_supabase:
            mock_storage = MagicMock()
            mock_storage.download.return_value = mock_valid_3dm_file
            mock_supabase.return_value.storage.from_.return_value = mock_storage
            
            with patch("rhino3dm.File3dm.Read", return_value=mock_rhino_model_valid):
                graph = create_validation_graph()
                block_id = str(uuid4())
                initial_state = make_initial_state(block_id)
                
                final_state = graph.invoke(initial_state)
                
                # Verify geometry validation passed
                assert final_state["geometry_valid"] is True
                
                # Verify semantic_data populated with LLM + Material
                assert final_state["semantic_data"]["tipologia"] == "dovela"  # From LLM mock
                assert final_state["semantic_data"]["material"] == "Piedra de Montjuïc"  # From UserStrings
                assert final_state["semantic_data"]["confidence"] == 0.85
                
                # Verify classification_method
                assert final_state["classification_method"] == ClassificationMethod.LLM_GPT4
                
                # Verify overall status
                assert final_state["overall_status"] == ValidationStatus.VALIDATED
                
                # Verify validation_path includes all nodes (happy path)
                expected_nodes = [
                    "ExtractGeometry",
                    "ValidateGeometry",
                    "ClassifyTipologia",
                    "EnrichMetadata",
                    "GenerateReport",
                    "MarkValidated",
                ]
                for node_name in expected_nodes:
                    assert node_name in final_state["validation_path"], \
                        f"Expected {node_name} in validation_path, but got {final_state['validation_path']}"
                
                # Verify completed_at set
                assert final_state["completed_at"] is not None
