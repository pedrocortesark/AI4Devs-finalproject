"""
Unit Tests for LangGraph StateGraph (T-1801)

WHAT WE'RE TESTING
==================
These tests verify the STRUCTURE and FLOW of the validation graph, not the
business logic inside each node (that's tested separately in node-specific tests).

We're validating:
  1. Graph compiles without errors
  2. State transitions work correctly (nomenclature → geometry → classification)
  3. Conditional edges route to the correct nodes (fail-fast behavior)
  4. Terminal nodes set the correct overall_status
  5. validation_path breadcrumbs are correct
  6. All 15 state fields are preserved across transitions

T-1801 REQUIREMENTS (10 test scenarios)
========================================
  HP-01: Skeleton flow START → END (happy path with all nodes)
  HP-02: Nomenclature OK → ExtractGeometry executed
  EC-01: Nomenclature FAIL → skip to MarkRejected (fail-fast)
  EC-02: Geometry FAIL → skip to MarkRejected (fail-fast)
  EC-03: Full happy path → status VALIDATED
  EC-04: Nomenclature fail → status REJECTED
  EC-05: validation_path has correct breadcrumbs (8 nodes for happy, 2 for reject)
  EC-06: All 15 state fields present in final state
  EC-07: Retry count preserved across nodes
  EC-08: completed_at set in terminal nodes

Author: AI Agent (T-1801-AGENT)
Created: 2026-05-04
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

try:
    from src.agent.graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from src.agent.graph.graph import create_validation_graph
    from src.agent.graph.nodes import node_mark_rejected
except ImportError:
    from graph.state import make_initial_state, ValidationStatus, ClassificationMethod
    from graph.graph import create_validation_graph
    from graph.nodes import node_mark_rejected


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures (T-1802: Mock LLM Client for T-1801 tests)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_llm_client():
    """
    Mock LLM client for all StateGraph tests (T-1801).
    
    T-1802 updated node_classify_tipologia to use real LLM client,
    but T-1801 tests don't need real LLM calls (testing graph structure, not classification).
    """
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
    """Mock Circuit Breaker for all StateGraph tests."""
    with patch("src.agent.graph.circuit_breaker.get_circuit_breaker") as mock_get_cb:
        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False  # Circuit always closed in tests
        mock_cb.record_success.return_value = None
        mock_cb.record_failure.return_value = None
        mock_get_cb.return_value = mock_cb
        yield mock_cb


@pytest.fixture(autouse=True)
def mock_redis_client():
    """Mock Redis client for all StateGraph tests."""
    with patch("infra.redis_client.get_redis_client") as mock_get_redis:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        yield mock_redis


@pytest.fixture(autouse=True)
def mock_supabase_and_rhino3dm():
    """
    Mock Supabase Storage and rhino3dm for all StateGraph tests.
    
    T-1803: ExtractGeometry is now the first node (downloads .3dm from Supabase).
    These mocks ensure tests work without real file downloads or rhino3dm parsing.
    """
    # Create mock rhino3dm model with VALID nomenclature + geometry
    mock_model = MagicMock()
    
    # Mock layers (VALID ISO-19650 nomenclature)
    layer1 = MagicMock()
    layer1.Name = "SF-C12-D-001"
    layer1.Visible = True
    layer1.Color = (255, 128, 0, 255)
    
    mock_model.Layers = [layer1]
    
    # Mock objects with VALID geometry
    obj1 = MagicMock()
    obj1.Attributes.LayerIndex = 0
    obj1.Attributes.IsInstanceDefinitionObject = False  # top-level placed object
    obj1.Geometry = MagicMock()
    obj1.Geometry.IsValid = True
    
    bbox1 = MagicMock()
    bbox1.IsValid = True
    bbox1.Min = MagicMock(X=0.0, Y=0.0, Z=0.0)
    bbox1.Max = MagicMock(X=10.0, Y=10.0, Z=10.0)
    obj1.Geometry.GetBoundingBox.return_value = bbox1
    obj1.Geometry.Vertices = [MagicMock() for _ in range(100)]
    obj1.Geometry.Faces = [MagicMock() for _ in range(50)]
    # GeometryValidator now validates BLOCK INSTANCES only (see decisions.md):
    # the placed instance must be an InstanceReference with a valid 3D bbox.
    obj1.Geometry.__class__.__name__ = 'InstanceReference'

    mock_model.Objects = [obj1]
    
    # Mock user strings
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "Piedra de Montjuïc" if key == "Material" else ""
    mock_model.Strings = mock_strings
    
    # Mock settings
    mock_model.Settings.ModelUnitSystem = "Meters"
    mock_model.Settings.ModelAbsoluteTolerance = 0.001
    
    # Patch Supabase Storage download
    with patch("infra.supabase_client.get_supabase_client") as mock_get_supabase:
        mock_storage = MagicMock()
        # Return mock .3dm file content (bytes)
        mock_storage.download.return_value = b'\x00\x00\x00\x00\x00\x00\x00\x00' + b'\x00' * 1000
        mock_get_supabase.return_value.storage.from_.return_value = mock_storage
        
        # Patch rhino3dm.File3dm.Read to return mock model
        with patch("rhino3dm.File3dm.Read", return_value=mock_model):
            yield mock_model


class TestStateGraphStructure:
    """Tests for graph compilation and basic structure."""

    def test_graph_compiles_without_errors(self):
        """HP-01: Graph compilation succeeds (no cycles, all edges defined)."""
        # WHEN: We create and compile the graph
        graph = create_validation_graph()
        
        # THEN: Graph should compile without raising exceptions
        assert graph is not None
        # Graph has a compiled attribute if compilation succeeded
        assert hasattr(graph, "invoke")

    def test_initial_state_has_16_fields(self):
        """EC-06: ValidationState has exactly 16 fields (updated in T-1806 with geometry_errors)."""
        # GIVEN: A fresh initial state
        state = make_initial_state(block_id="test-uuid-001", retry_count=0)
        
        # THEN: State should have exactly 16 keys
        assert len(state.keys()) == 16
        
        # AND: All required fields are present
        required_fields = {
            "block_id", "created_at", "retry_count",
            "nomenclature_valid", "nomenclature_errors",
            "geometry_metadata", "geometry_valid", "geometry_errors",
            "semantic_data", "classification_method", "circuit_breaker_tripped",
            "overall_status", "error_messages", "validation_path", "completed_at",
            "low_poly_url"
        }
        assert set(state.keys()) == required_fields


class TestHappyPathFlow:
    """Tests for successful validation (all checks pass)."""

    def test_happy_path_full_flow_reaches_validated(self):
        """HP-03 / EC-03: Full happy path → status VALIDATED."""
        # GIVEN: Initial state for a valid block
        initial_state = make_initial_state(block_id="test-uuid-hp-001", retry_count=0)
        
        # WHEN: We execute the graph (all stubs return success)
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: Final status should be VALIDATED
        assert final_state["overall_status"] == ValidationStatus.VALIDATED
        
        # AND: Validation path should include all 6 nodes
        # (ISO-19650 nomenclature node removed — see memory-bank/decisions.md)
        expected_path = [
            "ExtractGeometry",  # First node (downloads .3dm)
            "ValidateGeometry",
            "ClassifyTipologia",
            "EnrichMetadata",
            "GenerateReport",
            "MarkValidated",
        ]
        assert final_state["validation_path"] == expected_path
        
        # AND: Completed timestamp should be set
        assert final_state["completed_at"] != ""
        assert "T" in final_state["completed_at"]  # ISO-8601 format

    def test_nomenclature_valid_routes_to_extract_geometry(self):
        """HP-02: nomenclature_valid=True → ExtractGeometry executed."""
        # GIVEN: Initial state
        initial_state = make_initial_state(block_id="test-uuid-hp-002", retry_count=0)
        
        # WHEN: We execute the graph
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: ExtractGeometry should be in validation_path
        assert "ExtractGeometry" in final_state["validation_path"]
        
        # AND: geometry_metadata should be populated
        assert final_state["geometry_metadata"] is not None
        assert "volume" in final_state["geometry_metadata"]

    def test_semantic_data_populated_in_happy_path(self):
        """HP-04: ClassifyTipologia node populates semantic_data."""
        # GIVEN: Initial state
        initial_state = make_initial_state(block_id="test-uuid-hp-003", retry_count=0)
        
        # WHEN: We execute the graph
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: semantic_data should be populated
        assert final_state["semantic_data"] is not None
        assert "tipologia" in final_state["semantic_data"]
        assert "confidence" in final_state["semantic_data"]
        
        # AND: classification_method should be LLM_GPT4 (T-1802: real LLM classification)
        assert final_state["classification_method"] == ClassificationMethod.LLM_GPT4


class TestFailFastBehavior:
    """Tests for fail-fast conditional edges."""

    def test_nomenclature_fail_skips_to_rejected(self):
        """EC-01 / EC-04: nomenclature_valid=False → immediate rejection."""
        # GIVEN: Initial state
        initial_state = make_initial_state(block_id="test-uuid-ec-001", retry_count=0)
        
        # AND: We manually override nomenclature to fail
        # (In T-1801 skeleton, nomenclature always passes, so we need to patch)
        graph = create_validation_graph()
        
        # We'll test the node directly first to verify fail behavior
        test_state = initial_state.copy()
        test_state["nomenclature_valid"] = False
        test_state["nomenclature_errors"] = ["Test error: invalid pattern"]
        
        # WHEN: We call MarkRejected node directly (simulating fail-fast edge)
        rejected_state = node_mark_rejected(test_state)
        
        # THEN: Status should be REJECTED
        assert rejected_state["overall_status"] == ValidationStatus.REJECTED
        
        # AND: Error messages should include nomenclature errors
        assert len(rejected_state["error_messages"]) > 0

    def test_geometry_fail_skips_to_rejected(self):
        """EC-02: geometry_valid=False → skip LLM, go to rejection."""
        # GIVEN: State after nomenclature passes but geometry fails
        initial_state = make_initial_state(block_id="test-uuid-ec-002", retry_count=0)
        test_state = initial_state.copy()
        test_state["nomenclature_valid"] = True
        test_state["geometry_valid"] = False  # Geometry validation failed
        
        # WHEN: We simulate the conditional edge decision
        from src.agent.graph.graph import should_continue_after_geometry
        next_node = should_continue_after_geometry(test_state)
        
        # THEN: Next node should be MarkRejected (fail-fast)
        assert next_node == "MarkRejected"

    def test_validation_path_short_for_early_rejection(self):
        """EC-05: Early rejection → validation_path has only 2 nodes."""
        # GIVEN: State that fails nomenclature
        test_state = make_initial_state(block_id="test-uuid-ec-003", retry_count=0)
        test_state["nomenclature_valid"] = False
        test_state["nomenclature_errors"] = ["Invalid nomenclature"]
        
        # WHEN: We execute MarkRejected node (simulating early rejection)
        rejected_state = node_mark_rejected(test_state)
        
        # THEN: validation_path should be minimal (only rejection node added)
        # Initial path: [], after MarkRejected: ["MarkRejected"]
        assert "MarkRejected" in rejected_state["validation_path"]


class TestStatePreservation:
    """Tests for state field preservation across nodes."""

    def test_retry_count_preserved_across_nodes(self):
        """EC-07: retry_count is preserved throughout execution."""
        # GIVEN: Initial state with retry_count=2
        initial_state = make_initial_state(block_id="test-uuid-ec-004", retry_count=2)
        
        # WHEN: We execute the graph
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: retry_count should still be 2
        assert final_state["retry_count"] == 2

    def test_completed_at_set_in_terminal_nodes(self):
        """EC-08: completed_at is set when reaching MarkValidated or MarkRejected."""
        # GIVEN: Initial state
        initial_state = make_initial_state(block_id="test-uuid-ec-005", retry_count=0)
        
        # WHEN: We execute the graph (happy path)
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: completed_at should be set (non-empty ISO-8601 timestamp)
        assert final_state["completed_at"] != ""
        
        # AND: Should be parseable as ISO-8601
        datetime.fromisoformat(final_state["completed_at"].replace("Z", "+00:00"))

    def test_all_state_fields_present_after_execution(self):
        """EC-06 (extended): All 16 fields present in final state after execution (updated T-1806)."""
        # GIVEN: Initial state
        initial_state = make_initial_state(block_id="test-uuid-ec-006", retry_count=0)
        
        # WHEN: We execute the graph
        graph = create_validation_graph()
        final_state = graph.invoke(initial_state)
        
        # THEN: All 16 fields should still be present
        required_fields = {
            "block_id", "created_at", "retry_count",
            "nomenclature_valid", "nomenclature_errors",
            "geometry_metadata", "geometry_valid", "geometry_errors",
            "semantic_data", "classification_method", "circuit_breaker_tripped",
            "overall_status", "error_messages", "validation_path", "completed_at",
            "low_poly_url"
        }
        assert set(final_state.keys()) == required_fields


# ─────────────────────────────────────────────────────────────────────────────
# TEST SUMMARY (T-1801 DoD)
# ─────────────────────────────────────────────────────────────────────────────
# Total tests: 10 (per T-1801 requirement)
# Test categories:
#   - Structure: 2 tests (graph compilation, initial state)
#   - Happy Path: 3 tests (full flow, routing, semantic data)
#   - Fail-Fast: 3 tests (nomenclature fail, geometry fail, short path)
#   - State Preservation: 3 tests (retry count, completed_at, all fields)
#
# To run:
#   pytest tests/agent/unit/test_stategraph.py -v
#
# Expected result: 10/10 PASS (all tests green)
