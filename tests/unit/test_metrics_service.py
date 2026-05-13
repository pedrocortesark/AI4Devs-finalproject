"""
Unit tests for MetricsService (T-1809-INFRA).

Tests the business logic for LangGraph observability metrics aggregation.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from services.metrics_service import MetricsService
from schemas import (
    LangGraphMetricsResponse,
    ClassificationDistribution,
    ProcessingTimeHistogram,
)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    return MagicMock()


@pytest.fixture
def metrics_service(mock_supabase):
    """MetricsService instance with mocked Supabase."""
    return MetricsService(mock_supabase)


class TestMetricsService:
    """Test suite for MetricsService."""
    
    # ===== HP-01: All metrics returned correctly =====
    def test_get_metrics_happy_path(self, metrics_service, mock_supabase):
        """HP-01: All metrics returned with valid data"""
        # Mock total_processed query
        mock_supabase.table().select().eq().execute.return_value = MagicMock(count=1523)
        
        # Mock classification_distribution query
        classification_data = [
            {"state_snapshot": {"classification_method": "LLM_GPT4", "llm_confidence": 0.9}},
            {"state_snapshot": {"classification_method": "LLM_GPT4", "llm_confidence": 0.85}},
            {"state_snapshot": {"classification_method": "FALLBACK_REGEX"}},
        ]
        
        # Mock circuit_breaker_trips query
        circuit_breaker_data = MagicMock(count=3)
        
        # Mock processing_time query (GRAPH_STARTED and GRAPH_COMPLETED)
        processing_events = [
            {"block_id": "block1", "event_type": "GRAPH_STARTED", "created_at": "2026-05-13T10:00:00Z"},
            {"block_id": "block1", "event_type": "GRAPH_COMPLETED", "created_at": "2026-05-13T10:00:12Z"},
            {"block_id": "block2", "event_type": "GRAPH_STARTED", "created_at": "2026-05-13T11:00:00Z"},
            {"block_id": "block2", "event_type": "GRAPH_COMPLETED", "created_at": "2026-05-13T11:00:45Z"},
        ]
        
        # Setup mock chain for different queries
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.in_.return_value = mock_table
        mock_table.order.return_value = mock_table
        
        # Execute method
        with patch.object(metrics_service, '_query_total_processed', return_value=1523), \
             patch.object(metrics_service, '_query_classification_distribution', return_value=ClassificationDistribution(llm_gpt4=2, fallback_regex=1)), \
             patch.object(metrics_service, '_query_circuit_breaker_trips', return_value=3), \
             patch.object(metrics_service, '_query_processing_time_percentiles', return_value=ProcessingTimeHistogram(p50=12.5, p95=45.0, p99=89.0)), \
             patch.object(metrics_service, '_query_llm_confidence_avg', return_value=0.875):
            
            success, metrics, error = metrics_service.get_langgraph_metrics()
        
        # Assertions
        assert success is True
        assert error is None
        assert metrics is not None
        assert metrics.total_processed == 1523
        assert metrics.classification_method_distribution.llm_gpt4 == 2
        assert metrics.classification_method_distribution.fallback_regex == 1
        assert metrics.circuit_breaker_trips_24h == 3
        assert metrics.avg_processing_time.p50 == 12.5
        assert metrics.llm_confidence_avg == 0.875
    
    # ===== HP-02: 24h window filtering works =====
    def test_24h_window_filtering(self, metrics_service):
        """HP-02: Metrics calculated within 24h window"""
        # This is implicitly tested by the helper methods accepting window_start
        # We verify the window calculation
        with patch.object(metrics_service, '_query_total_processed', return_value=100), \
             patch.object(metrics_service, '_query_classification_distribution') as mock_class_dist, \
             patch.object(metrics_service, '_query_circuit_breaker_trips') as mock_cb, \
             patch.object(metrics_service, '_query_processing_time_percentiles', return_value=ProcessingTimeHistogram()), \
             patch.object(metrics_service, '_query_llm_confidence_avg', return_value=None):
            
            success, metrics, error = metrics_service.get_langgraph_metrics()
            
            # Verify window_start was passed to methods
            assert mock_class_dist.called
            window_start = mock_class_dist.call_args[0][0]
            assert isinstance(window_start, datetime)
            # Verify it's approximately 24h ago (allow 1 minute variance)
            expected_window = datetime.utcnow() - timedelta(hours=24)
            assert abs((window_start - expected_window).total_seconds()) < 60
    
    # ===== EC-03: Empty database returns zeros =====
    def test_empty_database_returns_zeros(self, metrics_service):
        """EC-03: Empty database returns zero metrics gracefully"""
        with patch.object(metrics_service, '_query_total_processed', return_value=0), \
             patch.object(metrics_service, '_query_classification_distribution', return_value=ClassificationDistribution()), \
             patch.object(metrics_service, '_query_circuit_breaker_trips', return_value=0), \
             patch.object(metrics_service, '_query_processing_time_percentiles', return_value=ProcessingTimeHistogram()), \
             patch.object(metrics_service, '_query_llm_confidence_avg', return_value=None):
            
            success, metrics, error = metrics_service.get_langgraph_metrics()
        
        assert success is True
        assert metrics.total_processed == 0
        assert metrics.classification_method_distribution.llm_gpt4 == 0
        assert metrics.classification_method_distribution.fallback_regex == 0
        assert metrics.circuit_breaker_trips_24h == 0
        assert metrics.avg_processing_time.p50 == 0.0
        assert metrics.llm_confidence_avg is None
    
    # ===== EC-04: Only LLM blocks in confidence calculation =====
    def test_llm_confidence_only_llm_blocks(self, metrics_service, mock_supabase):
        """EC-04: LLM confidence only calculated for LLM-classified blocks"""
        # Mock data with mixed classification methods
        events_data = [
            {"state_snapshot": {"classification_method": "LLM_GPT4", "llm_confidence": 0.9}},
            {"state_snapshot": {"classification_method": "LLM_GPT4", "llm_confidence": 0.8}},
            {"state_snapshot": {"classification_method": "FALLBACK_REGEX"}},  # Should be ignored
        ]
        
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=events_data)
        
        window_start = datetime.utcnow() - timedelta(hours=24)
        result = metrics_service._query_llm_confidence_avg(window_start)
        
        # Should be average of 0.9 and 0.8 only (0.85)
        assert result == pytest.approx(0.85)
    
    # ===== INT-05: Query performance <100ms =====
    @pytest.mark.skip(reason="Performance test requires real database")
    def test_query_performance(self, metrics_service):
        """INT-05: Metrics query completes in <100ms"""
        import time
        
        start = time.time()
        success, metrics, error = metrics_service.get_langgraph_metrics()
        duration_ms = (time.time() - start) * 1000
        
        assert duration_ms < 100
        assert success is True
    
    # ===== ERR-06: DB connection error handled =====
    def test_database_error_handled(self, metrics_service):
        """ERR-06: Database connection errors handled gracefully"""
        with patch.object(metrics_service, '_query_total_processed', side_effect=Exception("Database connection failed")):
            
            success, metrics, error = metrics_service.get_langgraph_metrics()
        
        assert success is False
        assert metrics is None
        assert "Failed to generate metrics" in error
    
    # ===== Helper method tests =====
    def test_query_total_processed(self, metrics_service, mock_supabase):
        """Test _query_total_processed helper"""
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = MagicMock(count=100)
        
        result = metrics_service._query_total_processed()
        
        assert result == 100
    
    def test_query_classification_distribution(self, metrics_service, mock_supabase):
        """Test _query_classification_distribution helper"""
        events_data = [
            {"state_snapshot": {"classification_method": "LLM_GPT4"}},
            {"state_snapshot": {"classification_method": "LLM_GPT4"}},
            {"state_snapshot": {"classification_method": "FALLBACK_REGEX"}},
        ]
        
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=events_data)
        
        window_start = datetime.utcnow() - timedelta(hours=24)
        result = metrics_service._query_classification_distribution(window_start)
        
        assert result.llm_gpt4 == 2
        assert result.fallback_regex == 1
    
    def test_query_circuit_breaker_trips(self, metrics_service, mock_supabase):
        """Test _query_circuit_breaker_trips helper"""
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.execute.return_value = MagicMock(count=5)
        
        window_start = datetime.utcnow() - timedelta(hours=24)
        result = metrics_service._query_circuit_breaker_trips(window_start)
        
        assert result == 5
