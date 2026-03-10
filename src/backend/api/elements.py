"""
FastAPI router for elements endpoints (T-1504-BACK).

Breaking Changes from /api/parts:
- Removed workshop_id filter (no workshops in MVP)
- Removed tipologia filter
- Added material_type filter (validated against 62 materials)
- Removed RLS enforcement (simplified access control)
- Removed navigation endpoint (deprecated)

Endpoints:
- GET /api/elements - List elements with optional filters
- GET /api/elements/{id} - Get element detail
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from schemas import ElementsListResponse, ElementDetail, ElementStatus
from infra.supabase_client import get_supabase_client
from services.elements_service import ElementsService
from services.element_detail_service import ElementDetailService
from constants import (
    ERROR_MSG_INVALID_STATUS,
    ERROR_MSG_INVALID_UUID,
    ERROR_MSG_ELEMENT_NOT_FOUND,
    ERROR_MSG_FETCH_ELEMENTS_FAILED,
)


def _validate_status_enum(status_value: Optional[str]) -> None:
    """
    Validate status parameter against ElementStatus enum values.

    Args:
        status_value: Status value to validate

    Raises:
        HTTPException: 400 if status is invalid
    """
    if status_value is not None:
        valid_statuses = [s.value for s in ElementStatus]
        if status_value not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MSG_INVALID_STATUS.format(valid_values=', '.join(valid_statuses))
            )


def _validate_uuid_format(element_id: str) -> None:
    """
    Validate element_id parameter as valid UUID.

    Args:
        element_id: UUID string to validate

    Raises:
        HTTPException: 400 if UUID format is invalid
    """
    try:
        UUID(element_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MSG_INVALID_UUID
        )


router = APIRouter()


@router.get("", response_model=ElementsListResponse)
async def list_elements(
    status: Optional[str] = Query(None, description="Filter by lifecycle status (validated, in_fabrication, etc.)"),
    material_type: Optional[str] = Query(None, description="Filter by stone material type (Montjuïc, Ulldecona, etc.)")
) -> ElementsListResponse:
    """
    List all render-ready elements with optional filtering.

    Application-level filtering (render-ready):
    - low_poly_url IS NOT NULL
    - bbox IS NOT NULL

    Query Parameters:
        - status: Filter by lifecycle status
        - material_type: Filter by stone material (one of 63 options)

    Returns:
        ElementsListResponse with:
        - elements: Array of Element (render-ready only)
        - filters_applied: Echo of applied filters for transparency
        - meta: Response metadata (total, filtered counts)

    Performance:
        - Query optimized with composite index idx_blocks_canvas_query
        - Target latency: <500ms
        - Target response size: <200KB gzipped

    Errors:
        - 400: Invalid status enum or material_type
        - 500: Database query failure

    Examples:
        >>> # GET /api/elements
        >>> # Response:
        >>> {
        ...   "elements": [
        ...     {
        ...       "id": "550e8400-e29b-41d4-a716-446655440000",
        ...       "iso_code": "SF-BLC-001-002",
        ...       "status": "validated",
        ...       "material_type": "Montjuïc",
        ...       "low_poly_url": "https://cdn.example.com/550e8400.glb",
        ...       "bbox": {"min": [-1, -1, -1], "max": [1, 1, 1]}
        ...     }
        ...   ],
        ...   "filters_applied": {},
        ...   "meta": {"total": 124, "filtered": 124}
        ... }
        >>>
        >>> # GET /api/elements?status=validated&material_type=Montjuïc
        >>> # Response:
        >>> {
        ...   "elements": [...],
        ...   "filters_applied": {"status": "validated", "material_type": "Montjuïc"},
        ...   "meta": {"total": 124, "filtered": 8}
        ... }
    """
    try:
        # Validate input parameters
        _validate_status_enum(status)

        # Get dependencies
        supabase = get_supabase_client()
        service = ElementsService(supabase)

        # Fetch elements (material validation happens in service)
        return service.list_elements(status=status, material_type=material_type)

    except ValueError as e:
        # Material validation error from service
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ERROR_MSG_FETCH_ELEMENTS_FAILED.format(error=str(e))
        )


@router.get("/{element_id}", response_model=ElementDetail)
async def get_element_detail(
    element_id: str
) -> ElementDetail:
    """
    Fetch a single element by ID.

    Args:
        element_id: UUID of the element

    Returns:
        ElementDetail with element details

    Raises:
        HTTPException 400: Invalid UUID format
        HTTPException 404: Element not found
        HTTPException 500: Database error
    """
    # Validate UUID format
    _validate_uuid_format(element_id)

    # Get service
    service = ElementDetailService()

    # Fetch element
    success, data, error = service.get_element_detail(element_id=element_id)

    if not success:
        # Determine appropriate status code
        if "Invalid UUID" in error:
            raise HTTPException(status_code=400, detail=error)
        elif "Database error" in error:
            raise HTTPException(status_code=500, detail=error)
        else:
            # Default to 404 for "not found"
            raise HTTPException(status_code=404, detail=ERROR_MSG_ELEMENT_NOT_FOUND)

    return ElementDetail(**data)

