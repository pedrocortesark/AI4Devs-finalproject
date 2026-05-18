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

        # T-1001-INFRA + US-015: Apply CDN transformation to all LOD URLs
        high_poly_url = self._apply_cdn_transformation(row.get("high_poly_url"))
        mid_poly_url = self._apply_cdn_transformation(row.get("mid_poly_url"))
        low_poly_url = self._apply_cdn_transformation(row.get("low_poly_url"))
        mtl_url = row.get("mtl_url") or None

        # Extract SF_ARC_Agrupacio1 from rhino_metadata JSONB
        rhino_metadata = row.get("rhino_metadata") or {}
        agrupacio_raw = rhino_metadata.get("SF_ARC_Agrupacio1") if isinstance(rhino_metadata, dict) else None
        agrupacio = str(agrupacio_raw) if agrupacio_raw is not None else None

        # Extract the stone material from the .3dm "Material" UserString.
        # rhino_metadata is populated by the async geometry_processing task; its
        # exact shape varies (flat top-level keys vs the nested
        # {document, layers, objects} UserStringCollection), so probe both —
        # same precedence as node_enrich_metadata (document first, then objects).
        material = self._extract_material(rhino_metadata)

        return Element(
            id=row["id"],
            iso_code=row["iso_code"],
            status=ElementStatus(row["status"]),
            high_poly_url=high_poly_url,  # CDN-transformed or None
            mid_poly_url=mid_poly_url,    # CDN-transformed or None
            low_poly_url=low_poly_url,    # CDN-transformed or None
            mtl_url=mtl_url,
            bbox=bbox,
            agrupacio=agrupacio,
            material=material,
            rhino_metadata=rhino_metadata if isinstance(rhino_metadata, dict) else None,
        )

    @staticmethod
    def _extract_material(rhino_metadata: Any) -> Optional[str]:
        """Return the 'Material' UserString from rhino_metadata, or None.

        Defensive against both persisted shapes:
          - flat:   {"Material": "Montjuïc", "Codi": "...", ...}
          - nested: {"document": {"Material": "..."}, "objects": {<id>: {...}}}
        """
        if not isinstance(rhino_metadata, dict):
            return None
        # Flat top-level
        val = rhino_metadata.get("Material")
        if val:
            return str(val)
        # Nested document-level
        document = rhino_metadata.get("document")
        if isinstance(document, dict) and document.get("Material"):
            return str(document["Material"])
        # Fallback: first object-level user strings
        objects = rhino_metadata.get("objects")
        if isinstance(objects, dict):
            for obj_strings in objects.values():
                if isinstance(obj_strings, dict) and obj_strings.get("Material"):
                    return str(obj_strings["Material"])
        return None

    def _build_filters_applied(self, status: Optional[str]) -> Dict[str, str]:
        """
        Build filters_applied dictionary from non-NULL filter parameters.

        Args:
            status: Status filter value

        Returns:
            Dictionary with only non-NULL filters included
        """
        filters = {}
        if status is not None:
            filters["status"] = status
        return filters



    def list_elements(
        self,
        status: Optional[str] = None
    ) -> ElementsListResponse:
        """
        List all render-ready elements with optional filtering.

        Application-level filtering (render-ready):
        - low_poly_url IS NOT NULL
        - bbox IS NOT NULL

        Query optimization:
        - Uses composite index idx_blocks_canvas_query (status)
        - Always filters is_archived=false
        - Returns minimal fields for 3D rendering (no heavy blobs)

        Args:
            status: Filter by lifecycle status (validated, in_fabrication, etc.)

        Returns:
            ElementsListResponse with:
            - elements: Array of Element (render-ready only)
            - filters_applied: Echo of applied filters
            - meta: {total: int, filtered: int}

        Raises:
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
        """
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

        # Execute query with ordering
        query = query.order(QUERY_FIELD_CREATED_AT, desc=QUERY_ORDER_DESC)
        response = query.execute()

        # Transform rows to Pydantic models
        elements = [self._transform_row_to_element(row) for row in response.data]

        # Build response
        filters_applied = self._build_filters_applied(status)

        return ElementsListResponse(
            elements=elements,
            filters_applied=filters_applied,
            meta={
                "total": len(elements),
                "filtered": len(elements)
            }
        )
