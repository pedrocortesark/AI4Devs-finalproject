"""
Admin endpoints for development/maintenance operations.

All endpoints are guarded against production use.
"""

import structlog
from fastapi import APIRouter, HTTPException

from infra.supabase_client import get_supabase_client
from config import settings
from constants import TABLE_BLOCKS, STORAGE_BUCKET_RAW_UPLOADS, STORAGE_BUCKET_PROCESSED

logger = structlog.get_logger()
router = APIRouter()


def _list_all_keys(supabase, bucket: str) -> list[str]:
    """
    Recursively list all object keys in a Supabase Storage bucket.

    supabase.storage.from_(bucket).list(path=prefix) returns only top-level
    entries. Entries with id=None are pseudo-directories and must be recursed.
    """
    all_keys: list[str] = []

    def _recurse(prefix: str = "") -> None:
        try:
            items = supabase.storage.from_(bucket).list(path=prefix) or []
        except Exception as e:
            logger.warning("admin.list_keys.error", bucket=bucket, prefix=prefix, error=str(e))
            return

        for item in items:
            name = item.get("name", "")
            if not name:
                continue
            full_key = f"{prefix}/{name}".lstrip("/") if prefix else name
            if item.get("id") is None:
                # Pseudo-directory — recurse
                _recurse(full_key)
            else:
                all_keys.append(full_key)

    _recurse()
    return all_keys


@router.delete("/reset-blocks")
async def reset_blocks() -> dict:
    """
    Delete all blocks and clear Storage buckets.

    Only available in non-production environments. Returns 403 in production
    without executing any destructive operation.

    Returns:
        {"deleted_blocks": N, "cleared_storage": bool}
    """
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="reset-blocks is not available in the production environment",
        )

    supabase = get_supabase_client()

    # --- 1. Count blocks before deletion ---
    try:
        count_result = (
            supabase.table(TABLE_BLOCKS)
            .select("id", count="exact")
            .execute()
        )
        deleted_blocks: int = count_result.count or 0
    except Exception as e:
        logger.error("admin.reset_blocks.count_failed", error=str(e))
        deleted_blocks = 0

    # --- 2. Delete all blocks ---
    # supabase-py v2 requires a filter on DELETE — use gte on created_at as "delete all"
    try:
        supabase.table(TABLE_BLOCKS).delete().gte("created_at", "1970-01-01").execute()
        logger.info("admin.reset_blocks.deleted", count=deleted_blocks)
    except Exception as e:
        logger.error("admin.reset_blocks.delete_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete blocks: {str(e)}")

    # --- 3. Clear storage buckets ---
    cleared_storage = True
    for bucket in [STORAGE_BUCKET_RAW_UPLOADS, STORAGE_BUCKET_PROCESSED]:
        try:
            keys = _list_all_keys(supabase, bucket)
            if keys:
                # Remove in batches of 100 (Supabase limit)
                for i in range(0, len(keys), 100):
                    batch = keys[i : i + 100]
                    supabase.storage.from_(bucket).remove(batch)
            logger.info("admin.reset_blocks.storage_cleared", bucket=bucket, files=len(keys))
        except Exception as e:
            logger.error("admin.reset_blocks.storage_failed", bucket=bucket, error=str(e))
            cleared_storage = False

    return {"deleted_blocks": deleted_blocks, "cleared_storage": cleared_storage}
