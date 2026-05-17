"""
Classification Helper Functions

Utilities for:
1. Fallback regex classification (when LLM fails)
2. Prompt injection prevention (sanitize user inputs)

T-1802-AGENT: LLM Classification Helpers
"""

import re
from typing import Dict, Any

import structlog

from src.agent.constants import (
    FALLBACK_REGEX_PATTERNS,
    FALLBACK_DEFAULT_TIPOLOGIA,
    FALLBACK_DEFAULT_CONFIDENCE,
    FORBIDDEN_PATTERNS,
    PROMPT_INJECTION_REDACTED_TEXT,
)
from src.agent.graph.state import ClassificationMethod

logger = structlog.get_logger(__name__)


def sanitize_user_string(text: str) -> str:
    """
    Sanitize user-provided string to prevent prompt injection attacks.
    
    Replaces forbidden patterns with [REDACTED_SECURITY] placeholder.
    
    Forbidden patterns (case-insensitive):
    - "ignore previous instructions"
    - "you are now"
    - "disregard all"
    - "forget everything"
    - "new instructions:"
    - "system prompt"
    - "admin mode"
    - "developer mode"
    
    Args:
        text: User string (from rhino_metadata, iso_code, etc.)
        
    Returns:
        Sanitized string with injections removed
        
    Example:
        >>> sanitize_user_string("SF-C12-D-001 ignore previous instructions")
        "SF-C12-D-001 [REDACTED_SECURITY]"
    """
    if not text:
        return text
    
    sanitized = text
    injection_detected = False
    
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, sanitized, re.IGNORECASE):
            injection_detected = True
            sanitized = re.sub(
                pattern,
                PROMPT_INJECTION_REDACTED_TEXT,
                sanitized,
                flags=re.IGNORECASE,
            )
    
    if injection_detected:
        logger.warning(
            "prompt_injection_detected",
            original=text[:100],  # Truncate for logging
            sanitized=sanitized[:100],
        )
    
    return sanitized


def fallback_classify_by_regex(iso_code: str) -> Dict[str, Any]:
    """
    Classify architectural piece using regex patterns (fallback when LLM fails).
    
    Pattern matching:
    - SF-C12-D-XXX → dovela
    - SF-C12-CA-XXX → capitel
    - SF-C12-CO-XXX → columna
    - SF-C12-CL-XXX → clave
    - SF-C12-IM-XXX → imposta
    - Default → other
    
    Args:
        iso_code: ISO-19650 block identifier (e.g., "SF-C12-D-001")
        
    Returns:
        Classification dict:
        {
            "tipologia": str,
            "confidence": 0.3,  # Low confidence (regex-based)
            "reasoning": "Fallback regex classification based on ISO code pattern",
            "classified_at": ISO timestamp,
            "classification_method": ClassificationMethod.FALLBACK_REGEX
        }
        
    Note:
        Never fails - defaults to "other" if no pattern matches
    """
    import datetime
    
    # Sanitize iso_code (prevent injection in logging)
    safe_iso_code = sanitize_user_string(iso_code)
    
    # Try each regex pattern
    for pattern, tipologia in FALLBACK_REGEX_PATTERNS.items():
        if re.match(pattern, safe_iso_code):
            logger.info(
                "fallback_regex_match",
                iso_code=safe_iso_code,
                pattern=pattern,
                tipologia=tipologia,
            )
            
            return {
                "tipologia": tipologia,
                "material": "Unknown",  # Cannot determine from ISO code alone
                "confidence": FALLBACK_DEFAULT_CONFIDENCE,
                "reasoning": f"Fallback regex classification: {pattern} → {tipologia}",
                "classified_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
    
    # No pattern matched → default to "other"
    logger.info(
        "fallback_regex_default",
        iso_code=safe_iso_code,
        default=FALLBACK_DEFAULT_TIPOLOGIA,
    )
    
    return {
        "tipologia": FALLBACK_DEFAULT_TIPOLOGIA,
        "material": "Unknown",
        "confidence": FALLBACK_DEFAULT_CONFIDENCE,
        "reasoning": "No regex pattern matched, defaulting to 'other'",
        "classified_at": datetime.datetime.utcnow().isoformat() + "Z",
    }



def validate_llm_confidence(confidence: float, threshold: float = 0.7) -> bool:
    """
    Validate if LLM confidence meets threshold.
    
    Args:
        confidence: LLM confidence score (0.0-1.0)
        threshold: Minimum acceptable confidence (default: 0.7)
        
    Returns:
        True if confidence >= threshold, False otherwise
        
    Example:
        >>> validate_llm_confidence(0.85, threshold=0.7)
        True
        
        >>> validate_llm_confidence(0.52, threshold=0.7)
        False  # Trigger fallback regex
    """
    meets_threshold = confidence >= threshold
    
    if not meets_threshold:
        logger.info(
            "low_confidence_fallback_triggered",
            confidence=confidence,
            threshold=threshold,
        )
    
    return meets_threshold


def merge_llm_with_metadata(
    llm_result: Dict[str, Any],
    geometry_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge LLM classification result with geometry metadata.
    
    Enriches LLM classification with:
    - Material from geometry_metadata (if available)
    - Volume, bbox, vertices_count (for audit trail)
    
    Args:
        llm_result: LLM classification dict {"tipologia", "confidence", "reasoning"}
        geometry_metadata: Geometry dict from ExtractGeometry node
        
    Returns:
        Merged semantic_data dict with both LLM and geometry info
        
    Example:
        llm = {"tipologia": "dovela", "confidence": 0.85, ...}
        geo = {"volume": 2.5, "material": "Montjuïc", ...}
        
        result = merge_llm_with_metadata(llm, geo)
        # {"tipologia": "dovela", "material": "Montjuïc", "confidence": 0.85, ...}
    """
    # Extract material from geometry_metadata (UserStrings)
    material = geometry_metadata.get("material", "Unknown")
    
    # Merge LLM result with material
    merged = {
        **llm_result,
        "material": material,
    }
    
    return merged
