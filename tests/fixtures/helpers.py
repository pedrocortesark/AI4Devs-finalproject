"""
Reusable test helpers for T-1507-TEST Integration Tests

Provides:
  - upload_and_confirm(): Full file upload pipeline helper
  - cleanup_test_elements(): Supabase cleanup helper
  - mock_element_factory(): Generate test Element objects
"""

import uuid
from typing import Optional
from pathlib import Path


def upload_and_confirm(
    client, 
    supabase_client, 
    file_path: Path, 
    test_prefix: str = "test-element-e2e"
) -> dict:
    """
    Helper: Execute full upload → confirm → wait for processing pipeline

    Args:
        client: FastAPI TestClient instance
        supabase_client: Supabase client fixture
        file_path: Path to .3dm file to upload
        test_prefix: Unique prefix for test cleanup

    Returns:
        dict with keys: file_id, presigned_url, upload_response, confirm_response

    Raises:
        AssertionError: If any step fails
    """
    # Step 1: Get presigned URL
    presigned_response = client.post(
        "/api/files/upload",
        json={
            "filename": file_path.name,
            "content_type": "application/x-3dm",
        }
    )
    assert presigned_response.status_code == 200, \
        f"Presigned URL generation failed: {presigned_response.text}"

    presigned_data = presigned_response.json()
    file_id = presigned_data["file_id"]
    presigned_url = presigned_data["presigned_url"]

    # Step 2: Upload file to Supabase Storage
    with open(file_path, "rb") as f:
        file_content = f.read()

    upload_response = client.put(
        presigned_url,
        content=file_content,
        headers={"Content-Type": "application/x-3dm"}
    )
    assert upload_response.status_code in [200, 201], \
        f"Storage upload failed: {upload_response.text}"

    # Step 3: Confirm upload (triggers Celery processing)
    confirm_response = client.post(
        f"/api/files/{file_id}/confirm",
        json={"iso_code": f"{test_prefix}-{uuid.uuid4().hex[:8]}"}
    )
    assert confirm_response.status_code == 200, \
        f"Upload confirmation failed: {confirm_response.text}"

    return {
        "file_id": file_id,
        "iso_code": confirm_response.json()["iso_code"],
        "presigned_url": presigned_url,
        "upload_response": upload_response,
        "confirm_response": confirm_response,
    }


def cleanup_test_elements(supabase_client, test_prefix: str = "test-element-e2e"):
    """
    Helper: Clean up test elements from database

    Args:
        supabase_client: Supabase client fixture
        test_prefix: Prefix used in iso_code for test elements

    Returns:
        int: Number of elements deleted
    """
    result = supabase_client.table("Element") \
        .delete() \
        .like("iso_code", f"{test_prefix}%") \
        .execute()
    
    return len(result.data) if result.data else 0


def mock_element_factory(
    iso_code: Optional[str] = None,
    status: str = "validated",
    material_type: str = "Montjuïc",
    low_poly_url: Optional[str] = None,
    bbox: Optional[dict] = None,
) -> dict:
    """
    Helper: Generate mock Element object for testing

    Args:
        iso_code: Element ISO code (generates random if None)
        status: Element status (default: "validated")
        material_type: Material type (default: "Montjuïc")
        low_poly_url: Low-poly GLB URL (generates placeholder if None)
        bbox: Bounding box (generates default if None)

    Returns:
        dict: Mock Element object matching API schema
    """
    element_id = str(uuid.uuid4())
    iso_code = iso_code or f"MOCK-{uuid.uuid4().hex[:8]}"
    file_id = str(uuid.uuid4())

    if low_poly_url is None:
        low_poly_url = f"https://example.supabase.co/storage/v1/object/public/glb-files/{file_id}/low_poly.glb"

    if bbox is None:
        bbox = {
            "min": [0.0, 0.0, 0.0],
            "max": [100.0, 100.0, 100.0]
        }

    return {
        "id": element_id,
        "iso_code": iso_code,
        "status": status,
        "material_type": material_type,
        "low_poly_url": low_poly_url,
        "bbox": bbox,
        "validation_report": None,
        "rhino_metadata": {},
        "created_at": "2026-03-09T12:00:00Z",
        "updated_at": "2026-03-09T12:00:00Z",
    }
