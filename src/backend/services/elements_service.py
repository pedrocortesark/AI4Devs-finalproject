"""
Business logic for elements listing operations.

Handles querying and transformation of elements data for 3D canvas rendering.
Implements GET /api/elements endpoint business logic (T-1504-BACK).

Breaking Changes from PartsService:
- Removed tipologia and workshop_id filters
- Added material_type filter (validated against 62 materials)
- Application-level filtering: low_poly_url IS NOT NULL AND bbox IS NOT NULL
"""

from typing import Optional, Dict, Any
from supabase import Client

from schemas import Element, ElementsListResponse, BoundingBox, ElementStatus
from constants import (
    TABLE_BLOCKS,
    QUERY_FIELD_IS_ARCHIVED,
    QUERY_FIELD_CREATED_AT,
    QUERY_ORDER_DESC,
    ELEMENTS_LIST_SELECT_FIELDS,
)


class ElementsService:
    """
    Service for elements listing operations.

    Provides business logic for fetching elements with dynamic filtering,
    optimized for 3D canvas rendering in Dashboard (US-005).
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize ElementsService with database client.

        Args:
            supabase_client: Supabase client instance for database operations
        """
        self.supabase = supabase_client

    def _apply_cdn_transformation(self, url: Optional[str]) -> Optional[str]:
        """
        Transform Supabase S3 URL to CDN URL when USE_CDN is enabled.

        This method implements the URL transformation strategy for GLB file delivery
        optimization (T-1001-INFRA). It only transforms URLs that match our S3 bucket
        pattern to avoid double-transformation of already-CDN URLs.

        Detection Logic:
        - 'processed-geometry': Our S3 bucket name for optimized GLB files
        - 'supabase.co': Ensures we only transform Supabase Storage URLs, not external CDNs

        Args:
            url: Original URL from database (S3 or NULL)

        Returns:
            CDN URL if transformation applied, original URL if skipped, None if input was None
        """
        from config import settings

        # Early return: NULL URLs remain NULL (geometry not processed yet)
        if url is None:
            return None

        # Early return: CDN disabled (development mode with direct S3 access)
        if not settings.USE_CDN:
            return url

        # Early return: Not a Supabase S3 URL (external CDN or already transformed)
        if 'processed-geometry' not in url or 'supabase.co' not in url:
            return url

        # Transform: Extract path after bucket name and prepend CDN base URL
        # Example: https://xxx.supabase.co/.../processed-geometry/low-poly/550e8400.glb
        #       -> https://xxx.cloudfront.net/low-poly/550e8400.glb
        path = url.split('processed-geometry/')[-1]
        return f"{settings.CDN_BASE_URL}/{path}"

    def _transform_row_to_element(self, row: Dict[str, Any]) -> Element:
        """
        Transform database row to Element Pydantic model.

        Handles NULL-safe extraction of optional fields (low_poly_url, bbox)
        and JSONB parsing for bounding box data.

        T-1001-INFRA: Delegates CDN URL transformation to _apply_cdn_transformation().

        Args:
            row: Database row dictionary from Supabase query result

        Returns:
            Element with all fields populated from row
        """
        # Parse bbox from JSONB to Pydantic model (NULL-safe)
        bbox_data = row.get("bbox")
        bbox = None
        if bbox_data is not None:
            bbox = BoundingBox(
                min=bbox_data["min"],
                max=bbox_data["max"]
            )

        # T-1001-INFRA: Apply CDN transformation if enabled (extracted method)
        low_poly_url = self._apply_cdn_transformation(row.get("low_poly_url"))

        return Element(
            id=row["id"],
            iso_code=row["iso_code"],
            status=ElementStatus(row["status"]),
            material_type=row["material_type"],
            low_poly_url=low_poly_url,  # CDN-transformed or original
            bbox=bbox
        )

    def _build_filters_applied(self, status: Optional[str], material_type: Optional[str]) -> Dict[str, str]:
        """
        Build filters_applied dictionary from non-NULL filter parameters.

        Args:
            status: Status filter value
            material_type: Material type filter value

        Returns:
            Dictionary with only non-NULL filters included
        """
        filters = {}
        if status is not None:
            filters["status"] = status
        if material_type is not None:
            filters["material_type"] = material_type
        return filters

    def _validate_material_type(self, material_type: str) -> None:
        """
        Validate material_type against MATERIAL_COLORS dictionary (62 real materials).

        Args:
            material_type: Material type string to validate

        Raises:
            ValueError: If material not in VALID_MATERIALS list
        """
        from agent.constants import VALID_MATERIALS

        if material_type not in VALID_MATERIALS:
            raise ValueError(
                f"Invalid material_type: '{material_type}'. Must be one of {len(VALID_MATERIALS)} "
                f"valid materials (e.g., Montjuïc, Ulldecona, Floresta). "
                f"See agent.constants.MATERIAL_COLORS for full list."
            )

    def list_elements(
        self,
        status: Optional[str] = None,
        material_type: Optional[str] = None
    ) -> ElementsListResponse:
        """
        List all render-ready elements with optional filtering.

        Application-level filtering (render-ready):
        - low_poly_url IS NOT NULL
        - bbox IS NOT NULL

        Query optimization:
        - Uses composite index idx_blocks_canvas_query (status, material_type)
        - Always filters is_archived=false
        - Returns minimal fields for 3D rendering (no heavy blobs)

        Args:
            status: Filter by lifecycle status (validated, in_fabrication, etc.)
            material_type: Filter by stone material (Montjuïc, Ulldecona, etc.)

        Returns:
            ElementsListResponse with:
            - elements: Array of Element (render-ready only)
            - filters_applied: Echo of applied filters
            - meta: {total: int, filtered: int}

        Raises:
            ValueError: If material_type is invalid (not in 63 materials)
            Exception: If database query fails

        Examples:
            >>> from infra.supabase_client import get_supabase_client
            >>> service = ElementsService(get_supabase_client())
            >>>
            >>> # Get all render-ready elements
            >>> result = service.list_elements()
            >>> len(result.elements)
            124
            >>> result.meta["total"]
            124
            >>>
            >>> # Filter by status
            >>> result = service.list_elements(status="validated")
            >>> result.filters_applied
            {"status": "validated"}
            >>>
            >>> # Filter by material type
            >>> result = service.list_elements(material_type="Montjuïc")
            >>> all(e.material_type == "Montjuïc" for e in result.elements)
            True
            >>>
            >>> # Combine multiple filters
            >>> result = service.list_elements(status="validated", material_type="Ulldecona")
            >>> result.filters_applied
            {"status": "validated", "material_type": "Ulldecona"}
        """
        # Validate material_type if provided
        if material_type is not None:
            self._validate_material_type(material_type)

        # Build base query with render-ready filter (application-level)
        query = (
            self.supabase
            .table(TABLE_BLOCKS)
            .select(ELEMENTS_LIST_SELECT_FIELDS)
            .eq(QUERY_FIELD_IS_ARCHIVED, False)
            .not_.is_("low_poly_url", "null")  # Render-ready: GLB must exist
            .not_.is_("bbox", "null")          # Render-ready: bbox must exist
        )

        # Apply dynamic filters
        if status is not None:
            query = query.eq("status", status)
        if material_type is not None:
            query = query.eq("material_type", material_type)

        # Execute query with ordering
        query = query.order(QUERY_FIELD_CREATED_AT, desc=QUERY_ORDER_DESC)
        response = query.execute()

        # Transform rows to Pydantic models
        elements = [self._transform_row_to_element(row) for row in response.data]

        # Build response
        filters_applied = self._build_filters_applied(status, material_type)

        return ElementsListResponse(
            elements=elements,
            filters_applied=filters_applied,
            meta={
                "total": len(elements),
                "filtered": len(elements)
            }
        )
