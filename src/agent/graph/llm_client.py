"""
LLM Client for GPT-4 Turbo Classification

Configured OpenAI client with:
- JSON Mode forced response
- Retry logic (Tenacity exponential backoff)
- Timeout handling
- Structured output parsing
- Rate limiting (Token bucket algorithm, T-1810)
- Concurrent request limiting (T-1810)

T-1802-AGENT: LLM Classification Node
T-1810-INFRA: OpenAI Rate Limiting (Client-Side)
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

import structlog
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from openai import OpenAIError, RateLimitError, APITimeoutError

from src.agent.constants import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT_SECONDS,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_WAIT_EXPONENTIAL_MULTIPLIER,
    LLM_RETRY_WAIT_EXPONENTIAL_MAX,
    CLASSIFICATION_PROMPTS,
    CLASSIFICATION_PROMPT_VERSION,
    OPENAI_RATE_LIMIT_PER_MIN,
    OPENAI_MAX_CONCURRENT,
    OPENAI_RATE_LIMIT_BUCKET_SIZE,
    OPENAI_RATE_LIMITER_TIMEOUT,
)

logger = structlog.get_logger(__name__)


class LLMClassificationError(Exception):
    """Base exception for LLM classification failures"""
    pass


class LLMTimeoutError(LLMClassificationError):
    """Raised when LLM request times out"""
    pass


class LLMInvalidResponseError(LLMClassificationError):
    """Raised when LLM returns invalid/unparseable JSON"""
    pass


class LLMClient:
    """
    OpenAI GPT-4 Turbo client for architectural piece classification.
    
    Features:
    - JSON Mode enforced (response_format="json_object")
    - Automatic retry with exponential backoff (3 attempts: 2s, 4s, 8s)
    - Timeout protection (10s hard limit)
    - Structured schema validation
    - Rate limiting (token bucket, 5 req/min default, T-1810)
    - Concurrent request limiting (max 3 simultaneous, T-1810)
    
    Usage:
        client = LLMClient()
        result = client.classify_tipologia(
            volume=2.5,
            bbox={"min": [0,0,0], "max": [1,1,2]},
            layers=["SF-C12-D-001"],
            vertices_count=5000,
            iso_code="SF-C12-D-001"
        )
        # Returns: {"tipologia": "dovela", "confidence": 0.85, "reasoning": "..."}
    """
    
    def __init__(self, rate_limiter=None):
        """
        Initialize OpenAI client with configuration from constants.
        
        Args:
            rate_limiter: Optional RateLimiterService instance (defaults to singleton)
                         Pass None to disable rate limiting (testing only)
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "OPENAI_API_KEY not found in environment, LLM classification will fail"
            )
        
        # Initialize ChatOpenAI with JSON Mode
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT_SECONDS,
            model_kwargs={"response_format": {"type": "json_object"}},  # Force JSON response
            openai_api_key=api_key,
        )
        
        # JSON output parser
        self.parser = JsonOutputParser()
        
        # T-1810: Initialize rate limiter.
        # The RateLimiterService lives in src/backend; it is reachable from the
        # backend test container ("services.*") and from local docker-compose
        # ("src.backend.*", since ./src is mounted), but NOT from the prod agent
        # image (built from the src/agent context only). Rate limiting is
        # best-effort by design (it already degrades when Redis is down), so a
        # missing module must NOT crash classification — we degrade to
        # rate_limiter=None, which classify_tipologia already treats as "no
        # throttling". This keeps real LLM classification working in prod.
        if rate_limiter is None:
            self.rate_limiter = None
            try:
                try:
                    from services.rate_limiter_service import RateLimiterService
                    from infra.redis_client import get_redis_client
                except ImportError:
                    from src.backend.services.rate_limiter_service import RateLimiterService
                    from src.backend.infra.redis_client import get_redis_client

                redis_client = get_redis_client()
                self.rate_limiter = RateLimiterService(
                    redis_client=redis_client,
                    rate_limit_per_min=OPENAI_RATE_LIMIT_PER_MIN,
                    max_concurrent=OPENAI_MAX_CONCURRENT,
                    bucket_size=OPENAI_RATE_LIMIT_BUCKET_SIZE,
                )
            except ImportError as e:
                logger.warning(
                    "rate_limiter_unavailable_degrading",
                    error=str(e),
                    message="RateLimiterService not importable (prod agent image); "
                            "continuing without client-side rate limiting",
                )
        else:
            self.rate_limiter = rate_limiter
        
        logger.info(
            "llm_client_initialized",
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            timeout=LLM_TIMEOUT_SECONDS,
            rate_limit_per_min=OPENAI_RATE_LIMIT_PER_MIN,
            max_concurrent=OPENAI_MAX_CONCURRENT,
        )
    
    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=LLM_RETRY_WAIT_EXPONENTIAL_MULTIPLIER,
            max=LLM_RETRY_WAIT_EXPONENTIAL_MAX,
        ),
        retry=retry_if_exception_type((OpenAIError, APITimeoutError, RateLimitError)),
        reraise=True,
    )
    def _call_llm(self, prompt: str) -> str:
        """
        Internal method to call LLM with retry logic.
        
        Retries on:
        - OpenAIError (API errors)
        - APITimeoutError (timeout errors)
        - RateLimitError (HTTP 429)
        
        Args:
            prompt: Formatted prompt string
            
        Returns:
            Raw LLM response text (JSON string)
            
        Raises:
            RetryError: If all retry attempts fail
            LLMTimeoutError: If timeout exceeded
        """
        try:
            messages = [
                SystemMessage(content="You are an expert architectural classifier."),
                HumanMessage(content=prompt),
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except APITimeoutError as e:
            logger.error("llm_timeout", error=str(e), timeout=LLM_TIMEOUT_SECONDS)
            raise LLMTimeoutError(f"LLM request timeout after {LLM_TIMEOUT_SECONDS}s") from e
        except RateLimitError as e:
            logger.warning("llm_rate_limit", error=str(e))
            raise  # Let Tenacity retry
        except OpenAIError as e:
            logger.error("llm_api_error", error=str(e), error_type=type(e).__name__)
            raise  # Let Tenacity retry
    
    def classify_tipologia(
        self,
        volume: float,
        bbox: Dict[str, Any],
        layers: list,
        vertices_count: int,
        iso_code: str,
    ) -> Dict[str, Any]:
        """
        Classify architectural piece using GPT-4 Turbo.
        
        T-1810: Implements rate limiting and concurrent request limiting to prevent
        HTTP 429 errors during batch uploads.
        
        Rate Limiting Flow:
        1. Acquire token from bucket (blocks until available or timeout)
        2. Acquire concurrent slot (max 3 simultaneous requests)
        3. Call OpenAI API with retry logic
        4. Release concurrent slot (always, even on error)
        
        Args:
            volume: Volume in cubic meters
            bbox: Bounding box dict {"min": [x,y,z], "max": [x,y,z]}
            layers: List of Rhino layer names
            vertices_count: Number of vertices in mesh
            iso_code: ISO-19650 block identifier
            
        Returns:
            Classification dict with schema:
            {
                "tipologia": str (dovela|capitel|columna|clave|imposta|other),
                "confidence": float (0.0-1.0),
                "reasoning": str (max 100 chars)
            }
            
        Raises:
            LLMClassificationError: If classification fails after retries
            LLMInvalidResponseError: If response JSON is invalid
        """
        # Format prompt with metadata
        prompt_template = CLASSIFICATION_PROMPTS[CLASSIFICATION_PROMPT_VERSION]
        prompt = prompt_template.format(
            volume=volume,
            bbox=bbox,
            layers=layers,
            vertices_count=vertices_count,
            iso_code=iso_code,
        )
        
        logger.info(
            "llm_classify_request",
            iso_code=iso_code,
            volume=volume,
            vertices_count=vertices_count,
        )
        
        # T-1810: Acquire rate limiter token (blocks until available or timeout)
        if self.rate_limiter and self.rate_limiter.enabled:
            token_acquired = self.rate_limiter.acquire_token(
                timeout=OPENAI_RATE_LIMITER_TIMEOUT
            )
            
            if not token_acquired:
                logger.error(
                    "rate_limiter_timeout",
                    iso_code=iso_code,
                    timeout_sec=OPENAI_RATE_LIMITER_TIMEOUT,
                    message="Rate limiter timeout, should trigger fallback classification",
                )
                raise LLMClassificationError(
                    f"Rate limiter timeout after {OPENAI_RATE_LIMITER_TIMEOUT}s. "
                    "Consider using fallback classification or increasing timeout."
                )
        
        # T-1810: Acquire concurrent slot (non-blocking check)
        concurrent_slot_acquired = False
        if self.rate_limiter and self.rate_limiter.enabled:
            concurrent_slot_acquired = self.rate_limiter.acquire_concurrent_slot()
            
            if not concurrent_slot_acquired:
                logger.warning(
                    "concurrent_limit_reached",
                    iso_code=iso_code,
                    max_concurrent=OPENAI_MAX_CONCURRENT,
                    message="Max concurrent LLM requests reached, should trigger fallback",
                )
                raise LLMClassificationError(
                    f"Max concurrent LLM requests ({OPENAI_MAX_CONCURRENT}) reached. "
                    "Consider using fallback classification."
                )
        
        try:
            # Call LLM with retry logic (Tenacity handles retries)
            raw_response = self._call_llm(prompt)
            
            # Parse JSON response
            try:
                result = json.loads(raw_response)
            except json.JSONDecodeError as e:
                logger.error(
                    "llm_invalid_json",
                    iso_code=iso_code,
                    raw_response=raw_response[:200],  # Truncate for logging
                    error=str(e),
                )
                raise LLMInvalidResponseError(
                    f"LLM returned invalid JSON: {str(e)}"
                ) from e
            
            # Validate schema (required fields)
            required_fields = ["tipologia", "confidence", "reasoning"]
            missing_fields = [f for f in required_fields if f not in result]
            if missing_fields:
                logger.error(
                    "llm_missing_fields",
                    iso_code=iso_code,
                    missing=missing_fields,
                    result=result,
                )
                raise LLMInvalidResponseError(
                    f"LLM response missing fields: {missing_fields}"
                )
            
            # Validate confidence is float in range [0.0, 1.0]
            try:
                confidence = float(result["confidence"])
                if not (0.0 <= confidence <= 1.0):
                    raise ValueError("Confidence must be between 0.0 and 1.0")
                result["confidence"] = confidence
            except (ValueError, TypeError) as e:
                logger.error(
                    "llm_invalid_confidence",
                    iso_code=iso_code,
                    confidence=result.get("confidence"),
                    error=str(e),
                )
                raise LLMInvalidResponseError(
                    f"Invalid confidence value: {result.get('confidence')}"
                ) from e
            
            # Add metadata
            result["classified_at"] = datetime.utcnow().isoformat() + "Z"
            
            logger.info(
                "llm_classify_success",
                iso_code=iso_code,
                tipologia=result["tipologia"],
                confidence=result["confidence"],
            )
            
            return result
            
        except RetryError as e:
            # All retry attempts exhausted
            logger.error(
                "llm_classify_failed_after_retries",
                iso_code=iso_code,
                attempts=LLM_RETRY_ATTEMPTS,
                error=str(e.last_attempt.exception()),
            )
            raise LLMClassificationError(
                f"LLM classification failed after {LLM_RETRY_ATTEMPTS} attempts"
            ) from e
        except (RateLimitError, APITimeoutError, OpenAIError) as e:
            # Tenacity reraise=True re-raises original exception after exhausting retries
            logger.error(
                "llm_classify_failed_openai_error",
                iso_code=iso_code,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise LLMClassificationError(
                f"LLM classification failed: {type(e).__name__}"
            ) from e
        finally:
            # T-1810: Always release concurrent slot (even on error)
            if concurrent_slot_acquired and self.rate_limiter:
                self.rate_limiter.release_concurrent_slot()
                logger.debug(
                    "concurrent_slot_released",
                    iso_code=iso_code,
                )


# Singleton instance (reuse across calls to avoid reinitializing OpenAI client)
_llm_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get singleton LLM client instance.
    
    Returns:
        LLMClient instance (creates on first call, reuses thereafter)
    """
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
