"""
Preview endpoint for .3dm file analysis before upload.

Parses the file in memory (writes to /tmp, always cleaned up) and returns
per-InstanceDefinition metadata without writing to DB or Storage.
"""

import uuid
import os
import re
import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from schemas import FilePreviewResponse, BlockPreview
from infra.supabase_client import get_supabase_client
from constants import TABLE_BLOCKS, MAX_FILE_SIZE_BYTES, ISO_19650_LAYER_NAME_PATTERN

try:
    import rhino3dm
except ImportError:
    rhino3dm = None

logger = structlog.get_logger()
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_ISO_PATTERN = re.compile(ISO_19650_LAYER_NAME_PATTERN)


def _validate_iso(name: str) -> tuple[bool, list[str]]:
    """Check name against ISO-19650 pattern; return (is_valid, issues)."""
    if not _ISO_PATTERN.match(name):
        return False, [
            f"'{name}' no cumple el patrón ISO-19650: [PREFIX]-[ZONA]-[TIPO]-[ID] "
            f"(ej. SF-NAV-CO-001)"
        ]
    return True, []


def _extract_refs_and_strings(
    file3dm, idef_id: str
) -> tuple[int, dict[str, str]]:
    """
    Count InstanceReferences that point to `idef_id` and extract UserStrings
    from the first one found.

    Returns:
        (count_refs, user_strings_dict)
    """
    count = 0
    first_strings: dict[str, str] = {}

    if not hasattr(file3dm, "Objects") or file3dm.Objects is None:
        return 0, {}

    for obj in file3dm.Objects:
        try:
            obj_type = getattr(obj.Geometry, "ObjectType", None)
            if obj_type != rhino3dm.ObjectType.InstanceReference:
                continue

            iref_geom = obj.Geometry
            if not hasattr(iref_geom, "ParentIdefId"):
                continue
            if str(iref_geom.ParentIdefId).lower() != idef_id.lower():
                continue

            count += 1

            # Extract UserStrings from first matching reference only
            if not first_strings and hasattr(obj, "Attributes") and hasattr(
                obj.Attributes, "GetUserStrings"
            ):
                raw = obj.Attributes.GetUserStrings()
                if raw is not None and isinstance(raw, (tuple, list)):
                    for key, value in raw:
                        if key not in first_strings:
                            first_strings[key] = value
        except Exception:
            continue

    return count, first_strings


def _check_exists(supabase, iso_code: str) -> bool:
    """Return True if iso_code already exists in the blocks table."""
    try:
        result = (
            supabase.table(TABLE_BLOCKS)
            .select("id")
            .eq("iso_code", iso_code)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0
    except Exception:
        # On DB error, assume not exists (preview should never block an upload)
        return False


@router.post("/preview", response_model=FilePreviewResponse)
@limiter.limit("5/minute")
async def preview_file(
    request: Request, file: UploadFile = File(...)
) -> FilePreviewResponse:
    """
    Analyse a .3dm file and return per-InstanceDefinition preview data.

    Does NOT write to the database or Storage. The file is written to /tmp
    and always cleaned up with try/finally.

    Rate limit: 5 requests/minute per IP.
    """
    if rhino3dm is None:
        raise HTTPException(
            status_code=500, detail="rhino3dm library not available on this server"
        )

    # Enforce file size limit before reading into memory
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
        )

    filename = file.filename or "upload.3dm"
    tmp_path = f"/tmp/{uuid.uuid4()}.3dm"

    try:
        with open(tmp_path, "wb") as f:
            f.write(content)

        file3dm = rhino3dm.File3dm.Read(tmp_path)
        if file3dm is None:
            raise HTTPException(
                status_code=422,
                detail="Cannot parse .3dm file — file may be corrupt or unsupported version",
            )

        supabase = get_supabase_client()
        blocks: list[BlockPreview] = []

        for idef in file3dm.InstanceDefinitions:
            idef_id_str = str(idef.Id).lower()
            count_refs, user_strings = _extract_refs_and_strings(file3dm, idef_id_str)

            codi: str | None = user_strings.get("Codi") or None
            material: str | None = user_strings.get("Material") or None
            iso_valid, iso_issues = _validate_iso(idef.Name)
            already_exists = _check_exists(supabase, idef.Name)

            blocks.append(
                BlockPreview(
                    name=idef.Name,
                    is_instance_object=count_refs > 0,
                    has_metadata=bool(codi and material),
                    codi=codi,
                    material=material,
                    iso_valid=iso_valid,
                    iso_issues=iso_issues,
                    user_strings=user_strings,
                    already_exists=already_exists,
                )
            )

        # Valid = has a Codi (can be registered) AND not already in DB
        # ISO compliance and other metadata are informational only
        valid_blocks = sum(
            1 for b in blocks if b.codi and not b.already_exists
        )
        duplicate_blocks = sum(1 for b in blocks if b.already_exists)
        invalid_blocks = len(blocks) - valid_blocks - duplicate_blocks

        logger.info(
            "preview_file.completed",
            filename=filename,
            total=len(blocks),
            valid=valid_blocks,
            duplicates=duplicate_blocks,
            invalid=invalid_blocks,
        )

        return FilePreviewResponse(
            filename=filename,
            total_blocks=len(blocks),
            valid_blocks=valid_blocks,
            invalid_blocks=invalid_blocks,
            duplicate_blocks=duplicate_blocks,
            blocks=blocks,
        )

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
