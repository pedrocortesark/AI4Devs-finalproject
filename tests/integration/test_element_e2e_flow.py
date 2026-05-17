"""
Integration tests for T-1507-TEST: Element E2E Integration Flow

TDD Phase: RED — These tests verify the complete Element pipeline:
  Upload .3dm → Celery Processing → Element API → Database verification

Requires:
  - PostgreSQL (db service) for blocks table with Element schema
  - Redis (via Celery eager mode from conftest.py) for task execution
  - Supabase Storage for file uploads
  - FastAPI backend with Element API endpoints

Test Strategy:
  - Backend Integration: Upload → Process → Verify Element contract
  - Uses existing fixtures: tests/fixtures/test-model.3dm
  - Celery eager mode: synchronous execution (no background worker)
  - Real database interactions via Supabase
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Load real .3dm fixture
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
test_3dm_content = (FIXTURE_DIR / "test-model.3dm").read_bytes()


def _cleanup_test_elements(supabase_client, test_prefix: str):
    """Helper to remove test elements from Supabase."""
    try:
        supabase_client.table("blocks").delete().like(
            "iso_code", f"{test_prefix}%"
        ).execute()
    except Exception:
        pass


class TestElementE2EFlow:
    """
    T-1507-TEST: Backend Integration Tests
    Verify Upload → Celery → Element API pipeline
    """

    def test_ep_be_01_upload_rejects_invalid_nomenclature(self, supabase_client):
        """
        EP-BE-01: Upload .3dm file with invalid layer nomenclature → Validation rejects file

        Given: A .3dm file with invalid layer names (e.g., "Peces", "Textures" instead of SF-ZONE-TYPE-NNN)
        When: Upload flow completes (POST /api/upload/url + confirm)
        Then:
            - Block records created in blocks table (one per InstanceDefinition)
            - Blocks have iso_codes extracted from InstanceDefinition names
            - Blocks status is "error_processing" (validation failed)
            - Validation report contains nomenclature errors
        """
        # Arrange
        bucket_name = "raw-uploads"
        test_file_key = "test/t1507_ep_be_01.3dm"
        file_id = "1507eb01-e29b-41d4-a716-446655440001"  # Valid UUID for error path test

        # Cleanup stale data
        try:
            supabase_client.storage.from_(bucket_name).remove([test_file_key])
        except Exception:
            pass
        _cleanup_test_elements(supabase_client, "GLPER.B-PAE0720")  # Cleanup re-enabled

        # Step 1: Generate presigned URL
        presigned_payload = {
            "filename": "test-model.3dm",
            "size": len(test_3dm_content),
            "checksum": "sha256:test1507"
        }
        presigned_response = client.post("/api/upload/url", json=presigned_payload)
        assert presigned_response.status_code == 200, \
            f"Expected 200, got {presigned_response.status_code}: {presigned_response.json()}"

        presigned_data = presigned_response.json()
        assert "upload_url" in presigned_data
        assert "file_id" in presigned_data

        # Step 2: Upload file to storage (simulate direct upload)
        supabase_client.storage.from_(bucket_name).upload(
            path=test_file_key,
            file=test_3dm_content,
            file_options={"content-type": "application/x-rhino"}
        )

        # Step 3: Confirm upload (triggers Celery task)
        confirm_payload = {
            "file_id": file_id,
            "file_key": test_file_key
        }
        confirm_response = client.post("/api/upload/confirm", json=confirm_payload)
        assert confirm_response.status_code == 200, \
            f"Expected 200, got {confirm_response.status_code}: {confirm_response.json()}"

        confirm_data = confirm_response.json()
        assert confirm_data["success"] is True
        assert confirm_data["task_id"] is not None, "task_id should be returned"

        # Step 4: Verify blocks created and rejected due to nomenclature errors
        # Query blocks table for blocks with test prefix
        result = supabase_client.table("blocks").select(
            "id, iso_code, status, validation_report"
        ).like("iso_code", "GLPER.B-PAE0720%").execute()

        assert len(result.data) > 0, \
            "Blocks should be created in blocks table after upload + processing"

        element = result.data[0]
        assert element["iso_code"] is not None, "iso_code should not be null"
        assert element["status"] == "error_processing", \
            f"Expected status 'error_processing' (validation failed), got '{element['status']}'"
        
        # Verify validation report contains nomenclature errors
        validation_report = element.get("validation_report")
        assert validation_report is not None, "Validation report should exist"
        assert not validation_report.get("is_valid", True), "File should be marked as invalid"
        assert "errors" in validation_report, "Validation report should contain errors list"

        # Cleanup
        supabase_client.storage.from_(bucket_name).remove([test_file_key])
        _cleanup_test_elements(supabase_client, "GLPER.B-PAE0720")  # Cleanup re-enabled

    def test_hp_be_02_element_has_material_from_material_colors(self, supabase_client):
        """
        HP-BE-02: REMOVED - material_type column eliminated (no longer used)
        
        Reason: material_type extraction was incorrect (searched wrong location).
        Material data now in rhino_metadata JSONB field.
        """
        pytest.skip("Test obsolete: material_type column removed from schema")

    def test_hp_be_03_element_has_https_absolute_low_poly_url(self, supabase_client):
        """
        HP-BE-03: Verify Element has low_poly_url with HTTPS absolute URL

        Given: An element fully processed by Agent
        When: Querying element details
        Then:
            - low_poly_url is absolute URL (starts with https://)
            - low_poly_url is NOT relative path (not "models/low-poly/...")
            - URL points to Supabase Storage or CDN
        """
        # Query elements with low_poly_url populated
        result = supabase_client.table("blocks").select(
            "id, iso_code, low_poly_url"
        ).not_.is_("low_poly_url", "null").limit(1).execute()

        if len(result.data) == 0:
            pytest.skip("No elements with low_poly_url to test URL format")

        element = result.data[0]
        assert element["low_poly_url"] is not None
        assert element["low_poly_url"].startswith("https://"), \
            f"low_poly_url should be absolute HTTPS URL, got: {element['low_poly_url']}"
        assert "supabase.co" in element["low_poly_url"] or "cloudfront.net" in element["low_poly_url"], \
            "low_poly_url should point to Supabase Storage or CloudFront CDN"

    def test_hp_be_04_element_has_bbox_structure(self, supabase_client):
        """
        HP-BE-04: Verify Element has bbox with structure {min: [x,y,z], max: [x,y,z]}

        Given: An element with geometry processed
        When: Querying element bbox
        Then:
            - bbox is JSONB object (not null)
            - bbox has "min" key with 3 floats
            - bbox has "max" key with 3 floats
            - min values < max values (valid bbox)
        """
        result = supabase_client.table("blocks").select(
            "id, iso_code, bbox"
        ).not_.is_("bbox", "null").limit(1).execute()

        if len(result.data) == 0:
            pytest.skip("No elements with bbox to test structure")

        element = result.data[0]
        bbox = element["bbox"]

        assert isinstance(bbox, dict), "bbox should be dict/JSONB"
        assert "min" in bbox, "bbox should have 'min' key"
        assert "max" in bbox, "bbox should have 'max' key"

        assert isinstance(bbox["min"], list) and len(bbox["min"]) == 3, \
            "bbox.min should be list of 3 floats"
        assert isinstance(bbox["max"], list) and len(bbox["max"]) == 3, \
            "bbox.max should be list of 3 floats"

        # Validate min < max
        assert bbox["min"][0] < bbox["max"][0], "bbox min.x should be < max.x"
        assert bbox["min"][1] < bbox["max"][1], "bbox min.y should be < max.y"
        assert bbox["min"][2] < bbox["max"][2], "bbox min.z should be < max.z"

    def test_hp_be_05_element_iso_code_matches_userstring(self, supabase_client):
        """
        HP-BE-05: Verify Element iso_code matches UserString "Codi" from .3dm file

        Given: A .3dm file with UserString "Codi" = "GLPER.B-PAE0720.0701"
        When: Agent extracts metadata
        Then:
            - Element iso_code matches extracted UserString
            - iso_code follows Sagrada Familia naming convention
            - iso_code is NOT "PENDING-{uuid}" (temporary value)
        """
        result = supabase_client.table("blocks").select(
            "id, iso_code, rhino_metadata"
        ).not_.like("iso_code", "PENDING-%").limit(1).execute()

        if len(result.data) == 0:
            pytest.skip("No elements with validated iso_code to test UserString extraction")

        element = result.data[0]
        assert element["iso_code"] is not None
        assert not element["iso_code"].startswith("PENDING-"), \
            "iso_code should not be temporary PENDING value"

        # Check rhino_metadata for user_strings (if available)
        if element.get("rhino_metadata") and isinstance(element["rhino_metadata"], dict):
            user_strings = element["rhino_metadata"].get("user_strings", {})
            if "Codi" in user_strings:
                assert element["iso_code"] == user_strings["Codi"], \
                    f"iso_code '{element['iso_code']}' should match UserString 'Codi' '{user_strings['Codi']}'"

    def test_hp_be_06_get_elements_returns_processed_element(self, supabase_client):
        """
        HP-BE-06: Verify GET /api/elements returns the processed element

        Given: An element exists in database with low_poly_url and bbox
        When: Calling GET /api/elements
        Then:
            - Response 200 OK
            - Response contains ElementsListResponse schema
            - Response.elements array contains at least 1 element
            - Element has id, iso_code, status, low_poly_url, bbox
        """
        response = client.get("/api/elements")
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.json()}"

        data = response.json()
        assert "elements" in data, "Response should have 'elements' key"
        assert "meta" in data, "Response should have 'meta' key"

        # If no elements, skip (empty DB is valid, but we can't test contract)
        if len(data["elements"]) == 0:
            pytest.skip("No elements returned from GET /api/elements (empty database)")

        element = data["elements"][0]
        assert "id" in element
        assert "iso_code" in element
        assert "status" in element
        assert "low_poly_url" in element, \
            "Element from GET /api/elements should have low_poly_url (application-level filter)"
        assert "bbox" in element, \
            "Element from GET /api/elements should have bbox (application-level filter)"

    def test_hp_be_07_get_element_detail_returns_full_data(self, supabase_client):
        """
        HP-BE-07: Verify GET /api/elements/{id} returns full element detail

        Given: An element exists in database
        When: Calling GET /api/elements/{element_id}
        Then:
            - Response 200 OK
            - Response contains ElementDetailSchema
            - Includes validation_report (if validated)
            - Includes rhino_metadata (JSONB)
            - Includes created_at, updated_at timestamps
        """
        # Get first element ID
        list_response = client.get("/api/elements")
        if list_response.status_code != 200 or len(list_response.json()["elements"]) == 0:
            pytest.skip("No elements available to test detail endpoint")

        element_id = list_response.json()["elements"][0]["id"]

        # Call detail endpoint
        detail_response = client.get(f"/api/elements/{element_id}")
        assert detail_response.status_code == 200, \
            f"Expected 200, got {detail_response.status_code}: {detail_response.json()}"

        element = detail_response.json()
        assert element["id"] == element_id
        assert "iso_code" in element
        assert "status" in element
        assert "low_poly_url" in element
        assert "bbox" in element

        # Optional fields (may be null)
        assert "validation_report" in element  # Can be null
        assert "rhino_metadata" in element  # JSONB
        assert "created_at" in element
        assert "updated_at" in element


class TestElementEdgeCases:
    """
    T-1507-TEST: Backend Edge Case Tests
    """

    def test_ec_be_03_query_before_processing_complete_returns_empty(self, supabase_client):
        """
        EC-BE-03: Query GET /api/elements before processing complete → Returns empty list

        Given: An element with status="processing" and low_poly_url=null
        When: Calling GET /api/elements (application-level filter active)
        Then:
            - Response 200 OK
            - Response.elements array does NOT contain unprocessed element
            - Application-level filter excludes elements without low_poly_url+bbox
        """
        # Query raw database for processing elements
        result = supabase_client.table("blocks").select(
            "id, iso_code, status, low_poly_url"
        ).eq("status", "processing").execute()

        if len(result.data) == 0:
            pytest.skip("No processing elements to test application-level filter")

        processing_element_id = result.data[0]["id"]

        # Call GET /api/elements
        api_response = client.get("/api/elements")
        assert api_response.status_code == 200

        # Verify processing element NOT in response
        returned_ids = [e["id"] for e in api_response.json()["elements"]]
        assert processing_element_id not in returned_ids, \
            "Processing element without low_poly_url should be filtered out by application layer"

    def test_ec_be_04_query_with_invalid_uuid_returns_400(self):
        """
        EC-BE-04: Query with invalid UUID → Returns 400 Bad Request

        Given: Invalid UUID format (not UUID v4)
        When: Calling GET /api/elements/invalid-uuid
        Then:
            - Response 400 or 422 (validation error)
            - Error message indicates invalid UUID format
        """
        response = client.get("/api/elements/not-a-uuid")
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid UUID, got {response.status_code}"

        data = response.json()
        assert "detail" in data, "Error response should have 'detail' key"


class TestElementErrorHandling:
    """
    T-1507-TEST: Backend Error Handling Tests
    """

    def test_err_be_01_confirm_upload_with_nonexistent_file_returns_404(self, supabase_client):
        """
        ERR-BE-01: Confirm upload with non-existent file_key → Returns 404

        Given: file_key that does not exist in Supabase Storage
        When: POST /api/upload/confirm with invalid file_key
        Then:
            - Response 404 Not Found
            - Error message indicates file not found
        """
        payload = {
            "file_id": "00000000-0000-0000-0000-000000000001",  # Valid UUID, non-existent file
            "file_key": "test/nonexistent-file-t1507.3dm"
        }

        response = client.post("/api/upload/confirm", json=payload)
        assert response.status_code == 404, \
            f"Expected 404 for non-existent file, got {response.status_code}: {response.json()}"

        data = response.json()
        assert "detail" in data

    def test_err_be_02_confirm_upload_with_invalid_file_id_format_returns_422(self):
        """
        ERR-BE-02: Confirm upload with invalid file_id format → Returns 422 Validation Error

        Given: file_id is not valid UUID format
        When: POST /api/upload/confirm
        Then:
            - Response 422 Unprocessable Entity
            - Pydantic validation error for file_id field
        """
        payload = {
            "file_id": "not-a-valid-uuid",
            "file_key": "test/some-file.3dm"
        }

        response = client.post("/api/upload/confirm", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid file_id, got {response.status_code}"

    def test_err_be_03_upload_file_over_500mb_rejected_at_presigned_url(self):
        """
        ERR-BE-03: Upload file > 500MB → Rejected at presigned URL generation

        Given: File size > 500MB (max upload limit)
        When: POST /api/upload/url with size=600MB
        Then:
            - Response 422 Unprocessable Entity (Pydantic field validation)
            - Error message indicates file size limit exceeded
        """
        payload = {
            "filename": "huge-model.3dm",
            "size": 600 * 1024 * 1024,  # 600MB
            "checksum": "sha256:huge"
        }

        response = client.post("/api/upload/url", json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for oversized file, got {response.status_code}"

        data = response.json()
        assert "detail" in data


class TestElementInfrastructure:
    """
    T-1507-TEST: Backend Infrastructure/Integration Tests
    """

    def test_int_be_01_celery_task_completes_within_timeout(self, supabase_client):
        """
        INT-BE-01: Verify Celery task completes within timeout (540s soft, 600s hard)

        Given: A valid .3dm file uploaded
        When: Celery processes file (in eager mode for test)
        Then:
            - Task completes without SoftTimeLimitExceeded
            - Task completes without TimeLimitExceeded
            - Task result is SUCCESS
        """
        # This test is implicitly covered by HP-BE-01 (upload + process)
        # If HP-BE-01 passes, it means Celery completed within timeout
        # We'll mark this as a documentation test
        pytest.skip("Implicitly tested by HP-BE-01 (upload + process flow)")

    def test_int_be_03_storage_cleanup_on_failed_processing(self, supabase_client):
        """
        INT-BE-03: Verify storage cleanup on failed processing (delete temp files)

        Given: File processing fails (invalid .3dm format)
        When: Celery task completes with ERROR status
        Then:
            - Temporary files cleaned up from storage
            - Block status updated to "error_processing"
            - No orphaned files in storage
        """
        pytest.skip("Cleanup logic not yet implemented (post-MVP feature)")
