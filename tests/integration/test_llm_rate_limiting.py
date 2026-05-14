"""
Integration Tests for LLM Rate Limiting

Tests the integration of RateLimiterService with LLMClient to verify
rate limiting prevents HTTP 429 errors during batch processing.

T-1810-INFRA: OpenAI Rate Limiting (Client-Side)
Author: AI Assistant
Date: 2026-05-13

Test Coverage:
- HP-01: Single LLM request acquires and releases token/slot
- EC-01: Concurrent limit enforcement (max 3 requests)
- INT-01: Multiple requests respect rate limit
- INT-02: Graceful degradation when Redis unavailable
- INT-03: Rate limiter timeout triggers fallback

Note: Full batch tests (100 files) are in test_batch_upload.py (manual validation)
"""

import pytest
from unittest.mock import MagicMock, patch
import time

# Import LLMClient and RateLimiterService
# Note: Tests run in backend container, imports are relative to src/backend/
try:
    from src.agent.graph.llm_client import LLMClient, LLMClassificationError
except ImportError:
    # If running from agent context
    from agent.graph.llm_client import LLMClient, LLMClassificationError

from services.rate_limiter_service import RateLimiterService


class TestLLMRateLimiting:
    """Integration tests for LLM rate limiting with RateLimiterService."""
    
    # ========================================================================
    # HP (Happy Path) Tests
    # ========================================================================
    
    def test_HP01_single_llm_request_acquires_and_releases(self):
        """
        HP-01: Single LLM request successfully acquires token and concurrent slot.
        
        Setup: Mock LLMClient with RateLimiterService
        Action: classify_tipologia()
        Expected: Token acquired, concurrent slot acquired, both released
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),
            "rate_limiter:openai:tokens": "5",  # Full bucket
            "rate_limiter:openai:concurrent": "0",
        }.get(key, "0")
        redis_mock.decr.return_value = 4  # Token acquired (5 → 4)
        redis_mock.incr.return_value = 1  # Concurrent slot acquired
        
        # Create rate limiter with mock Redis
        rate_limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
            max_concurrent=3,
        )
        
        # Mock OpenAI response
        with patch("src.agent.graph.llm_client.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"tipologia": "dovela", "confidence": 0.85, "reasoning": "Test"}'
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance
            
            # Create LLMClient with our rate limiter
            llm_client = LLMClient(rate_limiter=rate_limiter)
            
            # Act: Classify
            result = llm_client.classify_tipologia(
                volume=1.5,
                bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
                layers=["SF-C12-D-001"],
                vertices_count=1000,
                iso_code="SF-C12-D-001",
            )
        
        # Assert: Classification succeeded
        assert result["tipologia"] == "dovela"
        assert result["confidence"] == 0.85
        
        # Assert: Token was acquired (decr called on BUCKET_KEY)
        bucket_decr_calls = [call for call in redis_mock.decr.call_args_list 
                            if call[0][0] == rate_limiter.BUCKET_KEY]
        assert len(bucket_decr_calls) > 0, "Should call decr on BUCKET_KEY for token acquisition"
        
        # Assert: Concurrent slot was released (decr called on CONCURRENT_KEY)
        concurrent_decr_calls = [call for call in redis_mock.decr.call_args_list 
                                if call[0][0] == rate_limiter.CONCURRENT_KEY]
        assert len(concurrent_decr_calls) > 0, "Should call decr on CONCURRENT_KEY for slot release"
    
    # ========================================================================
    # EC (Edge Case) Tests
    # ========================================================================
    
    def test_EC01_concurrent_limit_enforcement(self):
        """
        EC-01: Max concurrent limit (3) blocks 4th request.
        
        Setup: RateLimiter with max_concurrent=3
        Action: Simulate 4 concurrent requests
        Expected: 4th request fails with LLMClassificationError
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),
            "rate_limiter:openai:tokens": "10",  # Plenty of tokens
            "rate_limiter:openai:concurrent": "0",
        }.get(key, "0")
        
        # Simulate concurrent counter incrementing
        incr_counter = 0
        def incr_side_effect(key):
            nonlocal incr_counter
            incr_counter += 1
            return incr_counter
        
        redis_mock.incr.side_effect = incr_side_effect
        redis_mock.decr.return_value = 3  # Rollback from 4 to 3
        
        # Create rate limiter
        rate_limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=10,
            max_concurrent=3,  # Max 3 concurrent
        )
        
        # Mock OpenAI response (won't be reached for 4th request)
        with patch("src.agent.graph.llm_client.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"tipologia": "dovela", "confidence": 0.85, "reasoning": "Test"}'
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance
            
            llm_client = LLMClient(rate_limiter=rate_limiter)
            
            # Acquire 3 concurrent slots manually (simulate 3 active requests)
            rate_limiter.acquire_concurrent_slot()
            rate_limiter.acquire_concurrent_slot()
            rate_limiter.acquire_concurrent_slot()
            
            # Act: Try 4th request (should fail due to concurrent limit)
            redis_mock.decr.return_value = 4  # For token acquisition
            redis_mock.get.side_effect = lambda key: {
                "rate_limiter:openai:last_refill": str(time.time()),
                "rate_limiter:openai:tokens": "10",
                "rate_limiter:openai:concurrent": "3",  # Already at max
            }.get(key, "3" if "concurrent" in key else "10")
            
            # Reset incr counter to simulate 4th attempt
            incr_counter = 3
            
            with pytest.raises(LLMClassificationError) as exc_info:
                llm_client.classify_tipologia(
                    volume=1.5,
                    bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
                    layers=["SF-C12-D-001"],
                    vertices_count=1000,
                    iso_code="SF-C12-D-001-4th",
                )
            
            # Assert: Error message mentions concurrent limit
            assert "Max concurrent" in str(exc_info.value)
    
    # ========================================================================
    # INT (Integration) Tests
    # ========================================================================
    
    def test_INT01_multiple_requests_respect_rate_limit(self):
        """
        INT-01: Multiple LLM requests respect rate limit (simplified version).
        
        Setup: RateLimiter with 5 tokens initially
        Action: 5 classify_tipologia() calls
        Expected: All 5 succeed (consume all tokens)
        
        Note: Full batch test (100 files, ~20 min) is in test_batch_upload.py
        """
        # Mock Redis client
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        
        token_count = 5
        def decr_side_effect(key):
            nonlocal token_count
            if "tokens" in key:
                token_count -= 1
                return token_count
            return 0  # For concurrent counter
        
        redis_mock.decr.side_effect = decr_side_effect
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),
            "rate_limiter:openai:tokens": str(max(token_count, 0)),
            "rate_limiter:openai:concurrent": "0",
        }.get(key, "0")
        redis_mock.incr.return_value = 1  # Concurrent slot
        
        rate_limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
            max_concurrent=5,  # Allow all 5 concurrent for this test
        )
        
        # Mock OpenAI response
        with patch("src.agent.graph.llm_client.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"tipologia": "dovela", "confidence": 0.85, "reasoning": "Test"}'
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance
            
            llm_client = LLMClient(rate_limiter=rate_limiter)
            
            # Act: Make 5 requests
            results = []
            for i in range(5):
                result = llm_client.classify_tipologia(
                    volume=1.5,
                    bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
                    layers=["SF-C12-D-001"],
                    vertices_count=1000,
                    iso_code=f"SF-C12-D-{i:03d}",
                )
                results.append(result)
        
        # Assert: All 5 succeeded
        assert len(results) == 5, "All 5 requests should succeed"
        assert all(r["tipologia"] == "dovela" for r in results)
        
        # Assert: Token bucket depleted
        assert token_count == 0, "All 5 tokens should be consumed"
    
    def test_INT02_graceful_degradation_redis_unavailable(self):
        """
        INT-02: LLMClient works without rate limiting when Redis unavailable.
        
        Setup: RateLimiterService with redis_client=None
        Action: classify_tipologia()
        Expected: Classification succeeds (no rate limiting applied)
        """
        # Create rate limiter with None redis_client
        rate_limiter = RateLimiterService(
            redis_client=None,  # Simulate Redis unavailable
            rate_limit_per_min=5,
        )
        
        assert rate_limiter.enabled is False, "Should be disabled without Redis"
        
        # Mock OpenAI response
        with patch("src.agent.graph.llm_client.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"tipologia": "columna", "confidence": 0.90, "reasoning": "Test"}'
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm_instance
            
            llm_client = LLMClient(rate_limiter=rate_limiter)
            
            # Act: Classify (should succeed without rate limiting)
            result = llm_client.classify_tipologia(
                volume=5.0,
                bbox={"min": [0, 0, 0], "max": [2, 2, 2]},
                layers=["SF-C12-CO-001"],
                vertices_count=5000,
                iso_code="SF-C12-CO-001",
            )
        
        # Assert: Classification succeeded
        assert result["tipologia"] == "columna"
        assert result["confidence"] == 0.90
    
    def test_INT03_rate_limiter_timeout_raises_error(self):
        """
        INT-03: Rate limiter timeout triggers LLMClassificationError.
        
        Setup: RateLimiter with 0 tokens, short timeout
        Action: acquire_token(timeout=0.3)
        Expected: Timeout → LLMClassificationError raised
        
        Note: In production, node_classify_tipologia catches this and uses fallback
        """
        # Mock Redis client with no tokens
        redis_mock = MagicMock()
        redis_mock.setnx.return_value = True
        redis_mock.get.side_effect = lambda key: {
            "rate_limiter:openai:last_refill": str(time.time()),
            "rate_limiter:openai:tokens": "0",  # No tokens
            "rate_limiter:openai:concurrent": "0",
        }.get(key, "0")
        redis_mock.decr.return_value = -1  # Decrement fails (no tokens)
        redis_mock.incr.return_value = 0   # Rollback
        
        rate_limiter = RateLimiterService(
            redis_client=redis_mock,
            rate_limit_per_min=5,
        )
        
        # Mock OpenAI (won't be reached due to rate limiter timeout)
        with patch("src.agent.graph.llm_client.ChatOpenAI") as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            llm_client = LLMClient(rate_limiter=rate_limiter)
            
            # Patch OPENAI_RATE_LIMITER_TIMEOUT to short value
            with patch("src.agent.graph.llm_client.OPENAI_RATE_LIMITER_TIMEOUT", 0.3):
                # Act: Try to classify (should timeout)
                with pytest.raises(LLMClassificationError) as exc_info:
                    llm_client.classify_tipologia(
                        volume=1.5,
                        bbox={"min": [0, 0, 0], "max": [1, 1, 1]},
                        layers=["SF-C12-D-001"],
                        vertices_count=1000,
                        iso_code="SF-C12-D-001",
                    )
                
                # Assert: Error message mentions timeout
                assert "Rate limiter timeout" in str(exc_info.value)
                assert "0.3" in str(exc_info.value), "Should mention timeout duration"


# ========================================================================
# Pytest Fixtures
# ========================================================================

@pytest.fixture
def mock_redis_client():
    """
    Fixture: Mock Redis client for testing.
    
    Returns a configured MagicMock with typical Redis responses.
    """
    redis_mock = MagicMock()
    redis_mock.setnx.return_value = True
    redis_mock.get.side_effect = lambda key: {
        "rate_limiter:openai:last_refill": str(time.time()),
        "rate_limiter:openai:tokens": "5",
        "rate_limiter:openai:concurrent": "0",
    }.get(key, "0")
    redis_mock.decr.return_value = 4
    redis_mock.incr.return_value = 1
    redis_mock.pipeline.return_value = redis_mock
    redis_mock.execute.return_value = [True, True, True]
    
    return redis_mock
