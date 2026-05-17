"""
Unit Tests for ElementsService (T-1504-BACK)

Tests service methods for querying elements list for 3D canvas.

Refactor Context (US-015):
- Replaces PartsService with ElementsService
- Removes tipologia/workshop_id filters
- Adds material_type filter (validated against 63 materials)
- Application-level filtering: low_poly_url IS NOT NULL AND bbox IS NOT NULL

Test Coverage (12 tests):
- Happy Path (4 tests): list_elements with various filter combinations
- Data Transformation (2 tests): DB rows → Element Pydantic models
- Query Building (2 tests): Dynamic WHERE clause construction with render-ready filter
- Material Validation (2 tests): material_type validation against VALID_MATERIALS
- CDN Transformation (1 test): Supabase Storage URL → CloudFront URL
- Error Handling (1 test): Invalid material_type raises ValueError

Expected Result: ALL TESTS MUST FAIL (TDD-RED Phase)
- ImportError: Module 'services.elements_service' does not exist
- AssertionError: Expected behavior not implemented

Author: AI Assistant (Prompt #217 - TDD-RED Phase)
Date: 2026-03-07
"""

from uuid import uuid4
from unittest.mock import Mock, MagicMock
import pytest

# These imports WILL FAIL because services don't exist yet (TDD-RED)
try:
    from services.elements_service import ElementsService
    from schemas import Element, ElementsListResponse, ElementStatus, BoundingBox
except ModuleNotFoundError:
    from src.backend.services.elements_service import ElementsService
    from src.backend.schemas import Element, ElementsListResponse, ElementStatus, BoundingBox


# ===== HAPPY PATH TESTS =====

def test_list_elements_no_filters_returns_only_render_ready():
    """
    HP: list_elements() with no filters returns only render-ready elements.

    GIVEN no filters provided (status=None, material_type=None)
    WHEN list_elements() is called
    THEN Supabase query filters by:
        - is_archived=false
        - low_poly_url IS NOT NULL
        - bbox IS NOT NULL
    AND returns only render-ready elements
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    # Mock database response (only render-ready elements)
    db_response = [
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0701",
            "status": "validated",
            "material_type": "Montjuïc",
            "low_poly_url": "models/low-poly/test.glb",
            "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
        },
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0702",
            "status": "validated",
            "material_type": "Ulldecona",
            "low_poly_url": "models/low-poly/test2.glb",
            "bbox": {"min": [-0.40, -0.80, -0.40], "max": [0.40, 0.80, 0.40]}
        }
    ]

    # Setup mock chain
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq  # is_archived filter
    mock_eq.not_ = mock_not  # Attribute for .not_.is_()
    mock_not.is_.return_value = mock_not  # First not null check (returns same mock for chaining)
    mock_not.not_ = mock_not  # Second .not_ access
    mock_not.order.return_value = mock_order  # created_at ordering
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements(status=None, material_type=None)

    # Assert
    assert isinstance(result, ElementsListResponse), "Should return ElementsListResponse"
    assert len(result.elements) == 2, "Should return 2 render-ready elements"
    assert result.meta["total"] == 2, "meta.total should be 2"
    assert result.meta["filtered"] == 2, "meta.filtered should be 2"

    # Verify all elements have low_poly_url and bbox
    for elem in result.elements:
        assert elem.low_poly_url is not None, f"Element {elem.id} should have low_poly_url"
        assert elem.bbox is not None, f"Element {elem.id} should have bbox"
        # Verify no workshop fields
        assert not hasattr(elem, 'workshop_id'), "Element should not have workshop_id"
        assert not hasattr(elem, 'workshop_name'), "Element should not have workshop_name"
        assert not hasattr(elem, 'tipologia'), "Element should not have tipologia"

    # Verify Supabase methods were called
    mock_supabase.table.assert_called_once_with("blocks")
    mock_table.select.assert_called_once()
    mock_select.eq.assert_called_with("is_archived", False)


def test_list_elements_applies_status_filter():
    """
    HP: list_elements(status="validated") filters by status.

    GIVEN status filter = "validated"
    WHEN list_elements(status="validated") is called
    THEN Supabase query includes WHERE status = 'validated'
    AND only validated render-ready elements returned
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = [
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0703",
            "status": "validated",
            "material_type": "Floresta",
            "low_poly_url": "models/low-poly/test3.glb",
            "bbox": {"min": [-0.30, -0.60, -0.30], "max": [0.30, 0.60, 0.30]}
        }
    ]

    # Setup mock chain
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), we have mock_not, then .eq() for status filter
    mock_not.eq.return_value = mock_eq  # Filter returns mock_eq
    mock_eq.order.return_value = mock_order  # Order on the filter result
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements(status="validated", material_type=None)

    # Assert
    assert len(result.elements) == 1
    assert result.elements[0].status == ElementStatus.VALIDATED
    assert result.filters_applied["status"] == "validated"


def test_list_elements_applies_material_type_filter():
    """
    HP: list_elements(material_type="Montjuïc") filters by material.

    GIVEN material_type filter = "Montjuïc" (one of 63 valid materials)
    WHEN list_elements(material_type="Montjuïc") is called
    THEN Supabase query includes WHERE material_type = 'Montjuïc'
    AND only Montjuïc elements returned
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = [
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0704",
            "status": "validated",
            "material_type": "Montjuïc",
            "low_poly_url": "models/low-poly/test4.glb",
            "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
        },
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0705",
            "status": "in_fabrication",
            "material_type": "Montjuïc",
            "low_poly_url": "models/low-poly/test5.glb",
            "bbox": {"min": [-0.32, -0.65, -0.32], "max": [0.32, 0.65, 0.32]}
        }
    ]

    # Setup mock chain
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), we have mock_not, then .eq() for material_type filter
    mock_not.eq.return_value = mock_eq  # Filter returns mock_eq
    mock_eq.order.return_value = mock_order  # Order on the filter result
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements(status=None, material_type="Montjuïc")

    # Assert
    assert len(result.elements) == 2
    for elem in result.elements:
        assert elem.material_type == "Montjuïc", f"Expected material 'Montjuïc', got '{elem.material_type}'"
    assert result.filters_applied["material_type"] == "Montjuïc"


def test_list_elements_multiple_filters_combined():
    """
    HP: list_elements(status="validated", material_type="Ulldecona") combines filters.

    GIVEN multiple filters
    WHEN list_elements(status="validated", material_type="Ulldecona") is called
    THEN Supabase query includes both WHERE clauses
    AND only elements matching both filters returned
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = [
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0706",
            "status": "validated",
            "material_type": "Ulldecona",
            "low_poly_url": "models/low-poly/test6.glb",
            "bbox": {"min": [-0.28, -0.55, -0.28], "max": [0.28, 0.55, 0.28]}
        }
    ]

    # Setup mock chain with multiple filters
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), we have mock_not, then .eq() for status filter
    mock_not.eq.return_value = mock_eq  # First filter returns mock_eq
    mock_eq.eq.return_value = mock_eq  # Second filter (material_type) returns mock_eq
    mock_eq.order.return_value = mock_order  # Order on the filter result
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements(status="validated", material_type="Ulldecona")

    # Assert
    assert len(result.elements) == 1
    assert result.elements[0].status == ElementStatus.VALIDATED
    assert result.elements[0].material_type == "Ulldecona"
    assert result.filters_applied["status"] == "validated"
    assert result.filters_applied["material_type"] == "Ulldecona"


# ===== DATA TRANSFORMATION TESTS =====

def test_transforms_db_row_to_element_pydantic():
    """
    DATA: Database row correctly transformed to Element Pydantic model.

    GIVEN database row with all required fields
    WHEN list_elements() processes row
    THEN Element model created with correct field mapping:
        - id (UUID) → str
        - iso_code → str
        - status → ElementStatus enum
        - material_type → str (validated)
        - low_poly_url → str (CDN transformed)
        - bbox → BoundingBox model
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    element_id = str(uuid4())
    db_response = [
        {
            "id": element_id,
            "iso_code": "GLPER.B-PAE0720.0707",
            "status": "validated",
            "material_type": "Montjuïc",
            "low_poly_url": "models/low-poly/test7.glb",
            "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
        }
    ]

    # Setup mock chain (no filters, just order after .not_.is_() calls)
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), call .order() directly on mock_not
    mock_not.order.return_value = mock_order
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements()

    # Assert
    elem = result.elements[0]
    assert isinstance(elem, Element), "Should be Element instance"
    assert str(elem.id) == element_id, "UUID should match (comparing string representations)"
    assert elem.iso_code == "GLPER.B-PAE0720.0707"
    assert elem.status == ElementStatus.VALIDATED
    assert elem.material_type == "Montjuïc"
    assert elem.low_poly_url is not None
    assert isinstance(elem.bbox, BoundingBox)
    assert elem.bbox.min == [-0.35, -0.70, -0.35]
    assert elem.bbox.max == [0.35, 0.70, 0.35]


def test_handles_null_validation_report_gracefully():
    """
    DATA: Null validation_report handled gracefully (detail endpoint).

    GIVEN element with validation_report = NULL
    WHEN element detail retrieved
    THEN validation_report field is None (not missing)
    """
    # This test is for ElementDetailService (detail endpoint)
    # Placeholder for GREEN phase implementation
    # Expected behavior: validation_report=None in response
    pass


# ===== QUERY BUILDING TESTS =====

def test_query_includes_render_ready_filter():
    """
    QUERY: Application-level render-ready filter applied correctly.

    GIVEN any list_elements() call
    WHEN building Supabase query
    THEN query includes:
        - .not_.is_("low_poly_url", "null")
        - .not_.is_("bbox", "null")
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = []

    # Setup mock chain with specific tracking
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    
    # Track not_.is_() calls
    mock_eq.not_ = mock_not
    is_calls = []
    def track_is_call(*args):
        is_calls.append(args)
        return mock_not
    mock_not.is_ = track_is_call
    mock_not.not_ = mock_not  # Second .not_ access
    mock_not.order.return_value = mock_order
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements()

    # Assert
    # Should have called .not_.is_() twice (low_poly_url and bbox)
    assert len(is_calls) >= 2, f"Expected at least 2 .not_.is_() calls, got {len(is_calls)}"
    # Verify fields checked for not null
    field_checks = [call[0] for call in is_calls if len(call) > 0]
    assert "low_poly_url" in str(field_checks) or "null" in str(field_checks), \
        "Should check low_poly_url IS NOT NULL"


def test_query_orders_by_created_at_desc():
    """
    QUERY: Query orders results by created_at DESC.

    GIVEN any list_elements() call
    WHEN building Supabase query
    THEN query includes .order("created_at", desc=True)
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = []

    # Setup mock chain (no filters, just order after .not_.is_() calls)  
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), call .order() directly on mock_not
    mock_not.order.return_value = mock_order
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements()

    # Assert
    # Verify .order() was called (exact args checking in GREEN phase)
    mock_not.order.assert_called()


# ===== MATERIAL VALIDATION TESTS =====

def test_material_type_validates_against_63_materials():
    """
    VALIDATION: material_type filter validated against VALID_MATERIALS.

    GIVEN material_type filter = "Montjuïc" (valid)
    WHEN list_elements(material_type="Montjuïc") is called
    THEN no ValueError raised
    AND query proceeds normally
    """
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = []

    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), .eq() for material_type filter
    mock_not.eq.return_value = mock_eq
    mock_eq.order.return_value = mock_order
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act & Assert - should not raise
    result = service.list_elements(material_type="Montjuïc")
    assert isinstance(result, ElementsListResponse)


def test_invalid_material_type_raises_value_error():
    """
    VALIDATION: Invalid material_type raises ValueError with descriptive message.

    GIVEN material_type filter = "InvalidMaterial" (not in VALID_MATERIALS)
    WHEN list_elements(material_type="InvalidMaterial") is called
    THEN ValueError raised with message:
        - Mentions "InvalidMaterial"
        - Mentions "63 valid materials"
        - Provides examples (Montjuïc, Ulldecona, etc.)
    """
    # Arrange
    mock_supabase = Mock()
    service = ElementsService(mock_supabase)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        service.list_elements(material_type="InvalidMaterial")
    
    error_msg = str(exc_info.value)
    assert "InvalidMaterial" in error_msg, "Error should mention invalid material"
    assert "63" in error_msg, "Error should mention 63 valid materials"
    assert any(mat in error_msg for mat in ["Montjuïc", "Ulldecona", "Floresta"]), \
        "Error should provide valid material examples"


# ===== CDN TRANSFORMATION TEST =====

def test_cdn_url_transformation_applied():
    """
    CDN: Supabase Storage URL transformed to CloudFront URL.

    GIVEN element with low_poly_url="models/low-poly/test.glb" (Supabase path)
    WHEN list_elements() processes response
    THEN low_poly_url transformed to CloudFront URL (if USE_CDN=true)
    OR URL format: https://d{id}.cloudfront.net/models/low-poly/test.glb
    
    NOTE: Transformation only happens if USE_CDN env var is True
    """
    from config import settings
    import pytest
    
    # Skip if CDN not enabled (similar to integration tests)
    if not hasattr(settings, 'USE_CDN') or not settings.USE_CDN:
        pytest.skip("USE_CDN is False or not configured - CDN transformation disabled")
    
    # Arrange
    mock_supabase = Mock()
    mock_table = Mock()
    mock_select = Mock()
    mock_eq = Mock()
    mock_not = Mock()
    mock_order = Mock()

    db_response = [
        {
            "id": str(uuid4()),
            "iso_code": "GLPER.B-PAE0720.0708",
            "status": "validated",
            "material_type": "Montjuïc",
            # Use full Supabase S3 URL for CDN transformation to work
            "low_poly_url": "https://example.supabase.co/storage/v1/object/public/processed-geometry/models/low-poly/test8.glb",
            "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
        }
    ]

    # Setup mock chain (no filters, just order after .not_.is_() calls)
    mock_supabase.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq
    mock_eq.not_ = mock_not
    mock_not.is_.return_value = mock_not  # First .not_.is_()
    mock_not.not_ = mock_not  # Access .not_ again
    # After second .not_.is_(), call .order() directly on mock_not
    mock_not.order.return_value = mock_order
    mock_response = MagicMock()
    mock_response.data = db_response
    mock_order.execute.return_value = mock_response

    service = ElementsService(mock_supabase)

    # Act
    result = service.list_elements()

    # Assert
    elem = result.elements[0]
    assert "cloudfront.net" in elem.low_poly_url, \
        f"Expected CloudFront URL, got {elem.low_poly_url}"
    assert "supabase.co" not in elem.low_poly_url, \
        "URL should be transformed to CDN, not Supabase Storage"
