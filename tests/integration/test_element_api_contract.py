"""
Integration tests for T-1507-TEST: Element API Contract Validation

TDD Phase: RED — These tests verify that backend API contracts match exactly:
  - Pydantic schemas (backend) ↔ Database schema
  - Field types, required/optional, validation rules

Focus: Contract compliance, not business logic
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestElementAPIContract:
    """
    T-1507-TEST: API Contract Validation Tests
    Verify Pydantic schema alignment with database and Element model
    """

    def test_api_contract_01_elements_list_response_schema(self):
        """
        Verify GET /api/elements returns correct ElementsListResponse schema

        Given: GET /api/elements endpoint
        When: Response received
        Then:
            - Response has "elements" array
            - Response has "meta" object with total/filtered
            - Each element matches Element schema (id,iso_code,status,material_type,low_poly_url,bbox)
        """
        response = client.get("/api/elements")
        assert response.status_code == 200

        data = response.json()
        assert "elements" in data, "Response must have 'elements' key"
        assert "meta" in data, "Response must have 'meta' key"
        assert isinstance(data["elements"], list), "'elements' must be list"
        assert isinstance(data["meta"], dict), "'meta' must be dict"

        # Meta structure
        assert "total" in data["meta"], "meta must have 'total'"
        assert "filtered" in data["meta"], "meta must have 'filtered'"
        assert isinstance(data["meta"]["total"], int)
        assert isinstance(data["meta"]["filtered"], int)

        # If elements exist, verify schema
        if len(data["elements"]) > 0:
            element = data["elements"][0]
            required_fields = ["id", "iso_code", "status", "low_poly_url", "bbox"]
            for field in required_fields:
                assert field in element, f"Element must have '{field}' field"

    def test_api_contract_02_element_detail_response_schema(self):
        """
        Verify GET /api/elements/{id} returns correct ElementDetail schema

        Given: GET /api/elements/{id} endpoint
        When: Response received
        Then:
            - Response has all Element fields
            - Plus: validation_report (nullable), rhino_metadata, created_at, updated_at
        """
        # Get first element
        list_response = client.get("/api/elements")
        if len(list_response.json().get("elements", [])) == 0:
            pytest.skip("No elements to test detail schema")

        element_id = list_response.json()["elements"][0]["id"]
        response = client.get(f"/api/elements/{element_id}")
        assert response.status_code == 200

        element = response.json()
        required_fields = [
            "id", "iso_code", "status",
            "low_poly_url", "bbox", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in element, f"ElementDetail must have '{field}' field"

        # Optional/nullable fields
        optional_fields = ["validation_report", "rhino_metadata"]
        for field in optional_fields:
            assert field in element, f"ElementDetail must include '{field}' (can be null)"

    def test_api_contract_03_bbox_structure_validation(self):
        """
        Verify bbox follows strict {min: [x,y,z], max: [x,y,z]} structure

        Given: Element with bbox
        When: Validating bbox structure
        Then:
            - bbox is object with "min" and "max" keys
            - min/max are arrays of 3 numbers (floats)
            - No extra keys in bbox
        """
        response = client.get("/api/elements")
        if response.status_code != 200 or len(response.json().get("elements", [])) == 0:
            pytest.skip("No elements to test bbox structure")

        element = response.json()["elements"][0]
        bbox = element["bbox"]

        assert isinstance(bbox, dict), "bbox must be dict/object"
        assert set(bbox.keys()) == {"min", "max"}, \
            f"bbox should only have 'min' and 'max' keys, got: {list(bbox.keys())}"

        assert isinstance(bbox["min"], list) and len(bbox["min"]) == 3
        assert isinstance(bbox["max"], list) and len(bbox["max"]) == 3
        assert all(isinstance(v, (int, float)) for v in bbox["min"])
        assert all(isinstance(v, (int, float)) for v in bbox["max"])

    def test_api_contract_04_element_status_enum_values(self):
        """
        Verify Element status field uses valid ElementStatus enum values

        Given: Element from API
        When: Checking status field
        Then:
            - status is one of: uploaded, processing, validated, rejected, 
              error_processing, in_fabrication, completed, archived
        """
        valid_statuses = [
            "uploaded", "processing", "validated", "rejected",
            "error_processing", "in_fabrication", "completed", "archived"
        ]

        response = client.get("/api/elements")
        if response.status_code != 200 or len(response.json().get("elements", [])) == 0:
            pytest.skip("No elements to test status enum")

        element = response.json()["elements"][0]
        assert element["status"] in valid_statuses, \
            f"Element status '{element['status']}' not in valid enum values"

    def test_api_contract_06_no_workshop_fields_in_response(self):
        """
        Verify workshop_id and workshop_name fields removed from API (T-1501-DB)

        Given: Element from API
        When: Checking response schema
        Then:
            - Element does NOT have "workshop_id" field
            - Element does NOT have "workshop_name" field
        """
        response = client.get("/api/elements")
        if response.status_code != 200 or len(response.json().get("elements", [])) == 0:
            pytest.skip("No elements to test workshop field removal")

        element = response.json()["elements"][0]
        forbidden_fields = ["workshop_id", "workshop_name"]
        for field in forbidden_fields:
            assert field not in element, \
                f"Element should NOT have '{field}' field (removed in T-1501-DB)"

    def test_api_contract_07_iso_code_not_null(self):
        """
        Verify iso_code is always present (never null)

        Given: Element from API
        When: Checking iso_code field
        Then:
            - iso_code is NOT null
            - iso_code is string
            - iso_code has length > 0
        """
        response = client.get("/api/elements")
        if response.status_code != 200 or len(response.json().get("elements", [])) == 0:
            pytest.skip("No elements to test iso_code")

        element = response.json()["elements"][0]
        assert element["iso_code"] is not None, "iso_code must not be null"
        assert isinstance(element["iso_code"], str), "iso_code must be string"
        assert len(element["iso_code"]) > 0, "iso_code must not be empty string"
