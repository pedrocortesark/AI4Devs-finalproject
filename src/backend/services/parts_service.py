"""
Business logic for parts listing operations.

Handles querying and transformation of parts data for 3D canvas rendering.
Implements GET /api/parts endpoint business logic (T-0501-BACK).
"""

from typing import Optional, Dict, Any
from supabase import Client

from schemas import PartCanvasItem, PartsListResponse, BoundingBox
from constants import (
    TABLE_BLOCKS,
    PARTS_LIST_SELECT_FIELDS,
    QUERY_FIELD_IS_ARCHIVED,
    QUERY_FIELD_CREATED_AT,
)


class PartsService:
    """
    Service for parts list operations.

    Handles database queries and transforms raw data into API-ready format.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize service with Supabase client.

        Args:
            supabase_client: Authenticated Supabase client
        """
        self.supabase = supabase_client

    def list_parts(
        self,
        status: Optional[str] = None,
        tipologia: Optional[str] = None,
        workshop_id: Optional[str] = None
    ) -> PartsListResponse:
        """
        List all parts with optional filtering.

        Query optimization:
        - Uses composite index idx_blocks_canvas_query (status, tipologia, workshop_id)
        - Always filters is_archived=false
        - Returns minimal fields for 3D rendering (no heavy blobs)

        Args:
            status: Filter by lifecycle status (validated, in_fabrication, etc.)
            tipologia: Filter by part type (capitel, columna, dovela, etc.)
            workshop_id: Filter by assigned workshop UUID

        Returns:
            PartsListResponse with parts array, count, and filters_applied

        Raises:
            Exception: If database query fails (handled by API layer)
        """
        # Build query with dynamic filters
        query = self.supabase.table(TABLE_BLOCKS).select(PARTS_LIST_SELECT_FIELDS)

        # Always filter archived blocks
        query = query.eq(QUERY_FIELD_IS_ARCHIVED, False)

        # Apply optional filters
        if status:
            query = query.eq("status", status)
        if tipologia:
            query = query.eq("tipologia", tipologia)
        if workshop_id:
            query = query.eq("workshop_id", workshop_id)

        # Sort by created_at descending (newest first)
        query = query.order(QUERY_FIELD_CREATED_AT, desc=True)

        # Execute query
        response = query.execute()

        # Transform rows to PartCanvasItem
        parts = [self._transform_row_to_part_item(row) for row in response.data]

        # Build filters_applied dict
        filters_applied = self._build_filters_applied(status, tipologia, workshop_id)

        return PartsListResponse(
            parts=parts,
            count=len(parts),
            filters_applied=filters_applied
        )

    def _transform_row_to_part_item(self, row: Dict[str, Any]) -> PartCanvasItem:
        """
        Transform database row to PartCanvasItem.

        Handles NULL values for optional fields (low_poly_url, bbox, workshop_id).

        Args:
            row: Raw database row dict

        Returns:
            PartCanvasItem with standardized structure
        """
        # Parse bbox from JSONB (handle NULL)
        bbox = None
        if row.get("bbox"):
            bbox_data = row["bbox"]
            bbox = BoundingBox(
                min=bbox_data["min"],
                max=bbox_data["max"]
            )

        return PartCanvasItem(
            id=row["id"],
            iso_code=row["iso_code"],
            status=row["status"],
            tipologia=row["tipologia"],
            low_poly_url=row.get("low_poly_url"),
            bbox=bbox,
            workshop_id=row.get("workshop_id")
        )

    def _build_filters_applied(
        self,
        status: Optional[str],
        tipologia: Optional[str],
        workshop_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Build filters_applied dict for transparency.

        Args:
            status: Status filter value
            tipologia: Tipologia filter value
            workshop_id: Workshop ID filter value

        Returns:
            Dict with applied filters (None if not applied)
        """
        return {
            "status": status,
            "tipologia": tipologia,
            "workshop_id": workshop_id
        }
