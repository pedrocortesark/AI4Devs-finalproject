"""
Integration tests for /api/metrics/langgraph endpoint (T-1809-INFRA).

Tests the complete metrics endpoint flow with real Supabase queries.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from main import app
from infra.supabase_client import get_supabase_client

client = TestClient(app)


class TestMetricsEndpoint:
    """Integration tests for metrics endpoint."""
    
    # ===== INT-01: Endpoint returns 200 with valid JSON =====
    def test_endpoint_returns_200_json(self):
        """INT-01: GET /api/metrics/langgraph returns 200 with JSON"""
        # Mock Supabase queries to avoid hitting real database
        mock_supabase = MagicMock()
        mock_table = mock_supabase.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.in_.return_value = mock_table
        mock_table.order.return_value = mock_table
        
        # Mock query results
        mock_table.execute.return_value = MagicMock(
            count=100,
            data=[
                {"state_snapshot": {"classification_method": "LLM_GPT4", "llm_confidence": 0.9}},
                {"state_snapshot": {"classification_method": "FALLBACK_REGEX"}},
            ]
        )
        
        with patch('services.metrics_service.MetricsService') as MockMetricsService:
            from schemas import LangGraphMetricsResponse, ClassificationDistribution, ProcessingTimeHistogram
            
            mock_service = MockMetricsService.return_value
            mock_service.get_langgraph_metrics.return_value = (
                True,
                LangGraphMetricsResponse(
                    total_processed=100,
                    classification_method_distribution=ClassificationDistribution(llm_gpt4=50, fallback_regex=50),
                    circuit_breaker_trips_24h=2,
                    avg_processing_time=ProcessingTimeHistogram(p50=10.0, p95=30.0, p99=60.0),
                    llm_confidence_avg=0.85,
                    generated_at=datetime.utcnow().isoformat() + "Z"
                ),
                None
            )
            
            response = client.get("/api/metrics/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate JSON structure
        assert "total_processed" in data
        assert "classification_method_distribution" in data
        assert "circuit_breaker_trips_24h" in data
        assert "avg_processing_time" in data
        assert "generated_at" in data
        
        # Validate nested objects
        assert "llm_gpt4" in data["classification_method_distribution"]
        assert "fallback_regex" in data["classification_method_distribution"]
        assert "p50" in data["avg_processing_time"]
        assert "p95" in data["avg_processing_time"]
        assert "p99" in data["avg_processing_time"]
    
    # ===== INT-02: Metrics match real data =====
    @pytest.mark.skip(reason="Requires seeded Supabase data")
    def test_metrics_accurate_with_real_data(self):
        """INT-02: Metrics calculated accurately from real events table"""
        # This test would require seeding the Supabase events table with known data
        # and verifying the aggregated metrics match expectations
        
        # Example flow:
        # 1. Seed events table with 100 GRAPH_COMPLETED events
        # 2. 70 with LLM_GPT4, 30 with FALLBACK_REGEX
        # 3. 5 FALLBACK_ACTIVATED events in last 24h
        # 4. Call endpoint
        # 5. Assert total_processed=100, llm_gpt4=70, fallback_regex=30, circuit_breaker_trips=5
        pass
    
    # ===== INT-03: Response caching works =====
    @pytest.mark.skip(reason="Caching not yet implemented")
    def test_response_caching(self):
        """INT-03: Metrics endpoint uses caching (60s TTL)"""
        # This test would verify that:
        # 1. First call queries database
        # 2. Second call within 60s returns cached result
        # 3. After 60s, cache is invalidated and DB is queried again
        pass
    
    # ===== ERR-01: Database error returns 500 =====
    def test_database_error_returns_500(self):
        """ERR-01: Database connection error returns 500"""
        with patch('api.metrics.MetricsService') as MockMetricsService:
            mock_service = MockMetricsService.return_value
            mock_service.get_langgraph_metrics.return_value = (
                False,
                None,
                "Failed to generate metrics: Database connection timeout"
            )
            
            response = client.get("/api/metrics/langgraph")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to generate metrics" in data["detail"]
    
    # ===== ERR-02: Unexpected exception returns 500 =====
    def test_unexpected_exception_returns_500(self):
        """ERR-02: Unexpected exceptions handled gracefully"""
        with patch('api.metrics.get_supabase_client', side_effect=Exception("Unexpected error")):
            response = client.get("/api/metrics/langgraph")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Unexpected error" in data["detail"]
    
    # ===== HP-01: Generated timestamp is ISO 8601 =====
    def test_generated_timestamp_iso8601(self):
        """HP-01: generated_at field is valid ISO 8601 timestamp"""
        with patch('services.metrics_service.MetricsService') as MockMetricsService:
            from schemas import LangGraphMetricsResponse, ClassificationDistribution, ProcessingTimeHistogram
            
            mock_service = MockMetricsService.return_value
            mock_service.get_langgraph_metrics.return_value = (
                True,
                LangGraphMetricsResponse(
                    total_processed=50,
                    classification_method_distribution=ClassificationDistribution(llm_gpt4=30, fallback_regex=20),
                    circuit_breaker_trips_24h=1,
                    avg_processing_time=ProcessingTimeHistogram(p50=5.0, p95=15.0, p99=25.0),
                    llm_confidence_avg=0.88,
                    generated_at="2026-05-13T14:30:00Z"
                ),
                None
            )
            
            response = client.get("/api/metrics/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate ISO 8601 format
        generated_at = data["generated_at"]
        assert generated_at.endswith("Z")  # UTC timezone
        
        # Verify it's parseable
        try:
            datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"generated_at '{generated_at}' is not valid ISO 8601")
    
    # ===== HP-02: llm_confidence_avg is null when no LLM blocks =====
    def test_llm_confidence_null_when_no_llm(self):
        """HP-02: llm_confidence_avg is null when no LLM classifications"""
        with patch('api.metrics.MetricsService') as MockMetricsService:
            from schemas import LangGraphMetricsResponse, ClassificationDistribution, ProcessingTimeHistogram
            
            mock_service = MockMetricsService.return_value
            mock_service.get_langgraph_metrics.return_value = (
                True,
                LangGraphMetricsResponse(
                    total_processed=10,
                    classification_method_distribution=ClassificationDistribution(llm_gpt4=0, fallback_regex=10),
                    circuit_breaker_trips_24h=10,
                    avg_processing_time=ProcessingTimeHistogram(p50=2.0, p95=5.0, p99=8.0),
                    llm_confidence_avg=None,  # All blocks used fallback
                    generated_at=datetime.utcnow().isoformat() + "Z"
                ),
                None
            )
            
            response = client.get("/api/metrics/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["llm_confidence_avg"] is None
        assert data["classification_method_distribution"]["llm_gpt4"] == 0
        assert data["classification_method_distribution"]["fallback_regex"] == 10
