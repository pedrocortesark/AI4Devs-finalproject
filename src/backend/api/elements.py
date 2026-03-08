"""
FastAPI router for elements endpoints (T-1504-BACK).

Breaking Changes from /api/parts:
- Removed workshop_id filter (no workshops in MVP)
- Removed tipologia filter
- Added material_type filter (validated against 62 materials)
- Removed RLS enforcement (simplified access control)

Endpoints:
- GET /api/elements - List elements with optional filters
- GET /api/elements/{id} - Get element detail
- GET /api/elements/{id}/navigation - Get prev/next element IDs
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from schemas import ElementsListResponse, ElementDetail, ElementNavigationResponse, ElementStatus
from infra.supabase_client import get_supabase_client
from services.elements_service import ElementsService
from services.element_detail_service import ElementDetailService
from services.navigation_service import NavigationService
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


@router.get(
    "/{element_id}/navigation",
    response_model=ElementNavigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get adjacent elements for navigation",
    description=(
        "Returns prev/next element IDs for 3D viewer modal navigation. "
        "Applies optional filters (status, material_type) and orders by created_at DESC. "
        "Uses Redis caching with 300s TTL for performance."
    ),
    responses={
        200: {
            "description": "Adjacent elements found",
            "content": {
                "application/json": {
                    "example": {
                        "prev_id": "123e4567-e89b-12d3-a456-426614174000",
                        "next_id": "123e4567-e89b-12d3-a456-426614174002",
                        "current_index": 42,
                        "total_count": 250
                    }
                }
            }
        },
        400: {"description": "Invalid UUID format"},
        404: {"description": "Element not found in filtered set"},
        500: {"description": "Internal database error"}
    }
)
async def get_element_navigation(
    element_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g., 'validated')"),
    material_type: Optional[str] = Query(None, description="Filter by material type (e.g., 'Montjuïc')")
):
    """
    Fetch prev/next element IDs for navigation in 3D viewer modal.

    Query Parameters:
    - status (optional): Filter by status
    - material_type (optional): Filter by material type

    Returns:
    - prev_id: UUID of previous element (null if first)
    - next_id: UUID of next element (null if last)
    - current_index: 1-based position in filtered set
    - total_count: Total elements in filtered set
    """
    # Validate UUID format
    _validate_uuid_format(element_id)

    # Initialize service and fetch adjacent elements
    service = NavigationService()

    # Call navigation service with material_type filter
    success, data, error = service.get_adjacent_parts(
        part_id=element_id,
        workshop_id=None,  # Not used in Element API
        status=status_filter,
        material_type=material_type
    )

    # Handle errors
    if not success:
        if "Invalid UUID" in error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )
        elif "not found" in error.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error
            )

    # Transform PartNavigationResponse to ElementNavigationResponse
    # (schemas are identical, just renamed)
    return ElementNavigationResponse(
        prev_id=data.prev_id,
        next_id=data.next_id,
        current_index=data.current_index,
        total_count=data.total_count
    )
