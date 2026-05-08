"""
Unit Tests for Circuit Breaker (GLOBAL)

Tests Circuit Breaker pattern with:
- Redis persistence (GLOBAL scope across workers)
- In-memory fallback (when Redis unavailable)
- State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
- Failure threshold (5 consecutive failures)
- Auto-recovery (300s TTL)
- Manual reset for admin operations

T-1802-AGENT: Circuit Breaker Tests (8 tests)
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.agent.graph.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerStats,
    CircuitBreakerOpenError,
    get_circuit_breaker,
)
from src.agent.constants import (
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIMEOUT_SECONDS,
    CB_HALF_OPEN_MAX_RETRIES,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing persistence"""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None  # No saved state initially
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    return redis_mock


@pytest.fixture
def circuit_breaker_with_redis(mock_redis_client):
    """Circuit Breaker instance with mocked Redis"""
    return CircuitBreaker(mock_redis_client)


@pytest.fixture
def circuit_breaker_no_redis():
    """Circuit Breaker instance without Redis (in-memory fallback)"""
    return CircuitBreaker(redis_client=None)


# ─────────────────────────────────────────────────────────────────────────────
# State Transition Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_circuit_breaker_initial_state_closed(circuit_breaker_with_redis):
    """
    HP-01: Circuit Breaker starts in CLOSED state
    
    Expected: is_open() = False, failure_count = 0
    """
    cb = circuit_breaker_with_redis
    
    assert cb.is_open() is False
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.CLOSED
    assert stats.failure_count == 0


def test_circuit_breaker_trips_after_threshold(circuit_breaker_with_redis):
    """
    HP-02: Circuit Breaker trips after 5 consecutive failures
    
    Transition: CLOSED → OPEN after CB_FAILURE_THRESHOLD failures
    """
    cb = circuit_breaker_with_redis
    
    # Record 4 failures (below threshold)
    for i in range(CB_FAILURE_THRESHOLD - 1):
        cb.record_failure()
        assert cb.is_open() is False  # Still closed
    
    # 5th failure → should trip circuit
    cb.record_failure()
    assert cb.is_open() is True  # Circuit now open
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.OPEN
    assert stats.failure_count == CB_FAILURE_THRESHOLD
    assert stats.total_trips == 1


def test_circuit_breaker_resets_on_success_when_closed(circuit_breaker_with_redis):
    """
    HP-03: Success resets failure count when CLOSED
    
    Scenario: 3 failures → success → failure_count resets to 0
    """
    cb = circuit_breaker_with_redis
    
    # Record 3 failures
    for i in range(3):
        cb.record_failure()
    
    stats = cb.get_stats()
    assert stats.failure_count == 3
    assert stats.state == CircuitState.CLOSED
    
    # Record success → should reset failure count
    cb.record_success()
    
    stats = cb.get_stats()
    assert stats.failure_count == 0
    assert stats.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_success_closes_circuit(circuit_breaker_with_redis):
    """
    HP-04: HALF_OPEN state transitions to CLOSED on success
    
    Transition: OPEN → HALF_OPEN (after timeout) → CLOSED (on success)
    """
    cb = circuit_breaker_with_redis
    
    # Trip circuit (5 failures)
    for i in range(CB_FAILURE_THRESHOLD):
        cb.record_failure()
    
    assert cb.is_open() is True
    
    # Simulate recovery timeout elapsed (use timestamp float)
    stats = cb.get_stats()
    recovery_time = time.time() - CB_RECOVERY_TIMEOUT_SECONDS - 1  # 1 second past recovery
    stats.opened_at = recovery_time
    cb._save_stats(stats)
    
    # Check is_open() → should auto-transition to HALF_OPEN
    is_open = cb.is_open()
    stats = cb.get_stats()
    assert stats.state == CircuitState.HALF_OPEN
    assert is_open is False  # HALF_OPEN allows requests through
    
    # Record success in HALF_OPEN → should close circuit
    cb.record_success()
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.CLOSED
    assert stats.failure_count == 0


def test_circuit_breaker_half_open_failure_reopens_circuit(circuit_breaker_with_redis):
    """
    HP-05: HALF_OPEN state re-opens circuit on failure
    
    Transition: HALF_OPEN → OPEN (if test request fails)
    """
    cb = circuit_breaker_with_redis
    
    # Trip circuit
    for i in range(CB_FAILURE_THRESHOLD):
        cb.record_failure()
    
    # Simulate recovery timeout (transition to HALF_OPEN)
    stats = cb.get_stats()
    recovery_time = time.time() - CB_RECOVERY_TIMEOUT_SECONDS - 1
    stats.opened_at = recovery_time
    cb._save_stats(stats)
    
    cb.is_open()  # Trigger auto-transition to HALF_OPEN
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.HALF_OPEN
    
    # Record failure in HALF_OPEN → should re-open circuit
    cb.record_failure()
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.OPEN
    assert cb.is_open() is True


# ─────────────────────────────────────────────────────────────────────────────
# Redis Persistence Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_circuit_breaker_saves_to_redis(mock_redis_client):
    """
    HP-06: Circuit Breaker persists state to Redis
    
    Expected: setex called with CB_REDIS_KEY, TTL, JSON data
    """
    cb = CircuitBreaker(mock_redis_client)
    
    # Record failure → should save to Redis
    cb.record_failure()
    
    # Verify Redis setex called
    mock_redis_client.setex.assert_called()
    
    # Get call arguments
    call_args = mock_redis_client.setex.call_args
    key = call_args[0][0]
    ttl = call_args[0][1]
    value = call_args[0][2]
    
    assert "circuit_breaker" in key
    assert ttl == CB_RECOVERY_TIMEOUT_SECONDS
    assert "failure_count" in value  # JSON data


def test_circuit_breaker_loads_from_redis(mock_redis_client):
    """
    HP-07: Circuit Breaker loads persisted state from Redis
    
    Scenario: Redis has saved state → new CB instance loads it
    """
    import json
    
    # Simulate existing Redis data (use lowercase state values)
    existing_stats = {
        "state": "open",  # lowercase to match CircuitState enum values
        "failure_count": 5,
        "last_failure_time": time.time(),
        "opened_at": time.time(),
        "half_open_attempts": 0,
        "total_trips": 1,
    }
    mock_redis_client.get.return_value = json.dumps(existing_stats)
    
    # Create new CB instance → should load from Redis
    cb = CircuitBreaker(mock_redis_client)
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.OPEN
    assert stats.failure_count == 5
    assert stats.total_trips == 1


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Fallback Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_circuit_breaker_in_memory_fallback(circuit_breaker_no_redis):
    """
    EC-07: Circuit Breaker uses in-memory fallback when Redis unavailable
    
    Expected: Still functional, but state not shared across workers
    """
    cb = circuit_breaker_no_redis
    
    # Should work without Redis
    assert cb.is_open() is False
    
    # Record failures → should trip circuit (in-memory)
    for i in range(CB_FAILURE_THRESHOLD):
        cb.record_failure()
    
    assert cb.is_open() is True
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.OPEN


# ─────────────────────────────────────────────────────────────────────────────
# Manual Reset Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_circuit_breaker_manual_reset(circuit_breaker_with_redis):
    """
    HP-08: Admin can manually reset Circuit Breaker
    
    Scenario: Circuit OPEN → reset() → CLOSED (emergency override)
    """
    cb = circuit_breaker_with_redis
    
    # Trip circuit
    for i in range(CB_FAILURE_THRESHOLD):
        cb.record_failure()
    
    assert cb.is_open() is True
    
    # Manual reset (admin operation)
    cb.reset()
    
    assert cb.is_open() is False
    
    stats = cb.get_stats()
    assert stats.state == CircuitState.CLOSED
    assert stats.failure_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Singleton Pattern Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_circuit_breaker_singleton():
    """
    HP-09: get_circuit_breaker returns same instance (singleton)
    """
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    
    # Reset singleton for test (avoid contamination)
    import src.agent.graph.circuit_breaker as cb_module
    cb_module._circuit_breaker_instance = None
    
    cb1 = get_circuit_breaker(mock_redis)
    cb2 = get_circuit_breaker(mock_redis)
    
    assert cb1 is cb2  # Same instance
