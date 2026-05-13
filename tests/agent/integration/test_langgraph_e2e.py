"""
T-1806 E2E LangGraph Integration Tests

End-to-end tests that validate the complete StateGraph workflow with real .3dm files.
Tests cover 6 scenarios: happy path, edge cases, error handling, concurrency, and performance.

Test Scenarios:
    - HP-E2E-01: Valid file → validated state with semantic_data
    - EC-E2E-02: Invalid nomenclature → rejected (fail-fast, no LLM)
    - EC-E2E-03: OpenAI timeout → fallback regex + circuit_breaker_tripped
    - ERR-E2E-04: Degenerate geometry → rejected with geometry_errors
    - INT-E2E-05: 6 files concurrent → all processed correctly
    - PERF-E2E-06: Performance <60s/file without LLM, <90s/file with LLM

Requirements:
    - Mock OpenAI (zero tokens consumed in CI)
    - Real .3dm files from tests/fixtures/
    - Cleanup test blocks after each test
    - Regression validation: 70/70 tests PASS baseline

Author: AI Assistant (T-1806)
Date: 2026-05-12
"""

import pytest
import uuid
import time
from pathlib import Path
from typing import Dict, Any

# Import StateGraph and validators
from src.agent.graph.graph import create_validation_graph
from src.agent.graph.state import ValidationState
from src.agent.constants import EventType


class TestLangGraphE2E:
    """
    E2E Integration Tests for LangGraph StateGraph validation workflow.
    
    These tests execute the complete StateGraph with real .3dm files and mocked
    OpenAI to validate end-to-end behavior without consuming API tokens.
    """
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _create_initial_state(
        self,
        block_id: str,
        file_path: str,
        iso_code: str = None
    ) -> ValidationState:
        """
        Create initial ValidationState for StateGraph execution.
        
        Args:
            block_id: Unique block identifier (UUID)
            file_path: Path to .3dm file in Storage (e.g., "test-e2e/file.3dm")
            iso_code: Optional ISO-19650 code (defaults to auto-generated)
        
        Returns:
            ValidationState dict with all required fields initialized
        """
        if iso_code is None:
            iso_code = f"TEST-E2E-{uuid.uuid4().hex[:8].upper()}"
        
        return {
            "block_id": block_id,
            "iso_code": iso_code,
            "file_path": file_path,
            "nomenclature_valid": None,
            "nomenclature_errors": [],
            "geometry_metadata": {},
            "geometry_valid": None,
            "geometry_errors": [],
            "semantic_data": {},
            "overall_status": "processing",
            "classification_method": None,
            "validation_path": [],
            "error_messages": [],
            "circuit_breaker_tripped": False,
            "created_at": None,
            "completed_at": None,
            "retry_count": 0,
            "low_poly_url": None,
        }
    
    def _assert_block_state(
        self,
        supabase_client,
        block_id: str,
        expected_status: str,
        expected_errors: Dict[str, Any] = None
    ):
        """
        Assert that a block in the database matches expected state.
        
        Args:
            supabase_client: Supabase client fixture
            block_id: Block ID to query
            expected_status: Expected overall_status ("validated" or "rejected")
            expected_errors: Optional dict with expected error fields
        
        Raises:
            AssertionError: If block state doesn't match expectations
        """
        result = supabase_client.table("blocks") \
            .select("*") \
            .eq("id", block_id) \
            .execute()
        
        assert len(result.data) == 1, f"Block {block_id} not found in database"
        
        block = result.data[0]
        
        assert block["overall_status"] == expected_status, \
            f"Expected status {expected_status}, got {block['overall_status']}"
        
        if expected_errors:
            for key, expected_value in expected_errors.items():
                actual_value = block.get(key)
                assert actual_value == expected_value, \
                    f"Expected {key}={expected_value}, got {actual_value}"
    
    def _count_events(
        self,
        supabase_client,
        block_id: str,
        event_type: str = None
    ) -> int:
        """
        Count events for a block, optionally filtered by event_type.
        
        Args:
            supabase_client: Supabase client fixture
            block_id: Block ID to query
            event_type: Optional event_type filter (e.g., "node_completed")
        
        Returns:
            int: Number of events matching criteria
        """
        query = supabase_client.table("events") \
            .select("id", count="exact") \
            .eq("block_id", block_id)
        
        if event_type:
            query = query.eq("event_type", event_type)
        
        result = query.execute()
        return result.count or 0
    
    def _get_event_node_names(
        self,
        supabase_client,
        block_id: str
    ) -> list:
        """
        Get list of node_names from events for a block (in chronological order).
        
        Args:
            supabase_client: Supabase client fixture
            block_id: Block ID to query
        
        Returns:
            list: Node names in execution order
        """
        result = supabase_client.table("events") \
            .select("node_name") \
            .eq("block_id", block_id) \
            .order("created_at", desc=False) \
            .execute()
        
        return [event["node_name"] for event in result.data if event["node_name"]]
    
    # ========================================================================
    # Test Scenarios
    # ========================================================================
    
    @pytest.mark.e2e
    def test_hp_e2e_01_valid_file_validated(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        HP-E2E-01: Valid file → validated state with semantic_data.
        
        Scenario:
            - Upload valid .3dm file with correct nomenclature
            - Mock OpenAI returns valid classification (dovela, confidence 0.92)
            - StateGraph executes full workflow (8 nodes)
            - Final state: validated
            - semantic_data populated with tipologia
            - GLB generated in /processed/
            - validation_report JSONB with 0 errors
        
        Assertions:
            - overall_status == "validated"
            - semantic_data contains tipologia, confidence, classification_method
            - 8-12 events in events table
            - All nodes executed in correct order
        """
        # TODO: Implement in Tarea 5
        pytest.skip("HP-E2E-01 not yet implemented")
    
    @pytest.mark.e2e
    def test_ec_e2e_02_invalid_nomenclature_rejected(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        EC-E2E-02: Invalid nomenclature → rejected (fail-fast, no LLM).
        
        Scenario:
            - Upload file with invalid nomenclature (e.g., "invalid-name.3dm")
            - Validate Nomenclature node detects error
            - StateGraph transitions directly to REJECTED (fail-fast)
            - NO OpenAI tokens consumed (verify mock call_count == 0)
            - Only 3 events in table (START, ValidateNomenclature, REJECTED)
        
        Assertions:
            - overall_status == "rejected"
            - nomenclature_errors array populated
            - event count == 3 (fail-fast, no downstream nodes)
            - mock_openai_client not called
            - Performance: <5s (no LLM overhead)
        """
        # TODO: Implement in Tarea 6
        pytest.skip("EC-E2E-02 not yet implemented")
    
    @pytest.mark.e2e
    def test_ec_e2e_03_openai_timeout_fallback(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        EC-E2E-03: OpenAI timeout → fallback regex + circuit_breaker_tripped.
        
        Scenario:
            - Upload valid file
            - Mock OpenAI raises TimeoutError after 3 retries
            - Circuit Breaker detects failure
            - Fallback regex classification activated automatically
            - Classification based on filename pattern (SF-C12-D-* → dovela)
            - Final state: validated (with degraded confidence)
        
        Assertions:
            - overall_status == "validated"
            - classification_method == "fallback_regex"
            - circuit_breaker_tripped == True
            - confidence < 0.7 (fallback has lower confidence)
            - Events include CIRCUIT_BREAKER_TRIPPED + FALLBACK_ACTIVATED
        """
        # TODO: Implement in Tarea 7
        pytest.skip("EC-E2E-03 not yet implemented")
    
    @pytest.mark.e2e
    def test_err_e2e_04_degenerate_geometry_rejected(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        ERR-E2E-04: Degenerate geometry → rejected with geometry_errors.
        
        Scenario:
            - Upload file with invalid geometry (0 vertices or corrupted)
            - ValidateGeometry node detects error
            - StateGraph transitions to REJECTED
            - NO downstream nodes executed (EnrichMetadata, GenerateReport skipped)
        
        Assertions:
            - overall_status == "rejected"
            - geometry_errors array contains "Invalid geometry: 0 vertices"
            - EnrichMetadata NOT in event node_names
            - GenerateReport NOT in event node_names
        """
        # TODO: Implement in Tarea 8
        pytest.skip("ERR-E2E-04 not yet implemented")
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_int_e2e_05_concurrent_processing(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        INT-E2E-05: 6 files concurrent → all processed correctly.
        
        Scenario:
            - Upload 6 files simultaneously (simulate batch upload)
            - StateGraph processes all in parallel (Celery workers simulation)
            - Expected outcomes:
                - 3 files validated (valid nomenclature + geometry)
                - 3 files rejected (1 nomenclature, 1 geometry, 1 mixed)
            - NO race conditions in DB (block_id unique, events not mixed)
        
        Assertions:
            - 6 blocks in database with correct statuses
            - All blocks have complete event trails
            - Events not mixed between blocks (integrity check)
            - Referential integrity maintained
        """
        # TODO: Implement in Tarea 9
        pytest.skip("INT-E2E-05 not yet implemented")
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_perf_e2e_06_performance_targets(
        self,
        supabase_client,
        mock_openai_client,
        e2e_upload_test_file,
        e2e_cleanup_blocks
    ):
        """
        PERF-E2E-06: Performance <60s/file without LLM, <90s/file with LLM.
        
        Scenario:
            - Measure execution time for 2 scenarios:
                1. Invalid nomenclature (no LLM) → <60s
                2. Valid file with LLM mock → <90s
            - Use pytest-benchmark for timing
        
        Assertions:
            - Scenario 1 duration < 60.0 seconds
            - Scenario 2 duration < 90.0 seconds
            - Benchmark report generated
        
        Note: Marked as @pytest.mark.benchmark (optional in CI)
        """
        # TODO: Implement in Tarea 10
        pytest.skip("PERF-E2E-06 not yet implemented")
