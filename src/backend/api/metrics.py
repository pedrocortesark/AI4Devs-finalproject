"""
Metrics API router - Endpoints for LangGraph observability.

This module exposes metrics endpoints for monitoring The Librarian agent's
operational performance, classification methods, and circuit breaker status.

T-1809-INFRA: Observability & Metrics Endpoint
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import structlog

from infra.supabase_client import get_supabase_client
from services.metrics_service import MetricsService
from schemas import LangGraphMetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = structlog.get_logger()


@router.get("/langgraph", response_model=LangGraphMetricsResponse)
async def get_langgraph_metrics() -> LangGraphMetricsResponse:
    """
    Get LangGraph agent operational metrics.
    
    Returns aggregated metrics from the events table including:
    - Total blocks processed (all-time)
    - Classification method distribution (LLM vs fallback, 24h)
    - Circuit breaker trips (24h)
    - Processing time percentiles (p50, p95, p99)
    - Average LLM confidence (24h)
    
    Returns:
        LangGraphMetricsResponse: Aggregated metrics
        
    Raises:
        HTTPException: 500 if metrics generation fails
    """
    try:
        supabase = get_supabase_client()
        metrics_service = MetricsService(supabase)
        
        success, metrics, error = metrics_service.get_langgraph_metrics()
        
        if not success:
            logger.error("metrics.endpoint.error", error=error)
            raise HTTPException(status_code=500, detail=error or "Failed to generate metrics")
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("metrics.endpoint.unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
