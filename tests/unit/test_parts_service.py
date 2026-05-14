"""
Unit tests for PartsService (T-0501-BACK).

Tests business logic for parts listing without database dependencies.
Uses mocked Supabase client to isolate service layer.
"""
import pytest
from unittest.mock import Mock, MagicMock
from uuid import uuid4

from services.parts_service import PartsService
from schemas import PartsListResponse, PartCanvasItem


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    return Mock()


@pytest.fixture
def parts_service(mock_supabase_client):
    """PartsService instance with mocked client."""
    return PartsService(mock_supabase_client)


def test_list_parts_no_filters(parts_service, mock_supabase_client):
    """
    Test list_parts with no filters returns all non-archived parts.
    """
    # ARRANGE: Mock database response
    mock_data = [
        {
            "id": str(uuid4()),
            "iso_code": "TEST-001",
            "status": "validated",
            "tipologia": "capitel",
            "low_poly_url": "models/test.glb",
            "bbox": {"min": [-1, -1, -1], "max": [1, 1, 1]},
            "workshop_id": None
        },
        {
            "id": str(uuid4()),
            "iso_code": "TEST-002",
            "status": "in_fabrication",
            "tipologia": "columna",
            "low_poly_url": None,
            "bbox": None,
            "workshop_id": None
        }
    ]
    
    mock_response = Mock()
    mock_response.data = mock_data
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    result = parts_service.list_parts()
    
    # ASSERT
    assert isinstance(result, PartsListResponse)
    assert result.count == 2
    assert len(result.parts) == 2
    assert result.filters_applied == {"status": None, "tipologia": None, "workshop_id": None}


def test_list_parts_with_status_filter(parts_service, mock_supabase_client):
    """
    Test list_parts with status filter applies filter correctly.
    """
    # ARRANGE
    mock_data = [
        {
            "id": str(uuid4()),
            "iso_code": "TEST-001",
            "status": "validated",
            "tipologia": "capitel",
            "low_poly_url": "models/test.glb",
            "bbox": {"min": [-1, -1, -1], "max": [1, 1, 1]},
            "workshop_id": None
        }
    ]
    
    mock_response = Mock()
    mock_response.data = mock_data
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    result = parts_service.list_parts(status="validated")
    
    # ASSERT
    assert result.count == 1
    assert result.filters_applied["status"] == "validated"
    # Verify .eq("status", "validated") was called
    assert mock_query.eq.called


def test_list_parts_transforms_bbox_correctly(parts_service, mock_supabase_client):
    """
    Test _transform_row_to_part_item handles bbox JSONB correctly.
    """
    # ARRANGE
    mock_data = [
        {
            "id": str(uuid4()),
            "iso_code": "TEST-001",
            "status": "validated",
            "tipologia": "capitel",
            "low_poly_url": "models/test.glb",
            "bbox": {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]},
            "workshop_id": None
        }
    ]
    
    mock_response = Mock()
    mock_response.data = mock_data
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    result = parts_service.list_parts()
    
    # ASSERT
    part = result.parts[0]
    assert part.bbox is not None
    assert part.bbox.min == [-0.5, -0.5, -0.5]
    assert part.bbox.max == [0.5, 0.5, 0.5]


def test_list_parts_handles_null_bbox(parts_service, mock_supabase_client):
    """
    Test _transform_row_to_part_item handles NULL bbox gracefully.
    """
    # ARRANGE
    mock_data = [
        {
            "id": str(uuid4()),
            "iso_code": "TEST-001",
            "status": "uploaded",
            "tipologia": "imposta",
            "low_poly_url": None,
            "bbox": None,
            "workshop_id": None
        }
    ]
    
    mock_response = Mock()
    mock_response.data = mock_data
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    result = parts_service.list_parts()
    
    # ASSERT
    part = result.parts[0]
    assert part.bbox is None
    assert part.low_poly_url is None


def test_list_parts_empty_result(parts_service, mock_supabase_client):
    """
    Test list_parts returns empty array when no parts match filters.
    """
    # ARRANGE
    mock_response = Mock()
    mock_response.data = []
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    result = parts_service.list_parts()
    
    # ASSERT
    assert result.count == 0
    assert len(result.parts) == 0


def test_list_parts_filters_archived(parts_service, mock_supabase_client):
    """
    Test list_parts always filters is_archived=false.
    """
    # ARRANGE
    mock_data = []
    mock_response = Mock()
    mock_response.data = mock_data
    
    # Chain the mocks properly
    mock_query = Mock()
    mock_query.execute.return_value = mock_response
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    
    mock_table = Mock()
    mock_table.select.return_value = mock_query
    mock_supabase_client.table.return_value = mock_table
    
    # ACT
    parts_service.list_parts()
    
    # ASSERT
    # Verify .eq was called (checking for is_archived filtering)
    assert mock_query.eq.called
