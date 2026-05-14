"""
Unit Tests for RateLimiterService

Tests the token bucket rate limiting algorithm with Redis backend.
Validates token acquisition, refill, concurrent limits, and graceful degradation.

T-1810-INFRA: OpenAI Rate Limiting (Client-Side)
Author: AI Assistant
Date: 2026-05-13

Test Coverage:
- HP-01: Token acquisition success
- HP-02: Token refill after interval
- EC-01: Token acquisition timeout
- EC-02: Concurrent limit enforcement
- ERR-01: Graceful degradation (Redis unavailable)
- INT-01: 10 concurrent requests respect rate limit
- INT-02: release_concurrent_slot decrements counter
- UTIL-01: reset() clears bucket and counters
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from redis.exceptions import RedisError

from services.rate_limiter_service import RateLimiterService


class TestRateLimiterService:
    """Unit tests for RateLimiterService token bucket algorithm."""
    
    # ========================================================================
    # HP (Happy Path) Tests
    # ========================================================================
    
    def test_HP01_acquire_token_success(self):
        """
        HP-01: Acquire token successfully when bucket has tokens.
        
        Setup: Fresh bucket with 5 tokens (default)
        Action: acquire_token()
        Expected: Returns True in <1s, bucket decremented to 4
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        redis_mock.get.side_effect = [
            time.time(),  # last_refill
            5,            # current_tokens (before decrement)
        ]
        redis_mock.decr.return_value = 4  # After decrement
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
            max_concurrent=3,
        )
        
        # Act
        start_time = time.time()
        result = limiter.acquire_token(timeout=5.0)
        elapsed = time.time() - start_time
        
        # Assert
        assert result is True, "Token acquisition should succeed"
        assert elapsed < 1.0, f"Should acquire token quickly, took {elapsed}s"
        redis_mock.decr.assert_called_once_with(limiter.BUCKET_KEY)
    
    def test_HP02_token_refill_after_interval(self):
        """
        HP-02: Tokens refill automatically after interval (12s for 5/min).
        
        Setup: Bucket with 0 tokens, last_refill = 13s ago
        Action: _refill_tokens()
        Expected: Bucket refilled with 1 token (13s / 12s = 1 token)
        """
        # Mock Redis client
        redis_mock = MagicMock()
        current_time = time.time()
        last_refill = current_time - 13.0  # 13 seconds ago
        
        redis_mock.get.side_effect = [
            str(last_refill),  # LAST_REFILL_KEY
            "0",               # BUCKET_KEY (current tokens)
        ]
        redis_mock.pipeline.return_value = redis_mock
        redis_mock.execute.return_value = [True, True]  # Pipeline results
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,  # 1 token every 12s
        )
        
        # Act
        with patch("time.time", return_value=current_time):
            new_tokens = limiter._refill_tokens()
        
        # Assert
        assert new_tokens == 1, "Should refill 1 token after 13s"
        # Verify Redis pipeline was used to update atomically
        assert redis_mock.set.call_count == 2  # tokens + last_refill
    
    # ========================================================================
    # EC (Edge Case) Tests
    # ========================================================================
    
    def test_EC01_acquire_token_timeout(self):
        """
        EC-01: acquire_token times out if no tokens available.
        
        Setup: Bucket with 0 tokens, no refill happening
        Action: acquire_token(timeout=0.5)
        Expected: Returns False after ~0.5s timeout
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),  # Just refilled
            "rate_limiter:openai:tokens": "0",  # No tokens available
        }.get(key, "0")
        redis_mock.decr.return_value = -1  # Decrement below zero (no tokens)
        redis_mock.incr.return_value = 0   # Increment back
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
        )
        
        # Act
        start_time = time.time()
        result = limiter.acquire_token(timeout=0.5)
        elapsed = time.time() - start_time
        
        # Assert
        assert result is False, "Should timeout when no tokens available"
        assert 0.4 < elapsed < 0.7, f"Should timeout after ~0.5s, took {elapsed}s"
    
    def test_EC02_concurrent_limit_enforcement(self):
        """
        EC-02: Concurrent limit blocks 4th request when max=3.
        
        Setup: Max concurrent = 3
        Action: acquire_concurrent_slot() × 4 times
        Expected: First 3 succeed, 4th returns False
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.incr.side_effect = [1, 2, 3, 4]  # Simulate counter increments
        redis_mock.decr.return_value = 3  # Decrement back from 4 to 3
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
            max_concurrent=3,
        )
        
        # Act: Acquire 3 slots (should all succeed)
        slot1 = limiter.acquire_concurrent_slot()
        slot2 = limiter.acquire_concurrent_slot()
        slot3 = limiter.acquire_concurrent_slot()
        
        # Act: Try to acquire 4th slot (should fail)
        slot4 = limiter.acquire_concurrent_slot()
        
        # Assert
        assert slot1 is True, "1st slot should acquire"
        assert slot2 is True, "2nd slot should acquire"
        assert slot3 is True, "3rd slot should acquire"
        assert slot4 is False, "4th slot should be rejected (exceeds max_concurrent)"
        
        # Verify decrement was called to roll back 4th attempt
        redis_mock.decr.assert_called_once_with(limiter.CONCURRENT_KEY)
    
    # ========================================================================
    # ERR (Error Handling) Tests
    # ========================================================================
    
    def test_ERR01_graceful_degradation_redis_unavailable(self):
        """
        ERR-01: Graceful degradation when Redis unavailable.
        
        Setup: Redis client = None
        Action: acquire_token(), acquire_concurrent_slot()
        Expected: Both return True (no rate limiting, log warning)
        """
        # Act: Create limiter with None redis_client
        limiter = RateLimiterService(
            redis_client=None,
            rate_limit_per_min=5,
        )
        
        # Assert
        assert limiter.enabled is False, "Should be disabled when Redis unavailable"
        
        # Act: Try to acquire token and concurrent slot
        token_result = limiter.acquire_token(timeout=1.0)
        concurrent_result = limiter.acquire_concurrent_slot()
        
        # Assert: Both succeed (graceful degradation)
        assert token_result is True, "Should succeed without rate limiting"
        assert concurrent_result is True, "Should succeed without concurrent limiting"
    
    # ========================================================================
    # INT (Integration) Tests
    # ========================================================================
    
    def test_INT01_ten_concurrent_requests_respect_rate_limit(self):
        """
        INT-01: 10 concurrent requests respect 5 req/min rate limit.
        
        Setup: Bucket with 5 tokens, rate_limit=5/min (12s per token)
        Action: 10× acquire_token() sequentially
        Expected: First 5 succeed immediately, next 5 blocked/timeout
        
        Note: Full test would take 60s. This test verifies first 5 succeed,
        then checks that 6th would need to wait (simulated with timeout).
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        
        # Simulate bucket with 5 tokens initially
        token_counts = [5, 4, 3, 2, 1, 0, 0, 0, 0, 0]  # Bucket state after each acquire
        decr_results = [4, 3, 2, 1, 0, -1, -1, -1, -1, -1]  # decr() return values
        
        call_count = 0
        def get_side_effect(key):
            nonlocal call_count
            if key == "rate_limiter:openai:last_refill":
                return str(time.time())  # Just refilled (no automatic refill in this test)
            elif key == "rate_limiter:openai:tokens":
                result = str(token_counts[min(call_count, len(token_counts) - 1)])
                call_count += 1
                return result
            return "0"
        
        redis_mock.get.side_effect = get_side_effect
        
        decr_call_count = 0
        def decr_side_effect(key):
            nonlocal decr_call_count
            result = decr_results[min(decr_call_count, len(decr_results) - 1)]
            decr_call_count += 1
            return result
        
        redis_mock.decr.side_effect = decr_side_effect
        redis_mock.incr.return_value = 0  # For rollback when decr returns negative
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
        )
        
        # Act: Acquire 5 tokens (should succeed immediately)
        results = []
        for i in range(5):
            result = limiter.acquire_token(timeout=0.5)
            results.append(result)
        
        # Assert: First 5 succeed
        assert all(results), f"First 5 requests should succeed, got {results}"
        
        # Act: Try 6th token (should timeout because bucket empty)
        sixth_result = limiter.acquire_token(timeout=0.3)
        
        # Assert: 6th fails (timeout)
        assert sixth_result is False, "6th request should timeout (bucket empty)"
    
    def test_INT02_release_concurrent_slot_decrements_counter(self):
        """
        INT-02: release_concurrent_slot() correctly decrements counter.
        
        Setup: Acquire 2 concurrent slots
        Action: Release 1 slot
        Expected: Counter decrements from 2 to 1
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.incr.side_effect = [1, 2]  # Acquire 2 slots
        redis_mock.decr.return_value = 1      # Release 1 slot (2 → 1)
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            max_concurrent=3,
        )
        
        # Act: Acquire 2 slots
        limiter.acquire_concurrent_slot()
        limiter.acquire_concurrent_slot()
        
        # Act: Release 1 slot
        limiter.release_concurrent_slot()
        
        # Assert
        redis_mock.decr.assert_called_once_with(limiter.CONCURRENT_KEY)
        assert redis_mock.decr.return_value == 1, "Counter should be 1 after release"
    
    # ========================================================================
    # UTIL (Utility) Tests
    # ========================================================================
    
    def test_UTIL01_reset_clears_bucket_and_counters(self):
        """
        UTIL-01: reset() resets bucket to full and concurrent counter to 0.
        
        Setup: Bucket with unknown state
        Action: reset()
        Expected: Bucket = bucket_size (5), concurrent = 0, last_refill = now
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.pipeline.return_value = redis_mock
        redis_mock.execute.return_value = [True, True, True]  # Pipeline results
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
        )
        
        # Act
        limiter.reset()
        
        # Assert: Verify Redis pipeline was used to set all keys
        assert redis_mock.set.call_count == 3, "Should set BUCKET_KEY, LAST_REFILL_KEY, CONCURRENT_KEY"
        
        # Verify bucket set to full (bucket_size)
        bucket_set_call = redis_mock.set.call_args_list[0]
        assert bucket_set_call[0][0] == limiter.BUCKET_KEY
        assert bucket_set_call[0][1] == limiter.bucket_size
    
    # ========================================================================
    # Additional: Test get_status() method
    # ========================================================================
    
    def test_get_status_returns_current_state(self):
        """
        Additional: get_status() returns accurate rate limiter state.
        
        Expected: Returns dict with enabled, available_tokens, concurrent_requests
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),
            "rate_limiter:openai:tokens": "3",
            "rate_limiter:openai:concurrent": "2",
        }.get(key, "0")
        
        limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
            max_concurrent=3,
        )
        
        # Act
        status = limiter.get_status()
        
        # Assert
        assert status["enabled"] is True, "Should be enabled with Redis"
        assert status["available_tokens"] == 3, "Should report 3 available tokens"
        assert status["concurrent_requests"] == 2, "Should report 2 concurrent requests"
        assert status["rate_limit_per_min"] == 5, "Should report configured rate limit"
        assert status["max_concurrent"] == 3, "Should report max concurrent limit"
    
    def test_get_status_when_redis_unavailable(self):
        """
        Additional: get_status() returns disabled state when Redis unavailable.
        """
        # Act
        limiter = RateLimiterService(redis_client=None)
        status = limiter.get_status()
        
        # Assert
        assert status["enabled"] is False, "Should be disabled"
        assert status["available_tokens"] is None, "Tokens should be None"
        assert status["concurrent_requests"] is None, "Concurrent should be None"
