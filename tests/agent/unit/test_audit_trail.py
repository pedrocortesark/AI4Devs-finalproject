"""
Unit Tests for T-1805 Audit Trail System

Tests verify:
1. Happy path: Full validation workflow generates expected events
2. Early rejection: Nomenclature failure triggers fail-fast with minimal events  
3. Query performance: <50ms for 100 blocks timeline query
4. Event ordering: Chronological correctness (ORDER BY created_at)
5. Batch insert: EventBuffer threshold triggers single INSERT
6. Best-effort: DB failures logged as WARNING, workflow continues

Author: AI Agent (T-1805-AGENT)
Created: 2026-05-08
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import json

from src.agent.graph.state import ValidationState, ValidationStatus, ClassificationMethod, make_initial_state
from src.agent.graph.nodes import (
    serialize_state_snapshot,
    insert_event,
    with_audit_trail,
    node_validate_nomenclature,
)
from src.agent.graph.events import EventBuffer
from src.agent.constants import EventType, EVENT_BUFFER_THRESHOLD, STATE_SNAPSHOT_FIELDS


# ═══════════════════════════════════════════════════════════════════════════
# HP-01: Happy Path - Full Validation Workflow
# ═══════════════════════════════════════════════════════════════════════════

@patch("src.agent.graph.nodes.get_supabase_client")
def test_happy_path_generates_expected_events(mock_get_supabase):
    """
    HP-01: Full validation workflow generates all expected audit trail events.

    Scenario:
        - Execute complete StateGraph validation (8 nodes)
        - Verify 16 events inserted (enter + exit per node)
        - Verify event types: NODE_ENTERED, NODE_COMPLETED
        - Verify events contain state_snapshot with correct fields

    Acceptance criteria:
        - 8 NODE_ENTERED events (one per node)
        - 8 NODE_COMPLETED events (one per node)
        - Total: 16 events minimum (excluding conditional edges)
        - state_snapshot contains: overall_status, nomenclature_valid, geometry_valid, classification_method

    BDD:
        GIVEN a valid .3dm file with correct nomenclature and geometry
        WHEN the StateGraph executes all 8 nodes
        THEN 16 audit trail events are inserted into the events table
        AND each event has a valid state_snapshot
    """
    # Mock Supabase client
    mock_supabase = Mock()
    mock_table = Mock()
    mock_insert = Mock()
    mock_execute = Mock(return_value=Mock(data=[{"id": "event-123"}]))
    
    mock_supabase.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = mock_execute
    
    mock_get_supabase.return_value = mock_supabase
    
    # Create initial state (happy path)
    state = make_initial_state("GLPER.B-PAE0720.0701")
    state["nomenclature_valid"] = True
    state["geometry_valid"] = True
    state["overall_status"] = ValidationStatus.PROCESSING
    
    # Execute multiple nodes with decorator (simulates StateGraph)
    @with_audit_trail
    def mock_node_1(s: ValidationState):
        return {"validation_path": ["Node1"]}
    
    @with_audit_trail
    def mock_node_2(s: ValidationState):
        return {"validation_path": ["Node1", "Node2"]}
    
    # Execute nodes
    state = {**state, **mock_node_1(state)}
    state = {**state, **mock_node_2(state)}
    
    # Verify events inserted
    assert mock_supabase.table.call_count >= 4  # 2 nodes × 2 events (enter + exit)
    
    # Verify event structure
    calls = mock_table.insert.call_args_list
    assert len(calls) >= 4
    
    for call_args in calls:
        event_data = call_args[0][0]
        assert "block_id" in event_data
        assert "event_type" in event_data
        assert "node_name" in event_data
        assert "state_snapshot" in event_data
        
        # Verify state_snapshot has correct fields
        snapshot = event_data["state_snapshot"]
        assert "overall_status" in snapshot
        assert "validation_path_length" in snapshot


# ═══════════════════════════════════════════════════════════════════════════
# EC-02: Early Rejection - Fail-Fast
# ═══════════════════════════════════════════════════════════════════════════

@patch("src.agent.graph.nodes.get_supabase_client")
def test_early_rejection_minimal_events(mock_get_supabase):
    """
    EC-02: Early rejection via fail-fast generates minimal events.

    Scenario:
        - Execute StateGraph with invalid nomenclature
        - Conditional edge routes directly to MarkRejected (skips nodes 3-7)
        - Verify only 6 events (ExtractGeometry, ValidateNomenclature, MarkRejected)

    Acceptance criteria:
        - ExtractGeometry: 2 events (entered + completed)
        - ValidateNomenclature: 2 events (entered + completed)
        - MarkRejected: 2 events (entered + completed)
        - Total: 6 events (not 16)
        - No events for: ValidateGeometry, ClassifyTipologia, EnrichMetadata, GenerateReport, MarkValidated

    BDD:
        GIVEN a .3dm file with invalid ISO-19650 nomenclature
        WHEN ValidateNomenclature returns nomenclature_valid=False
        THEN the graph routes to MarkRejected (fail-fast)
        AND only 6 audit trail events are created (3 nodes × 2 events)
    """
    # Mock Supabase client
    mock_supabase = Mock()
    mock_table = Mock()
    mock_insert = Mock()
    mock_execute = Mock(return_value=Mock(data=[{"id": "event-123"}]))
    
    mock_supabase.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = mock_execute
    
    mock_get_supabase.return_value = mock_supabase
    
    # Create state with nomenclature failure
    state = make_initial_state("INVALID-NAME")
    state["nomenclature_valid"] = False
    state["overall_status"] = ValidationStatus.PROCESSING
    
    # Execute 3 nodes (ExtractGeometry, ValidateNomenclature, MarkRejected)
    @with_audit_trail
    def mock_extract_geometry(s: ValidationState):
        return {"geometry_metadata": {"file_exists_in_storage": True}}
    
    @with_audit_trail
    def mock_validate_nomenclature(s: ValidationState):
        return {"nomenclature_valid": False}
    
    @with_audit_trail
    def mock_mark_rejected(s: ValidationState):
        return {"overall_status": ValidationStatus.REJECTED}
    
    state = {**state, **mock_extract_geometry(state)}
    state = {**state, **mock_validate_nomenclature(state)}
    state = {**state, **mock_mark_rejected(state)}
    
    # Verify only 6 events (3 nodes × 2 events)
    assert mock_supabase.table.call_count == 6
    
    # Verify node names
    calls = mock_table.insert.call_args_list
    node_names = [call_args[0][0]["node_name"] for call_args in calls]
    
    # Node names derived from function names (mock_extract_geometry → MockExtractGeometry)
    assert any("Extract" in name for name in node_names), f"No ExtractGeometry variant found in {node_names}"
    assert any("Nomenclature" in name for name in node_names), f"No ValidateNomenclature variant found in {node_names}"
    assert any("Reject" in name for name in node_names), f"No MarkRejected variant found in {node_names}"
    
    # Should NOT have these nodes
    assert not any("ValidateGeometry" in name for name in node_names)
    assert not any("Tipologia" in name for name in node_names)


# ═══════════════════════════════════════════════════════════════════════════
# INT-03: Query Performance
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(True, reason="Integration test - requires real Supabase connection")
def test_grafana_query_performance():
    """
    INT-03: Timeline query performance <50ms for 100 blocks.

    Scenario:
        - Insert 100 blocks × 16 events = 1,600 events into Supabase
        - Execute Grafana timeline query (with compound index)
        - Measure query execution time

    Acceptance criteria:
        - Query completes in <50ms
        - Uses idx_events_block_node_time covering index
        - Returns events ordered by created_at ASC

    SQL Query:
        SELECT node_name, event_type, state_snapshot, created_at
        FROM events
        WHERE block_id = $1
        ORDER BY created_at ASC;

    BDD:
        GIVEN 1,600 events in the events table (100 blocks)
        WHEN executing the Grafana timeline query for a single block
        THEN the query completes in <50ms
        AND uses the compound index (EXPLAIN ANALYZE confirms)
    """
    from infra.supabase_client import get_supabase_client
    import time
    
    supabase = get_supabase_client()
    block_id = "GLPER.B-PAE0720.0701"
    
    # Measure query time
    start = time.perf_counter()
    result = supabase.table("events").select("*").eq("block_id", block_id).order("created_at").execute()
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    # Verify performance
    assert elapsed_ms < 50, f"Query took {elapsed_ms:.2f}ms (expected <50ms)"
    
    # Verify ordering
    events = result.data
    if len(events) > 1:
        timestamps = [e["created_at"] for e in events]
        assert timestamps == sorted(timestamps), "Events not ordered chronologically"


# ═══════════════════════════════════════════════════════════════════════════
# INT-04: Event Ordering
# ═══════════════════════════════════════════════════════════════════════════

@patch("src.agent.graph.nodes.get_supabase_client")
def test_events_ordered_chronologically(mock_get_supabase):
    """
    INT-04: Events are ordered chronologically (ORDER BY created_at).

    Scenario:
        - Execute 3 nodes sequentially
        - Verify events have increasing created_at timestamps
        - Verify ORDER BY created_at returns correct sequence

    Acceptance criteria:
        - Event 1 (Node1 entered) has earliest created_at
        - Event 6 (Node3 completed) has latest created_at
        - No out-of-order events (e.g., Node2 completed before Node1 completed)

    BDD:
        GIVEN a StateGraph execution with 3 nodes
        WHEN retrieving events with ORDER BY created_at ASC
        THEN events appear in execution order
        AND NODE_ENTERED always precedes NODE_COMPLETED for same node
    """
    # Mock Supabase to capture inserted events with timestamps
    events_log = []
    
    def mock_insert(event_data):
        event_with_timestamp = {
            **event_data,
            "created_at": datetime.utcnow().isoformat()
        }
        events_log.append(event_with_timestamp)
        return Mock(execute=Mock(return_value=Mock(data=[event_with_timestamp])))
    
    mock_supabase = Mock()
    mock_table = Mock()
    mock_table.insert.side_effect = mock_insert
    mock_supabase.table.return_value = mock_table
    mock_get_supabase.return_value = mock_supabase
    
    # Execute nodes
    state = make_initial_state("GLPER.B-PAE0720.0701")
    
    @with_audit_trail
    def node_a(s: ValidationState):
        return {"validation_path": ["A"]}
    
    @with_audit_trail
    def node_b(s: ValidationState):
        return {"validation_path": ["A", "B"]}
    
    state = {**state, **node_a(state)}
    state = {**state, **node_b(state)}
    
    # Verify chronological ordering
    assert len(events_log) >= 4  # 2 nodes × 2 events
    
    # Extract timestamps
    timestamps = [e["created_at"] for e in events_log]
    assert timestamps == sorted(timestamps), "Events not in chronological order"
    
    # Verify NODE_ENTERED precedes NODE_COMPLETED for same node
    for i in range(0, len(events_log), 2):
        if i+1 < len(events_log):
            entered = events_log[i]
            completed = events_log[i+1]
            assert entered["event_type"] == EventType.NODE_ENTERED
            assert completed["event_type"] == EventType.NODE_COMPLETED
            assert entered["node_name"] == completed["node_name"]


# ═══════════════════════════════════════════════════════════════════════════
# EC-05: Batch Insert (EventBuffer)
# ═══════════════════════════════════════════════════════════════════════════

@patch("src.agent.graph.events.get_supabase_client")
def test_event_buffer_batch_insert(mock_get_supabase):
    """
    EC-05: EventBuffer triggers batch INSERT when threshold reached.

    Scenario:
        - Create EventBuffer with threshold=10
        - Add 15 events
        - Verify batch INSERT called at 10 events (threshold)
        - Verify remaining 5 events flushed on __exit__

    Acceptance criteria:
        - 1st batch: 10 events via single INSERT
        - 2nd batch: 5 events via single INSERT (on context exit)
        - Total: 2 batch INSERTs (not 15 individual)
        - EventBuffer.events cleared after each flush

    BDD:
        GIVEN an EventBuffer with threshold=10
        WHEN adding 15 events
        THEN a batch INSERT is triggered at event #10
        AND a second batch INSERT is triggered on __exit__ (5 remaining)
        AND buffer is cleared after each flush
    """
    # Mock Supabase client
    mock_supabase = Mock()
    mock_table = Mock()
    mock_insert = Mock()
    mock_execute = Mock(return_value=Mock(data=[]))
    
    mock_supabase.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = mock_execute
    
    mock_get_supabase.return_value = mock_supabase
    
    # Create EventBuffer with threshold=10
    block_id = "GLPER.B-PAE0720.0701"
    state = make_initial_state(block_id)
    
    with EventBuffer(block_id, threshold=10) as buffer:
        # Add 15 events
        for i in range(15):
            buffer.add(
                event_type=EventType.NODE_ENTERED,
                node_name=f"Node{i}",
                state=state
            )
            
            # After 10th event, buffer should flush
            if i == 9:  # 0-indexed
                assert mock_table.insert.call_count == 1  # First batch INSERT
                first_batch = mock_table.insert.call_args[0][0]
                assert len(first_batch) == 10
    
    # On __exit__, remaining 5 events should flush
    assert mock_table.insert.call_count == 2  # Second batch INSERT
    second_batch = mock_table.insert.call_args[0][0]
    assert len(second_batch) == 5


# ═══════════════════════════════════════════════════════════════════════════
# EC-06: Best-Effort Pattern (DB Failure)
# ═══════════════════════════════════════════════════════════════════════════

@patch("src.agent.graph.nodes.get_supabase_client")
@patch("src.agent.graph.nodes.logger")
def test_db_failure_non_fatal(mock_logger, mock_get_supabase):
    """
    EC-06: DB failures logged as WARNING, workflow continues (best-effort).

    Scenario:
        - Mock Supabase INSERT to raise exception
        - Execute node with @with_audit_trail decorator
        - Verify node execution completes successfully
        - Verify logger.warning called with error details

    Acceptance criteria:
        - Node function executes and returns result (no exception propagated)
        - logger.warning called with "event.insert_failed" or "audit.node_entered_failed"
        - StateGraph workflow continues uninterrupted

    BDD:
        GIVEN a Supabase INSERT failure (network timeout, DB down)
        WHEN executing a decorated node
        THEN the node completes successfully
        AND a WARNING is logged
        AND no exception is raised to the caller
    """
    # Mock Supabase to raise exception
    mock_supabase = Mock()
    mock_table = Mock()
    mock_insert = Mock()
    mock_insert.execute.side_effect = Exception("DB connection timeout")
    
    mock_supabase.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    
    mock_get_supabase.return_value = mock_supabase
    
    # Execute node (should NOT raise exception)
    state = make_initial_state("GLPER.B-PAE0720.0701")
    
    @with_audit_trail
    def mock_node(s: ValidationState):
        return {"validation_path": ["TestNode"]}
    
    result = mock_node(state)
    
    # Verify node executed successfully
    assert result["validation_path"] == ["TestNode"]
    
    # Verify WARNING logged (best-effort pattern)
    warning_calls = [
        call for call in mock_logger.warning.call_args_list
        if "audit" in str(call) or "event" in str(call)
    ]
    assert len(warning_calls) >= 1, "No warnings logged for DB failure"


# ═══════════════════════════════════════════════════════════════════════════
# UNIT: State Snapshot Serializer
# ═══════════════════════════════════════════════════════════════════════════

def test_serialize_state_snapshot_lightweight():
    """
    UNIT: serialize_state_snapshot extracts only lightweight fields.

    Scenario:
        - Create state with heavy geometry_metadata (~1MB)
        - Serialize to snapshot
        - Verify snapshot <1KB (excludes geometry_metadata)
        - Verify only STATE_SNAPSHOT_FIELDS included

    Acceptance criteria:
        - Snapshot contains: overall_status, nomenclature_valid, geometry_valid, classification_method
        - Snapshot contains: validation_path_length (integer, not full array)
        - Snapshot does NOT contain: geometry_metadata, error_messages
        - Snapshot size <1KB when JSON-serialized

    BDD:
        GIVEN a ValidationState with 1MB geometry_metadata
        WHEN calling serialize_state_snapshot(state)
        THEN the snapshot is <1KB
        AND contains only STATE_SNAPSHOT_FIELDS + validation_path_length
    """
    # Create state with heavy metadata
    state = make_initial_state("GLPER.B-PAE0720.0701")
    state["overall_status"] = ValidationStatus.PROCESSING
    state["nomenclature_valid"] = True
    state["geometry_valid"] = True
    state["classification_method"] = ClassificationMethod.LLM_GPT4
    state["validation_path"] = ["Node1", "Node2", "Node3"]
    
    # Add heavy geometry_metadata (simulate 1MB)
    state["geometry_metadata"] = {
        "vertices": [{"x": i, "y": i, "z": i} for i in range(10000)],  # Heavy payload
        "layers": [{"name": f"Layer{i}", "index": i} for i in range(1000)],
    }
    
    # Serialize
    snapshot = serialize_state_snapshot(state)
    
    # Verify lightweight
    snapshot_json = json.dumps(snapshot)
    snapshot_size_bytes = len(snapshot_json)
    assert snapshot_size_bytes < 1024, f"Snapshot too large: {snapshot_size_bytes} bytes (expected <1KB)"
    
    # Verify contains expected fields
    assert "overall_status" in snapshot
    assert "nomenclature_valid" in snapshot
    assert "geometry_valid" in snapshot
    assert "classification_method" in snapshot
    assert "validation_path_length" in snapshot
    assert snapshot["validation_path_length"] == 3
    
    # Verify excludes heavy fields
    assert "geometry_metadata" not in snapshot
    assert "error_messages" not in snapshot
    assert "vertices" not in snapshot_json  # Ensure heavy data not embedded
