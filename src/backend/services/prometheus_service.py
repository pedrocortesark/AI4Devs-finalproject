"""
Prometheus metrics exporter for LangGraph observability.

This service converts LangGraph metrics from the MetricsService into Prometheus format,
exposing them via the /metrics endpoint for scraping by Prometheus server.

T-1809-INFRA: Optional feature implementation.
"""

from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry
import structlog

from services.metrics_service import MetricsService
from schemas import LangGraphMetricsResponse

logger = structlog.get_logger(__name__)


class PrometheusService:
    """
    Prometheus metrics exporter for The Librarian agent.
    
    Exposes 5 core metrics in Prometheus format:
    1. langgraph_blocks_processed_total (Counter) - All-time blocks processed
    2. langgraph_classification_method (Gauge) - Classification method distribution (labeled)
    3. langgraph_circuit_breaker_trips_24h (Gauge) - Circuit breaker activations (24h)
    4. langgraph_processing_time_seconds (Histogram) - Processing time distribution
    5. langgraph_llm_confidence (Gauge) - Average LLM confidence (24h)
    
    Architecture:
        MetricsService (Supabase queries) → PrometheusService (Prometheus format) → /metrics endpoint
    
    Usage:
        prometheus_service = PrometheusService(metrics_service)
        prometheus_service.update_metrics()
        metrics_text = generate_latest(prometheus_service.registry)
    """
    
    def __init__(self, metrics_service: MetricsService):
        """
        Initialize Prometheus metrics collectors.
        
        Args:
            metrics_service: MetricsService instance for fetching LangGraph metrics
        """
        self.metrics_service = metrics_service
        self.registry = CollectorRegistry()
        
        # Metric 1: Counter - Total blocks processed (all-time)
        self.blocks_processed = Counter(
            'langgraph_blocks_processed_total',
            'Total blocks processed by The Librarian since system start',
            registry=self.registry
        )
        
        # Metric 2: Gauge - Classification method distribution (with labels)
        self.classification_method = Gauge(
            'langgraph_classification_method',
            'Number of blocks classified by each method (24h)',
            ['method'],  # Labels: llm_gpt4, fallback_regex
            registry=self.registry
        )
        
        # Metric 3: Gauge - Circuit breaker trips (24h)
        self.circuit_breaker_trips = Gauge(
            'langgraph_circuit_breaker_trips_24h',
            'Number of circuit breaker activations in last 24 hours',
            registry=self.registry
        )
        
        # Metric 4: Histogram - Processing time distribution (24h)
        # Buckets: 1s, 5s, 10s, 30s, 60s (1m), 120s (2m), 300s (5m), +Inf
        self.processing_time = Histogram(
            'langgraph_processing_time_seconds',
            'Block processing time distribution (24h)',
            buckets=[1, 5, 10, 30, 60, 120, 300],
            registry=self.registry
        )
        
        # Metric 5: Gauge - Average LLM confidence (24h)
        self.llm_confidence = Gauge(
            'langgraph_llm_confidence',
            'Average LLM confidence score (0-1) for blocks classified via GPT-4 (24h)',
            registry=self.registry
        )
        
        logger.info(
            "prometheus_service_initialized",
            metrics=["blocks_processed", "classification_method", "circuit_breaker_trips", 
                     "processing_time", "llm_confidence"]
        )
    
    def update_metrics(self) -> bool:
        """
        Fetch latest metrics from MetricsService and update Prometheus collectors.
        
        This method should be called on every /metrics endpoint request to ensure
        Prometheus scrapes the most recent data.
        
        Returns:
            bool: True if metrics updated successfully, False if MetricsService failed
        
        Side Effects:
            - Updates all 5 Prometheus metric collectors
            - Logs errors if MetricsService fails
        
        Implementation Note:
            Prometheus Counters are monotonic (only increase), but we set them directly
            from the database value. This works because Counter._value.set() bypasses
            the increment-only restriction. For production, consider using _metric_init()
            pattern or migrating to Gauge for total_processed.
        """
        try:
            success, langgraph_metrics, error = self.metrics_service.get_langgraph_metrics()
            
            if not success:
                logger.error(
                    "prometheus_update_failed",
                    error=error,
                    reason="MetricsService returned failure"
                )
                return False
            
            if not langgraph_metrics:
                logger.warning(
                    "prometheus_update_skipped",
                    reason="No metrics data available"
                )
                return False
        
            # Update Metric 1: Total blocks processed (Counter)
            # Note: Using _value.set() to bypass increment-only restriction
            # Alternative: Use Gauge instead of Counter for non-monotonic resets
            self.blocks_processed._value.set(float(langgraph_metrics.total_processed))
            
            # Update Metric 2: Classification method distribution (Gauge with labels)
            self.classification_method.labels(method='llm_gpt4').set(
                langgraph_metrics.classification_method_distribution.llm_gpt4
            )
            self.classification_method.labels(method='fallback_regex').set(
                langgraph_metrics.classification_method_distribution.fallback_regex
            )
            
            # Update Metric 3: Circuit breaker trips (Gauge)
            self.circuit_breaker_trips.set(
                langgraph_metrics.circuit_breaker_trips_24h
            )
            
            # Update Metric 4: Processing time histogram (Histogram)
            # Note: Histogram requires observing individual samples, but we only have percentiles
            # Solution: Approximate by observing p50, p95, p99 values multiple times
            # Production recommendation: Store raw processing times in events table
            percentiles = langgraph_metrics.avg_processing_time
            if percentiles.p50 > 0:
                # Observe p50 value 50 times to approximate median bucket
                for _ in range(50):
                    self.processing_time.observe(percentiles.p50)
            if percentiles.p95 > 0:
                # Observe p95 value 45 times (95th - 50th percentile ≈ 45% of samples)
                for _ in range(45):
                    self.processing_time.observe(percentiles.p95)
            if percentiles.p99 > 0:
                # Observe p99 value 4 times (99th - 95th percentile ≈ 4% of samples)
                for _ in range(4):
                    self.processing_time.observe(percentiles.p99)
            
            # Update Metric 5: LLM confidence (Gauge)
            if langgraph_metrics.llm_confidence_avg is not None:
                self.llm_confidence.set(langgraph_metrics.llm_confidence_avg)
            else:
                # Set to -1 to indicate "no LLM classifications in 24h window"
                self.llm_confidence.set(-1.0)
            
            logger.info(
                "prometheus_metrics_updated",
                total_processed=langgraph_metrics.total_processed,
                llm_classifications=langgraph_metrics.classification_method_distribution.llm_gpt4,
                fallback_classifications=langgraph_metrics.classification_method_distribution.fallback_regex,
                circuit_breaker_trips=langgraph_metrics.circuit_breaker_trips_24h,
                llm_confidence=langgraph_metrics.llm_confidence_avg
            )
            
            return True
            
        except Exception as e:
            logger.exception(
                "prometheus_update_exception",
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    def reset_metrics(self) -> None:
        """
        Reset all metrics to zero (useful for testing).
        
        WARNING: Do not call in production - Prometheus expects monotonic counters.
        """
        self.blocks_processed._value.set(0)
        self.classification_method.labels(method='llm_gpt4').set(0)
        self.classification_method.labels(method='fallback_regex').set(0)
        self.circuit_breaker_trips.set(0)
        self.llm_confidence.set(0)
        # Note: Histogram cannot be reset easily, would need to recreate registry
        
        logger.warning("prometheus_metrics_reset", reason="Manual reset called (testing only)")
