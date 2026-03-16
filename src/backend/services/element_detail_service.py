"""
T-1504-BACK: Element Detail Service
Business logic for fetching individual element details.

Breaking Changes from PartDetailService:
- Removed workshop_id filtering (no workshops in MVP)
- Removed RLS logic (simplified access control)
- Added material_type field
"""
import re
from typing import Optional, Tuple, Dict, Any
from uuid import UUID
from infra.supabase_client import get_supabase_client
from constants import (
    TABLE_BLOCKS,
    ELEMENT_DETAIL_SELECT_FIELDS,
    ERROR_MSG_ELEMENT_NOT_FOUND,
    ERROR_MSG_INVALID_UUID_FORMAT,
    ERROR_MSG_DATABASE_ERROR,
)


# UUID regex for standard format validation: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class ElementDetailService:
    """Service for fetching element details."""

    def __init__(self, supabase_client=None):
        """
        Initialize ElementDetailService.

        Args:
            supabase_client: Optional Supabase client instance (for testing/DI).
                           If None, uses default client from infra.
        """
        self.client = supabase_client or get_supabase_client()

    def get_element_detail(
        self,
        element_id: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch a single element by ID.

        Args:
            element_id: UUID of the element to fetch

        Returns:
            Tuple of (success: bool, data: dict or None, error: str or None)
            - success=True: data contains element dict, error is None
            - success=False: data is None, error contains error message

        Examples:
            >>> service = ElementDetailService()
            >>>
            >>> # Successful fetch
            >>> success, data, error = service.get_element_detail(
            ...     "550e8400-e29b-41d4-a716-446655440000"
            ... )
            >>> success
            True
            >>> data["iso_code"]
            "SF-BLC-001-002"
            >>> data["material_type"]
            "Montjuïc"
            >>> error
            None
            >>>
            >>> # Element not found
            >>> success, data, error = service.get_element_detail(
            ...     "00000000-0000-0000-0000-000000000000"
            ... )
            >>> success
            False
            >>> data
            None
            >>> error
            "Element not found"
            >>>
            >>> # Invalid UUID format
            >>> success, data, error = service.get_element_detail("invalid-uuid")
            >>> success
            False
            >>> error
            "Invalid UUID format"
        """
        # Validate UUID format strictly (standard format with dashes)
        if not element_id or not UUID_PATTERN.match(element_id):
            return False, None, "Invalid UUID format"

        try:
            # Additional validation: try to parse as UUID (catches malformed hex)
            UUID(element_id)
        except (ValueError, AttributeError, TypeError):
            return False, None, ERROR_MSG_INVALID_UUID_FORMAT

        try:
            # Query element by ID
            query = self.client.from_(TABLE_BLOCKS).select(
                ELEMENT_DETAIL_SELECT_FIELDS
            ).eq('id', element_id)

            response = query.execute()

            # Check if any results
            if not response.data:
                return False, None, ERROR_MSG_ELEMENT_NOT_FOUND

            # Transform response
            element = response.data[0]
            return True, self._transform_response(element), None

        except Exception as e:
            return False, None, ERROR_MSG_DATABASE_ERROR.format(error=str(e))

    def _transform_response(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw Supabase row to ElementDetail format.

        Handles missing columns defensively:
        - glb_size_bytes, triangle_count: Not in current schema, set to None

        Args:
            element: Raw Supabase row containing block data

        Returns:
            Dict[str, Any]: Transformed element data matching ElementDetail schema with fields:
                - id, iso_code, status, material_type, created_at
                - low_poly_url, bbox
                - validation_report
                - glb_size_bytes, triangle_count (set to None)
        """
        return {
            'id': element.get('id'),
            'iso_code': element.get('iso_code'),
            'status': element.get('status'),
            'material_type': element.get('material_type'),
            'created_at': element.get('created_at'),
            'high_poly_url': element.get('high_poly_url'),
            'mid_poly_url': element.get('mid_poly_url'),
            'low_poly_url': element.get('low_poly_url'),
            'bbox': element.get('bbox'),
            'validation_report': element.get('validation_report'),
            'rhino_metadata': element.get('rhino_metadata'),
            'glb_size_bytes': None,  # Not in current schema
            'triangle_count': None,  # Not in current schema
        }
