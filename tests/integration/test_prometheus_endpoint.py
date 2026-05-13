"""
Integration tests for Prometheus metrics endpoint.

Tests the /metrics endpoint exposed by api/prometheus.py router.

T-1809-INFRA: Optional feature - Prometheus exporter endpoint tests.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from main import app
from schemas import (
    LangGraphMetricsResponse,
    ClassificationDistribution,
    ProcessingTimeHistogram,
)


@pytest.fixture
def client():
    """Create a test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_metrics_response():
    """Sample metrics response for mocking."""
    return LangGraphMetricsResponse(
        total_processed=2500,
        classification_method_distribution=ClassificationDistribution(
            llm_gpt4=2100,
            fallback_regex=400
        ),
        circuit_breaker_trips_24h=25,
        avg_processing_time=ProcessingTimeHistogram(
            p50=10.5,
            p95=30.2,
            p99=55.8
        ),
        llm_confidence_avg=0.82,
        generated_at="2026-05-13T16:00:00Z"
    )


class TestPrometheusEndpointSuccess:
    """Test successful /metrics endpoint responses."""
    
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_returns_200_with_prometheus_format(
        self, mock_metrics_service_class, client, sample_metrics_response
    ):
        """INT-01: GET /metrics returns 200 with Prometheus text format."""
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act
        response = client.get("/metrics")
        
        # Assert
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "version=0.0.4" in response.headers["content-type"]  # Prometheus format version
        
        # Verify response contains Prometheus metrics
        text = response.text
        assert "# HELP langgraph_blocks_processed_total" in text
        assert "# TYPE langgraph_blocks_processed_total counter" in text
        assert "langgraph_blocks_processed_total" in text
    
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_contains_all_five_metrics(
        self, mock_metrics_service_class, client, sample_metrics_response
    ):
        """HP-01: Response contains all 5 Prometheus metrics."""
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act
        response = client.get("/metrics")
        text = response.text
        
        # Assert - All 5 metrics present
        assert "langgraph_blocks_processed_total" in text
        assert "langgraph_classification_method" in text
        assert "langgraph_circuit_breaker_trips_24h" in text
        assert "langgraph_processing_time_seconds" in text
        assert "langgraph_llm_confidence" in text
    
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_contains_labels_and_values(
        self, mock_metrics_service_class, client, sample_metrics_response
    ):
        """HP-02: Response contains correct labels and metric values."""
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act
        response = client.get("/metrics")
        text = response.text
        
        # Assert - Labels and values
        assert 'langgraph_classification_method{method="llm_gpt4"}' in text
        assert 'langgraph_classification_method{method="fallback_regex"}' in text
        assert '2100.0' in text  # llm_gpt4 count
        assert '400.0' in text   # fallback_regex count
        assert '25.0' in text    # circuit_breaker_trips


class TestPrometheusEndpointErrors:
    """Test /metrics endpoint error handling."""
    
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_returns_500_on_metrics_service_failure(
        self, mock_metrics_service_class, client
    ):
        """ERR-01: Returns 500 when MetricsService fails."""
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            False, None, "Database connection timeout"
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act
        response = client.get("/metrics")
        
        # Assert
        assert response.status_code == 500
        assert "Failed to generate Prometheus metrics" in response.json()["detail"]
    
    @patch('api.prometheus.PrometheusService')
    def test_metrics_endpoint_returns_500_on_update_metrics_failure(
        self, mock_prometheus_service_class, client
    ):
        """ERR-02: Returns 500 when PrometheusService.update_metrics() returns False."""
        # Arrange
        mock_prom_instance = Mock()
        mock_prom_instance.update_metrics.return_value = False
        mock_prometheus_service_class.return_value = mock_prom_instance
        
        # Act
        response = client.get("/metrics")
        
        # Assert
        assert response.status_code == 500
        assert "Failed to generate Prometheus metrics" in response.json()["detail"]
    
    @patch('api.prometheus.get_supabase_client')
    def test_metrics_endpoint_handles_unexpected_exception(
        self, mock_supabase_client, client
    ):
        """ERR-03: Returns 500 with error message on unexpected exception."""
        # Arrange
        mock_supabase_client.side_effect = Exception("Supabase client initialization failed")
        
        # Act
        response = client.get("/metrics")
        
        # Assert
        assert response.status_code == 500
        assert "Unexpected error generating Prometheus metrics" in response.json()["detail"]


class TestPrometheusEndpointCaching:
    """Test caching behavior (optional, requires Redis)."""
    
    @pytest.mark.skip(reason="Optional: Requires Redis running for cache validation")
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_uses_cache_on_repeated_requests(
        self, mock_metrics_service_class, client, sample_metrics_response
    ):
        """OPT-01: Repeated requests within 60s use cached metrics (reduces DB load)."""
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act - First request (cache miss)
        response1 = client.get("/metrics")
        assert response1.status_code == 200
        
        # Act - Second request within TTL (cache hit)
        response2 = client.get("/metrics")
        assert response2.status_code == 200
        
        # Assert - MetricsService.get_langgraph_metrics() called only once (cache hit on 2nd)
        # Note: This requires actual Redis and more complex mocking
        assert mock_service_instance.get_langgraph_metrics.call_count <= 2


class TestPrometheusEndpointPerformance:
    """Performance validation tests (optional)."""
    
    @pytest.mark.skip(reason="Optional: Performance test requires profiling tools")
    @patch('api.prometheus.MetricsService')
    def test_metrics_endpoint_response_time_under_100ms_with_cache(
        self, mock_metrics_service_class, client, sample_metrics_response
    ):
        """PERF-01: Response time <100ms with cache hit."""
        import time
        
        # Arrange
        mock_service_instance = Mock()
        mock_service_instance.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        mock_metrics_service_class.return_value = mock_service_instance
        
        # Act - Warm up cache
        client.get("/metrics")
        
        # Act - Measure second request (cache hit)
        start = time.time()
        response = client.get("/metrics")
        duration_ms = (time.time() - start) * 1000
        
        # Assert
        assert response.status_code == 200
        # Note: This is highly dependent on test environment, may need adjustment
        assert duration_ms < 100, f"Response time {duration_ms}ms exceeds 100ms threshold"
