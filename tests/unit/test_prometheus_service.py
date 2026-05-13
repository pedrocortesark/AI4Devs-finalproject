"""
Unit tests for PrometheusService.

T-1809-INFRA: Optional feature - Prometheus exporter tests.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from prometheus_client import generate_latest

from services.prometheus_service import PrometheusService
from services.metrics_service import MetricsService
from schemas import (
    LangGraphMetricsResponse,
    ClassificationDistribution,
    ProcessingTimeHistogram,
)


@pytest.fixture
def mock_metrics_service():
    """Create a mock MetricsService."""
    return Mock(spec=MetricsService)


@pytest.fixture
def sample_metrics_response():
    """Create a sample LangGraphMetricsResponse for testing."""
    return LangGraphMetricsResponse(
        total_processed=1523,
        classification_method_distribution=ClassificationDistribution(
            llm_gpt4=1402,
            fallback_regex=121
        ),
        circuit_breaker_trips_24h=12,
        avg_processing_time=ProcessingTimeHistogram(
            p50=8.5,
            p95=25.3,
            p99=42.1
        ),
        llm_confidence_avg=0.87,
        generated_at="2026-05-13T15:30:00Z"
    )


class TestPrometheusServiceInitialization:
    """Test PrometheusService initialization."""
    
    def test_prometheus_service_initializes_all_metrics(self, mock_metrics_service):
        """HP-01: PrometheusService initializes all 5 metric collectors."""
        # Act
        service = PrometheusService(mock_metrics_service)
        
        # Assert
        assert service.blocks_processed is not None
        assert service.classification_method is not None
        assert service.circuit_breaker_trips is not None
        assert service.processing_time is not None
        assert service.llm_confidence is not None
        assert service.registry is not None
    
    def test_prometheus_service_metrics_have_correct_types(self, mock_metrics_service):
        """HP-02: Metric collectors have correct Prometheus types."""
        # Act
        service = PrometheusService(mock_metrics_service)
        
        # Assert
        from prometheus_client import Counter, Gauge, Histogram
        assert isinstance(service.blocks_processed, Counter)
        assert isinstance(service.classification_method, Gauge)
        assert isinstance(service.circuit_breaker_trips, Gauge)
        assert isinstance(service.processing_time, Histogram)
        assert isinstance(service.llm_confidence, Gauge)


class TestPrometheusServiceUpdateMetrics:
    """Test PrometheusService.update_metrics() method."""
    
    def test_update_metrics_success(self, mock_metrics_service, sample_metrics_response):
        """HP-03: update_metrics() successfully updates all Prometheus collectors."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        result = service.update_metrics()
        
        # Assert
        assert result is True
        mock_metrics_service.get_langgraph_metrics.assert_called_once()
        
        # Verify metrics were updated (check Counter value via _value.get())
        assert service.blocks_processed._value.get() == 1523.0
        assert service.circuit_breaker_trips._value.get() == 12.0
        # Note: Gauge with labels stores keys as tuples like ('llm_gpt4',) and ('fallback_regex',)
        # Extract method values from the tuple structure
        label_values = [labels[0] for labels in service.classification_method._metrics.keys()]
        assert 'llm_gpt4' in label_values
        assert 'fallback_regex' in label_values
    
    def test_update_metrics_handles_metrics_service_failure(self, mock_metrics_service):
        """ERR-01: update_metrics() returns False when MetricsService fails."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            False, None, "Database connection error"
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        result = service.update_metrics()
        
        # Assert
        assert result is False
        mock_metrics_service.get_langgraph_metrics.assert_called_once()
    
    def test_update_metrics_handles_no_metrics_data(self, mock_metrics_service):
        """EC-01: update_metrics() returns False when metrics data is None."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, None, None
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        result = service.update_metrics()
        
        # Assert
        assert result is False
    
    def test_update_metrics_handles_null_llm_confidence(self, mock_metrics_service):
        """EC-02: update_metrics() sets llm_confidence to -1 when None."""
        # Arrange
        metrics_no_llm = LangGraphMetricsResponse(
            total_processed=100,
            classification_method_distribution=ClassificationDistribution(
                llm_gpt4=0,
                fallback_regex=100
            ),
            circuit_breaker_trips_24h=0,
            avg_processing_time=ProcessingTimeHistogram(p50=5.0, p95=10.0, p99=15.0),
            llm_confidence_avg=None,  # No LLM classifications
            generated_at="2026-05-13T15:30:00Z"
        )
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, metrics_no_llm, None
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        result = service.update_metrics()
        
        # Assert
        assert result is True
        assert service.llm_confidence._value.get() == -1.0
    
    def test_update_metrics_handles_exception(self, mock_metrics_service):
        """ERR-02: update_metrics() catches exceptions and returns False."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.side_effect = Exception("Unexpected error")
        service = PrometheusService(mock_metrics_service)
        
        # Act
        result = service.update_metrics()
        
        # Assert
        assert result is False


class TestPrometheusServiceHistogram:
    """Test histogram metric behavior."""
    
    def test_histogram_populates_buckets_correctly(self, mock_metrics_service, sample_metrics_response):
        """HP-04: Histogram buckets are populated based on percentiles."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        service.update_metrics()
        
        # Assert - Generate Prometheus output and verify histogram exists
        output = generate_latest(service.registry).decode('utf-8')
        assert 'langgraph_processing_time_seconds_bucket' in output
        assert 'langgraph_processing_time_seconds_count' in output
        assert 'langgraph_processing_time_seconds_sum' in output


class TestPrometheusServiceLabels:
    """Test labeled metrics (classification_method)."""
    
    def test_classification_method_labels_created(self, mock_metrics_service, sample_metrics_response):
        """HP-05: Classification method gauge creates labels for llm_gpt4 and fallback_regex."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        
        # Act
        service.update_metrics()
        
        # Assert - Generate Prometheus output and verify labels exist
        output = generate_latest(service.registry).decode('utf-8')
        assert 'langgraph_classification_method{method="llm_gpt4"}' in output
        assert 'langgraph_classification_method{method="fallback_regex"}' in output
        assert '1402.0' in output  # llm_gpt4 count
        assert '121.0' in output   # fallback_regex count


class TestPrometheusServiceResetMetrics:
    """Test reset_metrics() utility method."""
    
    def test_reset_metrics_clears_all_values(self, mock_metrics_service, sample_metrics_response):
        """UTIL-01: reset_metrics() sets all metrics to zero (testing utility)."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        service.update_metrics()
        
        # Act
        service.reset_metrics()
        
        # Assert
        assert service.blocks_processed._value.get() == 0.0
        assert service.circuit_breaker_trips._value.get() == 0.0
        assert service.llm_confidence._value.get() == 0.0


class TestPrometheusServiceIntegration:
    """Integration-style tests verifying Prometheus text output format."""
    
    def test_generate_latest_produces_valid_prometheus_format(
        self, mock_metrics_service, sample_metrics_response
    ):
        """INT-01: generate_latest() produces valid Prometheus text format."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        service.update_metrics()
        
        # Act
        output = generate_latest(service.registry).decode('utf-8')
        
        # Assert - Check for HELP and TYPE comments (Prometheus format requirements)
        assert '# HELP langgraph_blocks_processed_total' in output
        assert '# TYPE langgraph_blocks_processed_total counter' in output
        assert '# HELP langgraph_classification_method' in output
        assert '# TYPE langgraph_classification_method gauge' in output
        assert '# HELP langgraph_circuit_breaker_trips_24h' in output
        assert '# TYPE langgraph_circuit_breaker_trips_24h gauge' in output
        assert '# HELP langgraph_processing_time_seconds' in output
        assert '# TYPE langgraph_processing_time_seconds histogram' in output
        assert '# HELP langgraph_llm_confidence' in output
        assert '# TYPE langgraph_llm_confidence gauge' in output
    
    def test_prometheus_output_contains_all_metric_values(
        self, mock_metrics_service, sample_metrics_response
    ):
        """INT-02: Prometheus output contains all expected metric values."""
        # Arrange
        mock_metrics_service.get_langgraph_metrics.return_value = (
            True, sample_metrics_response, None
        )
        service = PrometheusService(mock_metrics_service)
        service.update_metrics()
        
        # Act
        output = generate_latest(service.registry).decode('utf-8')
        
        # Assert - Verify actual metric values appear in output
        assert 'langgraph_blocks_processed_total 1523.0' in output
        assert 'langgraph_circuit_breaker_trips_24h 12.0' in output
        assert 'langgraph_llm_confidence 0.87' in output
