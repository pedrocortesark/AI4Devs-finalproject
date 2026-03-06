"""
Storage utilities for Supabase Storage path generation.

This module implements standardized naming conventions for files uploaded
to Supabase Storage buckets, ensuring uniqueness, traceability, and S3 best practices.
"""

from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from constants import STORAGE_PATH_PREFIX_MODELS, STORAGE_PATH_SUBDIR_LOW_POLY


def generate_glb_storage_path(
    block_id: UUID,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Generate standardized storage path for low-poly GLB files.
    
    Format: models/low-poly/{uuid}_{ISO8601}.glb
    Example: models/low-poly/550e8400-e29b-41d4-a716-446655440000_2026-03-06T15:30:45Z.glb
    
    This function implements the storage path convention defined in US-015 Epic
    (Element Model Refactoring). It ensures:
    - Unique paths per upload (timestamp prevents collision)
    - Chronological sorting (ISO8601 timestamp format)
    - Database traceability (UUID maps to blocks.id)
    - S3 compatibility (no leading slash, hierarchical structure)
    
    Args:
        block_id: Block UUID from database (blocks.id column)
        timestamp: Upload timestamp in UTC (defaults to current UTC time if None)
    
    Returns:
        Storage path string relative to bucket root (no leading slash)
        
    Raises:
        ValueError: If block_id is not a valid UUID
        ValueError: If timestamp is not timezone-aware
        
    Examples:
        >>> block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        >>> timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)
        >>> generate_glb_storage_path(block_id, timestamp)
        'models/low-poly/550e8400-e29b-41d4-a716-446655440000_2026-03-06T15:30:45Z.glb'
        
    Notes:
        - Timestamp MUST be timezone-aware (UTC preferred, auto-converted if not)
        - Returned path is relative (no leading '/') for Supabase Storage compatibility
        - Function is idempotent: same inputs always produce same output
        - Microseconds are truncated for consistent path format
    """
    # Validate block_id is UUID instance
    if not isinstance(block_id, UUID):
        raise ValueError("block_id must be a UUID instance")
    
    # Default timestamp to current UTC if None (truncate microseconds for consistency)
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    
    # Validate timestamp is timezone-aware
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    
    # Convert to UTC and truncate microseconds
    timestamp_utc = timestamp.astimezone(timezone.utc).replace(microsecond=0)
    
    # Format as ISO8601 with Z suffix
    iso_timestamp = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Construct path using centralized constants
    uuid_str = str(block_id)
    path = f"{STORAGE_PATH_PREFIX_MODELS}/{STORAGE_PATH_SUBDIR_LOW_POLY}/{uuid_str}_{iso_timestamp}.glb"
    
    return path
