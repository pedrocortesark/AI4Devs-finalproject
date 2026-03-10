"""
Integration tests for T-029-BACK: Trigger Validation from Confirm Endpoint

TDD Phase: GREEN — These tests verify the full endpoint flow:
  POST /api/upload/confirm → blocks created → task enqueued → task_id returned

Requires:
  - PostgreSQL (db service) for blocks table
  - Redis (via Celery eager mode from conftest.py) for task execution
  - Supabase (for file storage and blocks table)

Tests:
  1. Endpoint returns task_id (not null) on happy path
  2. Block records created in DB (one per InstanceDefinition in test-model.3dm)
  3. Payload validation still returns 422 (no-regression)
  4. File not found returns 404, no block created

Architecture Note:
  As of register_3dm_blocks refactor, blocks are created asynchronously by 
  parsing the .3dm file and creating one block per InstanceDefinition. 
  The test-model.3dm fixture contains 6 InstanceDefinitions (GLPER.B-PAE0720.070X).
"""

from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Load real .3dm fixture for magic bytes validation
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
test_3dm_content = (FIXTURE_DIR / "test-model.3dm").read_bytes()

# Expected InstanceDefinitions in test-model.3dm
EXPECTED_ISO_CODES = [
    "GLPER.B-PAE0720.0702",
    "GLPER.B-PAE0720.0704",
    "GLPER.B-PAE0720.0706",
    "GLPER.B-PAE0720.0701",
    "GLPER.B-PAE0720.0703",
    "GLPER.B-PAE0720.0705",
]


def _cleanup_test_blocks(supabase_client):
    """Helper to remove test fixture blocks from Supabase."""
    try:
        supabase_client.table("blocks").delete().in_(
            "iso_code", EXPECTED_ISO_CODES
        ).execute()
    except Exception:
        pass


def test_confirm_upload_returns_task_id(supabase_client):
    """
    T-029-BACK Integration Test 1:
    When confirming a valid upload, the response should include
    a non-null task_id indicating the validation task was enqueued.

    Given: A file exists in Supabase Storage
    When: POST /api/upload/confirm with valid file_id and file_key
    Then:
        - Response 200 with success=True
        - task_id is NOT null (Celery task was enqueued)
        - event_id is NOT null (event was created)
    """
    # Arrange: Upload test file to storage
    bucket_name = "raw-uploads"
    test_file_key = "test/t029_enqueue_test.3dm"

    file_id = "029e8400-e29b-41d4-a716-446655440029"

    # Cleanup stale data from previous runs
    try:
        supabase_client.storage.from_(bucket_name).remove([test_file_key])
    except Exception:
        pass
    _cleanup_test_blocks(supabase_client)

    supabase_client.storage.from_(bucket_name).upload(
        path=test_file_key,
        file=test_3dm_content,
        file_options={"content-type": "application/x-rhino"}
    )

    payload = {
        "file_id": file_id,
        "file_key": test_file_key
    }

    # Act
    response = client.post("/api/upload/confirm", json=payload)

    # Assert
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    data = response.json()
    assert data["success"] is True
    assert data["event_id"] is not None, "event_id should not be null"
    assert data["task_id"] is not None, (
        "task_id should NOT be null — T-029-BACK requires Celery task enqueue"
    )

    # Cleanup
    supabase_client.storage.from_(bucket_name).remove([test_file_key])
    _cleanup_test_blocks(supabase_client)


def test_confirm_upload_creates_block_record(supabase_client):
    """
    T-029-BACK Integration Test 2:
    When confirming a valid upload, block records should be created
    in the blocks table (one per InstanceDefinition in the .3dm file).

    Given: A file exists in Supabase Storage (test-model.3dm with 6 InstanceDefinitions)
    When: POST /api/upload/confirm
    Then:
        - 6 rows exist in blocks table with iso_codes from InstanceDefinitions
        - Blocks have correct url_original matching the file_key
    
    Architecture Note:
        The register_3dm_blocks task (runs eagerly in tests) parses the .3dm file
        and creates one block per InstanceDefinition. The PENDING-{file_id} pattern
        was deprecated in favor of actual iso_codes from block definitions.
    """
    # Arrange
    bucket_name = "raw-uploads"
    test_file_key = "test/t029_block_test.3dm"

    file_id = "029eaaaa-bbbb-41d4-a716-446655440029"

    # Cleanup stale data
    try:
        supabase_client.storage.from_(bucket_name).remove([test_file_key])
    except Exception:
        pass
    _cleanup_test_blocks(supabase_client)

    supabase_client.storage.from_(bucket_name).upload(
        path=test_file_key,
        file=test_3dm_content,
        file_options={"content-type": "application/x-rhino"}
    )

    payload = {
        "file_id": file_id,
        "file_key": test_file_key
    }

    # Act
    response = client.post("/api/upload/confirm", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    # Assert: Query blocks table via Supabase
    result = supabase_client.table("blocks").select(
        "id, iso_code, status, tipologia, url_original"
    ).in_("iso_code", EXPECTED_ISO_CODES).execute()

    assert len(result.data) == 6, (
        f"Expected 6 blocks (one per InstanceDefinition in test-model.3dm), "
        f"but found {len(result.data)}. T-029-BACK should create blocks via register_3dm_blocks task."
    )

    # Verify all expected iso_codes are present
    created_iso_codes = {block["iso_code"] for block in result.data}
    assert created_iso_codes == set(EXPECTED_ISO_CODES), (
        f"Expected iso_codes {set(EXPECTED_ISO_CODES)}, got {created_iso_codes}"
    )

    # Verify all blocks point to the uploaded file
    for block in result.data:
        assert block["url_original"] == test_file_key, (
            f"Block {block['iso_code']} url_original mismatch: "
            f"expected '{test_file_key}', got '{block['url_original']}'"
        )

    # Cleanup
    _cleanup_test_blocks(supabase_client)
    supabase_client.storage.from_(bucket_name).remove([test_file_key])


def test_confirm_upload_invalid_payload_still_returns_422():
    """
    T-029-BACK No-Regression Test 9:
    Invalid payload (missing required fields) should still return 422.
    This ensures T-029-BACK changes don't break existing validation.
    """
    # Missing file_key
    payload = {
        "file_id": "550e8400-e29b-41d4-a716-446655440000"
    }

    response = client.post("/api/upload/confirm", json=payload)
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_confirm_upload_file_not_found_returns_404_no_block(supabase_client):
    """
    T-029-BACK Integration Test 4:
    When file doesn't exist in S3, no block should be created.

    Given: A file_key that doesn't exist in storage
    When: POST /api/upload/confirm
    Then:
        - Response 404
        - NO block record created in blocks table
    """
    file_id = "029edead-beef-4444-a716-000000000000"
    payload = {
        "file_id": file_id,
        "file_key": "non-existent/t029-phantom.3dm"
    }

    # Count blocks before (test fixture blocks)
    result_before = supabase_client.table("blocks").select(
        "id", count="exact"
    ).in_("iso_code", EXPECTED_ISO_CODES).execute()
    count_before = result_before.count or 0

    # Act
    response = client.post("/api/upload/confirm", json=payload)

    # Assert: 404 and no new block
    assert response.status_code == 404

    result_after = supabase_client.table("blocks").select(
        "id", count="exact"
    ).in_("iso_code", EXPECTED_ISO_CODES).execute()
    count_after = result_after.count or 0

    assert count_after == count_before, (
        "No block should be created when file is not found in storage"
    )
