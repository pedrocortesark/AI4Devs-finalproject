"""
Metrics service - Business logic for LangGraph observability metrics.

This module implements metrics aggregation from the events table to provide
operational visibility into The Librarian agent's performance, classification
methods, and circuit breaker activations.

T-1809-INFRA: Observability & Metrics Endpoint
"""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import json
from supabase import Client
import structlog

from constants import (
    METRICS_WINDOW_HOURS,
    PERCENTILES,
    EVENT_TYPE_GRAPH_COMPLETED,
    EVENT_TYPE_FALLBACK_ACTIVATED,
)
from schemas import (
    LangGraphMetricsResponse,
    ClassificationDistribution,
    ProcessingTimeHistogram,
)

logger = structlog.get_logger()


class MetricsService:
    """
    Service class for LangGraph metrics aggregation.
    
    Aggregates operational metrics from the events table to provide insights into:
    - Total blocks processed (all-time counter)
    - Classification method distribution (LLM vs fallback, 24h window)
    - Circuit breaker trips (24h window)
    - Processing time percentiles (p50, p95, p99)
    - Average LLM confidence (24h window)
    
    T-1809 Optional Feature: Redis caching (60s TTL) to reduce DB load.
    """
    
    # Cache configuration
    CACHE_KEY = "metrics:langgraph:latest"
    CACHE_TTL = 60  # 60 seconds
    
    def __init__(self, supabase_client: Client):
        """
        Initialize metrics service.
        
        Args:
            supabase_client: Configured Supabase client instance
        """
        self.supabase = supabase_client
    
    def get_langgraph_metrics(self) -> Tuple[bool, Optional[LangGraphMetricsResponse], Optional[str]]:
        """
        Aggregate LangGraph metrics from events table.
        
        T-1809 Optional Feature: Implements Redis caching with 60s TTL to reduce
        database load during high-frequency Prometheus scraping (every 15-30s).
        
        Cache Strategy:
            - Key: "metrics:langgraph:latest"
            - TTL: 60 seconds
            - Invalidation: Automatic expiry (no manual flush)
            - Fallback: If Redis fails, query DB directly (graceful degradation)
        
        Performance Impact:
            - Cache Hit: <10ms (98% faster than DB query)
            - Cache Miss: ~200-500ms (DB query + cache write)
            - Expected Hit Rate: ~75% (with 15s scrape interval)
        
        Returns:
            Tuple of (success, metrics_response, error_message)
            - success: True if metrics generated successfully
            - metrics_response: LangGraphMetricsResponse object or None
            - error_message: Error description or None
        """
        try:
            # Attempt to get cached metrics from Redis
            try:
                from infra.redis_client import get_redis_client
                redis = get_redis_client()
                cached = redis.get(self.CACHE_KEY)
                
                if cached:
                    logger.info(
                        "langgraph.metrics.cache_hit",
                        cache_key=self.CACHE_KEY,
                        ttl=self.CACHE_TTL
                    )
                    metrics_dict = json.loads(cached)
                    metrics = LangGraphMetricsResponse(**metrics_dict)
                    return True, metrics, None
                    
                logger.debug(
                    "langgraph.metrics.cache_miss",
                    cache_key=self.CACHE_KEY,
                    reason="Key expired or not found"
                )
                
            except Exception as redis_error:
                # Graceful degradation: If Redis fails, continue with DB query
                logger.warning(
                    "langgraph.metrics.cache_error",
                    error=str(redis_error),
                    fallback="Querying DB directly"
                )
            
            # Cache miss or Redis unavailable - Query database
            # Calculate 24h window
            window_start = datetime.utcnow() - timedelta(hours=METRICS_WINDOW_HOURS)
            
            # Query metrics
            total_processed = self._query_total_processed()
            classification_dist = self._query_classification_distribution(window_start)
            circuit_breaker_trips = self._query_circuit_breaker_trips(window_start)
            processing_time_histogram = self._query_processing_time_percentiles(window_start)
            llm_confidence_avg = self._query_llm_confidence_avg(window_start)
            
            # Build response
            metrics = LangGraphMetricsResponse(
                total_processed=total_processed,
                classification_method_distribution=classification_dist,
                circuit_breaker_trips_24h=circuit_breaker_trips,
                avg_processing_time=processing_time_histogram,
                llm_confidence_avg=llm_confidence_avg,
                generated_at=datetime.utcnow().isoformat() + "Z"
            )
            
            # Cache the result for 60 seconds
            try:
                from infra.redis_client import get_redis_client
                redis = get_redis_client()
                redis.setex(
                    self.CACHE_KEY,
                    self.CACHE_TTL,
                    json.dumps(metrics.model_dump())
                )
                logger.debug(
                    "langgraph.metrics.cached",
                    cache_key=self.CACHE_KEY,
                    ttl=self.CACHE_TTL
                )
            except Exception as cache_write_error:
                # Non-critical: Cache write failure doesn't affect response
                logger.warning(
                    "langgraph.metrics.cache_write_failed",
                    error=str(cache_write_error)
                )
            
            logger.info(
                "langgraph.metrics.generated",
                total_processed=total_processed,
                circuit_breaker_trips=circuit_breaker_trips,
                window_hours=METRICS_WINDOW_HOURS
            )
            
            return True, metrics, None
            
        except Exception as e:
            logger.error("langgraph.metrics.error", error=str(e), exc_info=True)
            return False, None, f"Failed to generate metrics: {str(e)}"
    
    def _query_total_processed(self) -> int:
        """
        Count total blocks processed since system start.
        
        Returns:
            Total count of GRAPH_COMPLETED events
        """
        try:
            result = self.supabase.table("events") \
                .select("id", count="exact") \
                .eq("event_type", EVENT_TYPE_GRAPH_COMPLETED) \
                .execute()
            
            return result.count if result.count else 0
        except Exception as e:
            logger.warning("metrics.total_processed.error", error=str(e))
            return 0
    
    def _query_classification_distribution(self, window_start: datetime) -> ClassificationDistribution:
        """
        Calculate distribution of classification methods (24h window).
        
        Args:
            window_start: Start of 24h time window
            
        Returns:
            ClassificationDistribution with llm_gpt4 and fallback_regex counts
        """
        try:
            # Query events with state_snapshot containing classification_method
            result = self.supabase.table("events") \
                .select("state_snapshot") \
                .eq("event_type", EVENT_TYPE_GRAPH_COMPLETED) \
                .gte("created_at", window_start.isoformat()) \
                .execute()
            
            llm_count = 0
            fallback_count = 0
            
            for event in result.data:
                if event.get("state_snapshot"):
                    method = event["state_snapshot"].get("classification_method", "")
                    if method == "LLM_GPT4":
                        llm_count += 1
                    elif method == "FALLBACK_REGEX":
                        fallback_count += 1
            
            return ClassificationDistribution(
                llm_gpt4=llm_count,
                fallback_regex=fallback_count
            )
        except Exception as e:
            logger.warning("metrics.classification_dist.error", error=str(e))
            return ClassificationDistribution()
    
    def _query_circuit_breaker_trips(self, window_start: datetime) -> int:
        """
        Count circuit breaker activations (24h window).
        
        Args:
            window_start: Start of 24h time window
            
        Returns:
            Count of FALLBACK_ACTIVATED events
        """
        try:
            result = self.supabase.table("events") \
                .select("id", count="exact") \
                .eq("event_type", EVENT_TYPE_FALLBACK_ACTIVATED) \
                .gte("created_at", window_start.isoformat()) \
                .execute()
            
            return result.count if result.count else 0
        except Exception as e:
            logger.warning("metrics.circuit_breaker.error", error=str(e))
            return 0
    
    def _query_processing_time_percentiles(self, window_start: datetime) -> ProcessingTimeHistogram:
        """
        Calculate processing time percentiles (p50, p95, p99).
        
        NOTE: This is a simplified implementation. For production, consider using
        PostgreSQL's percentile_cont() function for better performance.
        
        Args:
            window_start: Start of 24h time window
            
        Returns:
            ProcessingTimeHistogram with p50, p95, p99
        """
        try:
            # Query GRAPH_STARTED and GRAPH_COMPLETED events grouped by block_id
            result = self.supabase.table("events") \
                .select("block_id, event_type, created_at") \
                .in_("event_type", ["GRAPH_STARTED", EVENT_TYPE_GRAPH_COMPLETED]) \
                .gte("created_at", window_start.isoformat()) \
                .order("created_at") \
                .execute()
            
            # Group by block_id and calculate durations
            durations = []
            block_times: Dict[str, Dict[str, Any]] = {}
            
            for event in result.data:
                block_id = event["block_id"]
                if block_id not in block_times:
                    block_times[block_id] = {}
                
                if event["event_type"] == "GRAPH_STARTED":
                    block_times[block_id]["start"] = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
                elif event["event_type"] == EVENT_TYPE_GRAPH_COMPLETED:
                    block_times[block_id]["end"] = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            
            # Calculate durations in seconds
            for block_id, times in block_times.items():
                if "start" in times and "end" in times:
                    duration = (times["end"] - times["start"]).total_seconds()
                    durations.append(duration)
            
            # Calculate percentiles
            if not durations:
                return ProcessingTimeHistogram()
            
            durations.sort()
            n = len(durations)
            
            p50 = durations[int(n * 0.50)] if n > 0 else 0.0
            p95 = durations[int(n * 0.95)] if n > 0 else 0.0
            p99 = durations[int(n * 0.99)] if n > 0 else 0.0
            
            return ProcessingTimeHistogram(p50=p50, p95=p95, p99=p99)
            
        except Exception as e:
            logger.warning("metrics.processing_time.error", error=str(e))
            return ProcessingTimeHistogram()
    
    def _query_llm_confidence_avg(self, window_start: datetime) -> Optional[float]:
        """
        Calculate average LLM confidence score (24h window).
        
        Args:
            window_start: Start of 24h time window
            
        Returns:
            Average confidence score (0-1) or None if no LLM classifications
        """
        try:
            result = self.supabase.table("events") \
                .select("state_snapshot") \
                .eq("event_type", EVENT_TYPE_GRAPH_COMPLETED) \
                .gte("created_at", window_start.isoformat()) \
                .execute()
            
            confidences = []
            for event in result.data:
                if event.get("state_snapshot"):
                    snapshot = event["state_snapshot"]
                    if snapshot.get("classification_method") == "LLM_GPT4":
                        confidence = snapshot.get("llm_confidence")
                        if confidence is not None:
                            confidences.append(float(confidence))
            
            if not confidences:
                return None
            
            return sum(confidences) / len(confidences)
            
        except Exception as e:
            logger.warning("metrics.llm_confidence.error", error=str(e))
            return None
