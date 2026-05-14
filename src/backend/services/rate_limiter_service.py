"""
OpenAI Rate Limiter Service

Token bucket algorithm with Redis backend for rate limiting OpenAI API requests.
Prevents HTTP 429 errors during batch uploads by enforcing configurable rate limits
and concurrent request limits.

Features:
- Token bucket refill algorithm (5 tokens/min default)
- Max concurrent requests limit (3 simultaneous default)
- Graceful degradation if Redis unavailable
- Thread-safe with Redis atomic operations

T-1810-INFRA: OpenAI Rate Limiting (Client-Side)
Author: AI Assistant
Date: 2026-05-13
"""

import time
from typing import Optional
import structlog
from redis import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)


class RateLimiterService:
    """
    Token bucket rate limiter with Redis backend.
    
    Implements rate limiting for OpenAI API requests to prevent HTTP 429 errors
    during batch processing. Uses Redis for distributed state management.
    
    Algorithm:
    - Token bucket with configurable refill rate (default: 5 tokens/min)
    - Tokens refill at fixed intervals (12 seconds per token for 5/min)
    - acquire_token() blocks until token available or timeout
    - Concurrent request limit tracked with Redis counter
    
    Examples:
        >>> limiter = RateLimiterService(redis_client, rate_limit_per_min=5)
        >>> if limiter.acquire_token(timeout=30.0):
        ...     try:
        ...         response = openai_api.call()
        ...     finally:
        ...         limiter.release_token()
        
    Redis Keys:
    - rate_limiter:openai:tokens -> int (available tokens in bucket)
    - rate_limiter:openai:last_refill -> float (timestamp of last refill)
    - rate_limiter:openai:concurrent -> int (current concurrent requests)
    """
    
    # Redis key prefixes
    BUCKET_KEY = "rate_limiter:openai:tokens"
    LAST_REFILL_KEY = "rate_limiter:openai:last_refill"
    CONCURRENT_KEY = "rate_limiter:openai:concurrent"
    
    def __init__(
        self, 
        redis_client: Optional[Redis],
        rate_limit_per_min: int = 5,
        max_concurrent: int = 3,
        bucket_size: int = None,
    ):
        """
        Initialize rate limiter service.
        
        Args:
            redis_client: Redis client instance (can be None for graceful degradation)
            rate_limit_per_min: Maximum tokens consumed per minute (default: 5)
            max_concurrent: Maximum simultaneous requests allowed (default: 3)
            bucket_size: Maximum tokens in bucket (default: same as rate_limit)
        """
        self.redis = redis_client
        self.rate_limit = rate_limit_per_min
        self.max_concurrent = max_concurrent
        self.bucket_size = bucket_size or rate_limit_per_min
        self.refill_interval = 60.0 / rate_limit_per_min  # seconds per token
        
        # Graceful degradation flag
        self.enabled = redis_client is not None
        
        if not self.enabled:
            logger.warning(
                "rate_limiter_disabled",
                reason="redis_unavailable",
                impact="no_rate_limiting"
            )
        else:
            # Initialize bucket on first use
            self._initialize_bucket()
            logger.info(
                "rate_limiter_initialized",
                rate_limit_per_min=rate_limit_per_min,
                max_concurrent=max_concurrent,
                bucket_size=self.bucket_size,
                refill_interval_sec=self.refill_interval,
            )
    
    def _initialize_bucket(self):
        """
        Initialize token bucket in Redis if not exists.
        
        Sets initial tokens to bucket_size and last_refill to current timestamp.
        Uses SETNX to avoid overwriting existing bucket state.
        """
        if not self.enabled:
            return
        
        try:
            # Set initial tokens if key doesn't exist (SETNX = SET if Not eXists)
            self.redis.setnx(self.BUCKET_KEY, self.bucket_size)
            
            # Set initial refill timestamp
            self.redis.setnx(self.LAST_REFILL_KEY, time.time())
            
            logger.debug(
                "bucket_initialized",
                bucket_key=self.BUCKET_KEY,
                initial_tokens=self.bucket_size,
            )
        except RedisError as e:
            logger.error("bucket_init_failed", error=str(e))
            self.enabled = False
    
    def _refill_tokens(self) -> int:
        """
        Refill tokens based on elapsed time since last refill.
        
        Calculates how many tokens should be added based on time elapsed
        and refill_interval. Updates both token count and last_refill timestamp.
        
        Returns:
            int: Current token count after refill
        """
        if not self.enabled:
            return self.bucket_size  # Unlimited if disabled
        
        try:
            current_time = time.time()
            last_refill = float(self.redis.get(self.LAST_REFILL_KEY) or current_time)
            elapsed = current_time - last_refill
            
            # Calculate tokens to add (integer division)
            tokens_to_add = int(elapsed / self.refill_interval)
            
            if tokens_to_add > 0:
                # Get current tokens
                current_tokens = int(self.redis.get(self.BUCKET_KEY) or 0)
                
                # Add tokens (cap at bucket_size)
                new_tokens = min(current_tokens + tokens_to_add, self.bucket_size)
                
                # Update Redis atomically (pipeline for consistency)
                pipe = self.redis.pipeline()
                pipe.set(self.BUCKET_KEY, new_tokens)
                pipe.set(self.LAST_REFILL_KEY, last_refill + (tokens_to_add * self.refill_interval))
                pipe.execute()
                
                logger.debug(
                    "tokens_refilled",
                    tokens_added=tokens_to_add,
                    new_tokens=new_tokens,
                    elapsed_sec=elapsed,
                )
                
                return new_tokens
            else:
                # No refill needed
                return int(self.redis.get(self.BUCKET_KEY) or 0)
                
        except RedisError as e:
            logger.error("refill_failed", error=str(e))
            self.enabled = False
            return self.bucket_size  # Graceful degradation
    
    def acquire_token(self, timeout: float = 30.0) -> bool:
        """
        Acquire a token from the bucket (blocking with timeout).
        
        Blocks until a token is available or timeout is reached. Refills tokens
        automatically based on elapsed time. Uses polling with 0.1s intervals.
        
        Args:
            timeout: Maximum seconds to wait for token (default: 30.0)
        
        Returns:
            bool: True if token acquired, False if timeout reached
        
        Examples:
            >>> if limiter.acquire_token(timeout=30.0):
            ...     # Token acquired, proceed with request
            ...     make_openai_request()
            >>> else:
            ...     # Timeout, fallback to non-LLM method
            ...     use_fallback_method()
        """
        if not self.enabled:
            # Graceful degradation: always succeed if Redis unavailable
            logger.debug("token_acquired_degraded", reason="redis_unavailable")
            return True
        
        start_time = time.time()
        poll_interval = 0.1  # 100ms polling
        
        while (time.time() - start_time) < timeout:
            try:
                # Refill tokens based on elapsed time
                available_tokens = self._refill_tokens()
                
                if available_tokens > 0:
                    # Try to decrement token count (atomic operation)
                    new_count = self.redis.decr(self.BUCKET_KEY)
                    
                    if new_count >= 0:
                        # Success: token acquired
                        logger.debug(
                            "token_acquired",
                            remaining_tokens=new_count,
                            wait_time_sec=time.time() - start_time,
                        )
                        return True
                    else:
                        # Race condition: another process took the last token
                        # Increment back and retry
                        self.redis.incr(self.BUCKET_KEY)
                
                # Wait before next poll
                time.sleep(poll_interval)
                
            except RedisError as e:
                logger.error("acquire_token_failed", error=str(e))
                self.enabled = False
                return True  # Graceful degradation
        
        # Timeout reached
        logger.warning(
            "token_acquire_timeout",
            timeout_sec=timeout,
            message="Rate limiter timeout, consider increasing rate_limit or timeout"
        )
        return False
    
    def check_concurrent_limit(self) -> bool:
        """
        Check if concurrent request limit allows new request.
        
        Does NOT increment counter (use acquire_concurrent_slot() for that).
        This is a read-only check.
        
        Returns:
            bool: True if under limit, False if at max concurrent requests
        """
        if not self.enabled:
            return True  # No limit if disabled
        
        try:
            current_concurrent = int(self.redis.get(self.CONCURRENT_KEY) or 0)
            return current_concurrent < self.max_concurrent
        except RedisError as e:
            logger.error("concurrent_check_failed", error=str(e))
            self.enabled = False
            return True  # Graceful degradation
    
    def acquire_concurrent_slot(self) -> bool:
        """
        Acquire a concurrent request slot.
        
        Increments concurrent counter if under max_concurrent limit.
        Must be paired with release_concurrent_slot() in finally block.
        
        Returns:
            bool: True if slot acquired, False if at limit
        
        Examples:
            >>> if limiter.acquire_concurrent_slot():
            ...     try:
            ...         response = openai_api.call()
            ...     finally:
            ...         limiter.release_concurrent_slot()
        """
        if not self.enabled:
            return True  # No limit if disabled
        
        try:
            # Atomic increment and get
            new_count = self.redis.incr(self.CONCURRENT_KEY)
            
            if new_count <= self.max_concurrent:
                logger.debug(
                    "concurrent_slot_acquired",
                    concurrent_count=new_count,
                    max_concurrent=self.max_concurrent,
                )
                return True
            else:
                # Exceeded limit, decrement back
                self.redis.decr(self.CONCURRENT_KEY)
                logger.warning(
                    "concurrent_limit_reached",
                    current=new_count - 1,
                    max=self.max_concurrent,
                )
                return False
                
        except RedisError as e:
            logger.error("acquire_concurrent_failed", error=str(e))
            self.enabled = False
            return True  # Graceful degradation
    
    def release_concurrent_slot(self):
        """
        Release a concurrent request slot.
        
        Decrements the concurrent counter. Should be called in a finally block
        after acquire_concurrent_slot().
        """
        if not self.enabled:
            return
        
        try:
            new_count = self.redis.decr(self.CONCURRENT_KEY)
            
            # Prevent negative counts (safety check)
            if new_count < 0:
                self.redis.set(self.CONCURRENT_KEY, 0)
                logger.warning("concurrent_count_negative", corrected_to=0)
            else:
                logger.debug("concurrent_slot_released", concurrent_count=new_count)
                
        except RedisError as e:
            logger.error("release_concurrent_failed", error=str(e))
            # Don't disable on release failure (non-critical)
    
    def reset(self):
        """
        Reset rate limiter state (for testing/admin purposes).
        
        Resets token bucket to full and concurrent count to 0.
        """
        if not self.enabled:
            logger.warning("reset_skipped", reason="redis_unavailable")
            return
        
        try:
            pipe = self.redis.pipeline()
            pipe.set(self.BUCKET_KEY, self.bucket_size)
            pipe.set(self.LAST_REFILL_KEY, time.time())
            pipe.set(self.CONCURRENT_KEY, 0)
            pipe.execute()
            
            logger.info("rate_limiter_reset", bucket_tokens=self.bucket_size)
        except RedisError as e:
            logger.error("reset_failed", error=str(e))
    
    def get_status(self) -> dict:
        """
        Get current rate limiter status (for monitoring/debugging).
        
        Returns:
            dict: Current state with keys:
                - enabled: bool
                - available_tokens: int
                - concurrent_requests: int
                - max_concurrent: int
                - rate_limit_per_min: int
        """
        if not self.enabled:
            return {
                "enabled": False,
                "available_tokens": None,
                "concurrent_requests": None,
                "max_concurrent": self.max_concurrent,
                "rate_limit_per_min": self.rate_limit,
            }
        
        try:
            # Refill first to get accurate count
            available = self._refill_tokens()
            concurrent = int(self.redis.get(self.CONCURRENT_KEY) or 0)
            
            return {
                "enabled": True,
                "available_tokens": available,
                "concurrent_requests": concurrent,
                "max_concurrent": self.max_concurrent,
                "rate_limit_per_min": self.rate_limit,
            }
        except RedisError as e:
            logger.error("get_status_failed", error=str(e))
            return {
                "enabled": False,
                "available_tokens": None,
                "concurrent_requests": None,
                "max_concurrent": self.max_concurrent,
                "rate_limit_per_min": self.rate_limit,
            }
