"""
Circuit Breaker for OpenAI API (GLOBAL Scope)

Implements Circuit Breaker pattern to prevent cascading failures when OpenAI API is down.

Key Features:
- GLOBAL scope: Trips after 5 failures from ANY block (not per-block)
- Redis persistence: State shared across Celery workers
- In-memory fallback: Degrades gracefully if Redis unavailable
- Auto-recovery: Closes circuit after 5-minute TTL

States:
- CLOSED: Normal operation, LLM calls allowed
- OPEN: Circuit tripped (5+ failures), block all LLM calls → fallback regex
- HALF_OPEN: Recovery attempt, allow limited retries

T-1802-AGENT: Circuit Breaker GLOBAL
"""

import time
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from src.agent.constants import (
    CB_REDIS_KEY,
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIMEOUT_SECONDS,
    CB_HALF_OPEN_MAX_RETRIES,
    CB_MEMORY_FALLBACK_ENABLED,
)

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit Breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit tripped, block requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerStats:
    """Circuit Breaker statistics for monitoring"""
    state: CircuitState
    failure_count: int
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None
    half_open_attempts: int = 0
    total_trips: int = 0  # Lifetime counter
    
    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "opened_at": self.opened_at,
            "half_open_attempts": self.half_open_attempts,
            "total_trips": self.total_trips,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit is open and request is blocked"""
    pass


class CircuitBreaker:
    """
    Global Circuit Breaker for OpenAI API calls.
    
    Scope: GLOBAL (all blocks share same counter)
    Rationale: If OpenAI is down, no point retrying for each block
    
    Redis Schema:
        Key: circuit_breaker:openai:global
        Value: JSON {"failure_count": int, "opened_at": float|null, ...}
        TTL: 300s (auto-recovery)
    
    In-Memory Fallback:
        If Redis unavailable → use process-local counter
        Warning: NOT shared across workers (degraded resilience)
    
    Usage:
        cb = CircuitBreaker(redis_client)
        
        if cb.is_open():
            # Use fallback regex classification
            return fallback_classify()
        
        try:
            result = llm_classify()
            cb.record_success()
            return result
        except LLMError:
            cb.record_failure()
            return fallback_classify()
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize Circuit Breaker.
        
        Args:
            redis_client: Redis client instance (from infra.redis_client)
                         If None or unavailable → in-memory fallback
        """
        self.redis_client = redis_client
        self.use_redis = redis_client is not None
        
        # In-memory fallback state (used if Redis unavailable)
        self._memory_stats = CircuitBreakerStats(
            state=CircuitState.CLOSED,
            failure_count=0,
        )
        
        logger.info(
            "circuit_breaker_initialized",
            use_redis=self.use_redis,
            memory_fallback_enabled=CB_MEMORY_FALLBACK_ENABLED,
        )
    
    def _get_stats_from_redis(self) -> Optional[CircuitBreakerStats]:
        """
        Get Circuit Breaker stats from Redis.
        
        Returns:
            CircuitBreakerStats if Redis available, None otherwise
        """
        if not self.use_redis:
            return None
        
        try:
            import json
            data = self.redis_client.get(CB_REDIS_KEY)
            if data is None:
                # Initialize fresh state in Redis
                return CircuitBreakerStats(
                    state=CircuitState.CLOSED,
                    failure_count=0,
                )
            
            # Parse JSON state
            state_dict = json.loads(data)
            return CircuitBreakerStats(
                state=CircuitState(state_dict["state"]),
                failure_count=state_dict["failure_count"],
                last_failure_time=state_dict.get("last_failure_time"),
                opened_at=state_dict.get("opened_at"),
                half_open_attempts=state_dict.get("half_open_attempts", 0),
                total_trips=state_dict.get("total_trips", 0),
            )
            
        except (RedisConnectionError, RedisError) as e:
            logger.warning(
                "redis_unavailable_fallback_memory",
                error=str(e),
            )
            return None  # Fallback to in-memory
    
    def _save_stats_to_redis(self, stats: CircuitBreakerStats):
        """
        Save Circuit Breaker stats to Redis with TTL.
        
        Args:
            stats: Circuit Breaker statistics to persist
        """
        if not self.use_redis:
            return
        
        try:
            import json
            data = json.dumps(stats.to_dict())
            
            # Set with TTL for auto-recovery
            self.redis_client.setex(
                CB_REDIS_KEY,
                CB_RECOVERY_TIMEOUT_SECONDS,
                data,
            )
            
        except (RedisConnectionError, RedisError) as e:
            logger.warning(
                "redis_save_failed",
                error=str(e),
            )
            # Degrade to in-memory (next call will use _memory_stats)
            self.use_redis = False
    
    def _get_stats(self) -> CircuitBreakerStats:
        """Get current stats (Redis or in-memory fallback)"""
        if self.use_redis:
            stats = self._get_stats_from_redis()
            if stats is not None:
                return stats
            # Redis failed, fall back to memory
            logger.warning("using_memory_fallback")
        
        return self._memory_stats
    
    def _save_stats(self, stats: CircuitBreakerStats):
        """Save stats (Redis or in-memory fallback)"""
        if self.use_redis:
            self._save_stats_to_redis(stats)
        else:
            self._memory_stats = stats
    
    def is_open(self) -> bool:
        """
        Check if circuit is OPEN (requests blocked).
        
        Returns:
            True if circuit is open (use fallback), False otherwise
        """
        stats = self._get_stats()
        
        # If circuit was OPEN, check if recovery timeout expired
        if stats.state == CircuitState.OPEN:
            if stats.opened_at is not None:
                elapsed = time.time() - stats.opened_at
                if elapsed >= CB_RECOVERY_TIMEOUT_SECONDS:
                    # Recovery timeout expired → transition to HALF_OPEN
                    logger.info(
                        "circuit_half_open_recovery",
                        elapsed_seconds=elapsed,
                    )
                    stats.state = CircuitState.HALF_OPEN
                    stats.half_open_attempts = 0
                    self._save_stats(stats)
                    return False  # Allow retry
        
        return stats.state == CircuitState.OPEN
    
    def record_failure(self):
        """
        Record LLM call failure (increment counter, possibly trip circuit).
        
        Behavior:
        - CLOSED state: Increment counter, trip if threshold reached
        - HALF_OPEN state: Re-open circuit on failure
        """
        stats = self._get_stats()
        stats.failure_count += 1
        stats.last_failure_time = time.time()
        
        logger.warning(
            "circuit_breaker_failure_recorded",
            failure_count=stats.failure_count,
            threshold=CB_FAILURE_THRESHOLD,
            state=stats.state.value,
        )
        
        # Check if threshold reached (trip circuit)
        if stats.state == CircuitState.CLOSED:
            if stats.failure_count >= CB_FAILURE_THRESHOLD:
                # Trip circuit → OPEN state
                stats.state = CircuitState.OPEN
                stats.opened_at = time.time()
                stats.total_trips += 1
                
                logger.error(
                    "circuit_breaker_tripped",
                    failure_count=stats.failure_count,
                    threshold=CB_FAILURE_THRESHOLD,
                    total_trips=stats.total_trips,
                )
        
        elif stats.state == CircuitState.HALF_OPEN:
            # Half-open attempt failed → re-open circuit
            stats.state = CircuitState.OPEN
            stats.opened_at = time.time()
            stats.half_open_attempts = 0
            
            logger.warning(
                "circuit_breaker_reopened_after_half_open_failure",
            )
        
        self._save_stats(stats)
    
    def record_success(self):
        """
        Record LLM call success (reset counter if in recovery).
        
        Behavior:
        - CLOSED state: Reset failure counter
        - HALF_OPEN state: Close circuit after success
        """
        stats = self._get_stats()
        
        if stats.state == CircuitState.HALF_OPEN:
            # Half-open attempt succeeded → close circuit
            stats.state = CircuitState.CLOSED
            stats.failure_count = 0
            stats.half_open_attempts = 0
            stats.opened_at = None
            
            logger.info(
                "circuit_breaker_closed_after_recovery",
            )
        
        elif stats.state == CircuitState.CLOSED:
            # Normal success → reset failure counter
            stats.failure_count = 0
        
        self._save_stats(stats)
    
    def get_stats(self) -> CircuitBreakerStats:
        """
        Get current Circuit Breaker statistics (for monitoring endpoint).
        
        Returns:
            CircuitBreakerStats with current state
        """
        return self._get_stats()
    
    def reset(self):
        """
        Manually reset circuit to CLOSED state (admin operation).
        
        Warning: Use only for testing or manual recovery
        """
        stats = CircuitBreakerStats(
            state=CircuitState.CLOSED,
            failure_count=0,
        )
        self._save_stats(stats)
        
        logger.warning("circuit_breaker_manually_reset")


# Singleton instance (shared across Celery tasks in same worker process)
_circuit_breaker_instance: Optional[CircuitBreaker] = None


def get_circuit_breaker(redis_client=None) -> CircuitBreaker:
    """
    Get singleton Circuit Breaker instance.
    
    Args:
        redis_client: Redis client (from infra.redis_client)
                     If None → uses in-memory fallback
    
    Returns:
        CircuitBreaker instance
    """
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None:
        _circuit_breaker_instance = CircuitBreaker(redis_client)
    return _circuit_breaker_instance
