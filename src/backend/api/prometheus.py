"""
Prometheus metrics endpoint for LangGraph observability.

Exposes /metrics endpoint in Prometheus text exposition format for scraping.

T-1809-INFRA: Optional feature - Prometheus exporter endpoint.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import structlog

from infra.supabase_client import get_supabase_client
from services.metrics_service import MetricsService
from services.prometheus_service import PrometheusService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["prometheus"])


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    Prometheus scrape endpoint.
    
    Returns metrics in Prometheus text exposition format for scraping by Prometheus server.
    
    **Exposed Metrics:**
    
    1. `langgraph_blocks_processed_total` (counter) - Total blocks processed since system start
    2. `langgraph_classification_method{method="llm_gpt4|fallback_regex"}` (gauge) - Classification distribution (24h)
    3. `langgraph_circuit_breaker_trips_24h` (gauge) - Circuit breaker activations (24h)
    4. `langgraph_processing_time_seconds` (histogram) - Processing time distribution (24h, buckets: 1s, 5s, 10s, 30s, 1m, 2m, 5m)
    5. `langgraph_llm_confidence` (gauge) - Average LLM confidence 0-1 (24h, -1 if no LLM classifications)
    
    **Prometheus Scrape Configuration:**
    
    ```yaml
    # prometheus.yml
    scrape_configs:
      - job_name: 'langgraph-metrics'
        scrape_interval: 15s
        static_configs:
          - targets: ['backend:8000']
        metrics_path: '/metrics'
    ```
    
    **Response Format:**
    
    ```
    # HELP langgraph_blocks_processed_total Total blocks processed by The Librarian since system start
    # TYPE langgraph_blocks_processed_total counter
    langgraph_blocks_processed_total 1523.0
    
    # HELP langgraph_classification_method Number of blocks classified by each method (24h)
    # TYPE langgraph_classification_method gauge
    langgraph_classification_method{method="llm_gpt4"} 1402.0
    langgraph_classification_method{method="fallback_regex"} 121.0
    
    # HELP langgraph_circuit_breaker_trips_24h Number of circuit breaker activations in last 24 hours
    # TYPE langgraph_circuit_breaker_trips_24h gauge
    langgraph_circuit_breaker_trips_24h 12.0
    
    # HELP langgraph_processing_time_seconds Block processing time distribution (24h)
    # TYPE langgraph_processing_time_seconds histogram
    langgraph_processing_time_seconds_bucket{le="1"} 0.0
    langgraph_processing_time_seconds_bucket{le="5"} 45.0
    langgraph_processing_time_seconds_bucket{le="10"} 850.0
    langgraph_processing_time_seconds_bucket{le="30"} 1380.0
    langgraph_processing_time_seconds_bucket{le="60"} 1500.0
    langgraph_processing_time_seconds_bucket{le="120"} 1520.0
    langgraph_processing_time_seconds_bucket{le="300"} 1523.0
    langgraph_processing_time_seconds_bucket{le="+Inf"} 1523.0
    langgraph_processing_time_seconds_count 1523.0
    langgraph_processing_time_seconds_sum 18276.5
    
    # HELP langgraph_llm_confidence Average LLM confidence score (0-1) for blocks classified via GPT-4 (24h)
    # TYPE langgraph_llm_confidence gauge
    langgraph_llm_confidence 0.87
    ```
    
    Returns:
        Response: Prometheus text format (text/plain; version=0.0.4; charset=utf-8)
    
    Raises:
        HTTPException 500: If metrics generation fails
    
    Performance:
        - Cold start: ~200-500ms (queries Supabase events table)
        - With cache: <100ms (if MetricsService has Redis caching enabled)
    
    Monitoring:
        - Prometheus should scrape every 15-30 seconds
        - Set scrape_timeout to 10s to handle cold starts
    """
    try:
        # Initialize services
        supabase = get_supabase_client()
        metrics_service = MetricsService(supabase)
        prometheus_service = PrometheusService(metrics_service)
        
        # Fetch latest metrics from database and update Prometheus collectors
        success = prometheus_service.update_metrics()
        
        if not success:
            logger.error(
                "prometheus_endpoint_failed",
                endpoint="/metrics",
                reason="PrometheusService.update_metrics() returned False"
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to generate Prometheus metrics. Check logs for database connectivity."
            )
        
        # Generate Prometheus text exposition format
        metrics_output = generate_latest(prometheus_service.registry)
        
        logger.info(
            "prometheus_endpoint_success",
            endpoint="/metrics",
            content_type=CONTENT_TYPE_LATEST,
            bytes_generated=len(metrics_output)
        )
        
        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST
        )
        
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    
    except Exception as e:
        logger.exception(
            "prometheus_endpoint_exception",
            endpoint="/metrics",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error generating Prometheus metrics: {str(e)}"
        )
