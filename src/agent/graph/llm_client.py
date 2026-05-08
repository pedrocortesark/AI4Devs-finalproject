"""
LLM Client for GPT-4 Turbo Classification

Configured OpenAI client with:
- JSON Mode forced response
- Retry logic (Tenacity exponential backoff)
- Timeout handling
- Structured output parsing

T-1802-AGENT: LLM Classification Node
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
    
    def __init__(self):
        """Initialize OpenAI client with configuration from constants."""
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
        
        logger.info(
            "llm_client_initialized",
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            timeout=LLM_TIMEOUT_SECONDS,
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
        
        try:
            # Call LLM with retry logic
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
