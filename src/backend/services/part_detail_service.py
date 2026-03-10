"""
T-1002-BACK: Part Detail Service
Business logic for fetching individual part details with RLS enforcement.
"""
import re
from typing import Optional, Tuple, Dict, Any
from uuid import UUID
from infra.supabase_client import get_supabase_client


# UUID regex for standard format validation: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class PartDetailService:
    """Service for fetching part details with Row-Level Security."""

    def __init__(self, supabase_client=None):
        """
        Initialize PartDetailService.

        Args:
            supabase_client: Optional Supabase client instance (for testing/DI).
                           If None, uses default client from infra.
        """
        self.client = supabase_client or get_supabase_client()

    def get_part_detail(
        self,
        part_id: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch a single part by ID.

        Args:
            part_id: UUID of the part to fetch

        Returns:
            Tuple of (success: bool, data: dict or None, error: str or None)
        """
        # Validate UUID format strictly (standard format with dashes)
        if not part_id or not UUID_PATTERN.match(part_id):
            return False, None, "Invalid UUID format"

        try:
            # Additional validation: try to parse as UUID (catches malformed hex)
            UUID(part_id)
        except (ValueError, AttributeError, TypeError):
            return False, None, "Invalid UUID format"

        try:
            # Query blocks table for part details
            query = self.client.from_('blocks').select(
                'id, iso_code, status, tipologia, created_at, '
                'low_poly_url, bbox, '
                'validation_report'
            ).eq('id', part_id)

            response = query.execute()

            # Check if any results
            if not response.data:
                return False, None, "Part not found or access denied"

            # Transform response
            part = response.data[0]
            return True, self._transform_response(part), None

        except Exception as e:
            return False, None, f"Database error: {str(e)}"

    def _transform_response(self, part: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw Supabase row to PartDetailResponse format.

        Handles missing columns defensively:
        - glb_size_bytes, triangle_count: Not in current schema, set to None

        Args:
            part: Raw Supabase row containing block data

        Returns:
            Dict[str, Any]: Transformed part data matching PartDetailResponse schema with fields:
                - id, iso_code, status, tipologia, created_at
                - low_poly_url, bbox
                - validation_report
                - glb_size_bytes, triangle_count (set to None)
        """
        return {
            'id': part.get('id'),
            'iso_code': part.get('iso_code'),
            'status': part.get('status'),
            'tipologia': part.get('tipologia'),
            'created_at': part.get('created_at'),
            'low_poly_url': part.get('low_poly_url'),
            'bbox': part.get('bbox'),
            'validation_report': part.get('validation_report'),
            'glb_size_bytes': None,  # Not in current schema
            'triangle_count': None,  # Not in current schema
        }
