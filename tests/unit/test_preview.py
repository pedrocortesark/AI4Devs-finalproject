"""
Unit tests for POST /api/upload/preview endpoint.

Tests:
  1. Valid block (ISO ok, has metadata, not duplicate) → valid_blocks=1
  2. Duplicate block (already in DB) → duplicate_blocks=1, valid_blocks=0
  3. Invalid ISO name → iso_valid=False, invalid_blocks=1
  4. Block with no UserStrings → has_metadata=False, invalid_blocks=1
  5. rhino3dm unavailable (None) → HTTP 500
  6. Corrupt file (File3dm.Read returns None) → HTTP 422
  7. Ingestion status — pending task → ready=False
  8. Ingestion status — successful task → ready=True, registered/skipped populated
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_mock_idef(name: str, idef_id: str = "aaaabbbb-0000-0000-0000-000000000001"):
    idef = MagicMock()
    idef.Name = name
    idef.Id = idef_id
    return idef


def _make_mock_iref_obj(idef_id: str, user_strings: list[tuple]):
    """Create a mock scene object that is an InstanceReference."""
    import rhino3dm as rh
    obj = MagicMock()
    obj.Geometry.ObjectType = rh.ObjectType.InstanceReference
    obj.Geometry.ParentIdefId = idef_id
    # GetUserStrings returns a tuple of (key, value) pairs
    obj.Attributes.GetUserStrings.return_value = tuple(user_strings)
    return obj


@pytest.fixture
def rhino_file_with_valid_block():
    """Mock rhino3dm File3dm with one valid InstanceDefinition."""
    idef_id = "aaaabbbb-0000-0000-0000-000000000001"
    idef = _make_mock_idef("SF-NAV-CO-001", idef_id)
    iref_obj = _make_mock_iref_obj(
        idef_id,
        [("Codi", "SF-NAV-CO-001"), ("Material", "Montjuïc"), ("Tipologia", "Column")],
    )
    mock_file = MagicMock()
    mock_file.InstanceDefinitions = [idef]
    mock_file.Objects = [iref_obj]
    return mock_file


@pytest.fixture
def supabase_no_existing(monkeypatch):
    """Mock Supabase client that returns no existing blocks."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    monkeypatch.setattr("api.preview.get_supabase_client", lambda: mock_sb)
    return mock_sb


@pytest.fixture
def supabase_block_exists(monkeypatch):
    """Mock Supabase client that returns one existing block (duplicate)."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "existing-uuid"}
    ]
    monkeypatch.setattr("api.preview.get_supabase_client", lambda: mock_sb)
    return mock_sb


def _make_test_client():
    from main import app
    return TestClient(app)


def _upload_dummy_file(client, tmp_path, filename: str = "model.3dm"):
    """Helper: POST a fake file to /api/upload/preview."""
    fake = tmp_path / filename
    fake.write_bytes(b"fake rhino content")
    with open(fake, "rb") as f:
        return client.post(
            "/api/upload/preview",
            files={"file": (filename, f, "application/octet-stream")},
        )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPreviewEndpoint:
    def test_valid_block(self, monkeypatch, tmp_path, rhino_file_with_valid_block, supabase_no_existing):
        """Happy path: valid ISO + metadata + not duplicate → valid_blocks=1."""
        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: rhino_file_with_valid_block)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_blocks"] == 1
        assert data["valid_blocks"] == 1
        assert data["duplicate_blocks"] == 0
        assert data["invalid_blocks"] == 0
        block = data["blocks"][0]
        assert block["name"] == "SF-NAV-CO-001"
        assert block["iso_valid"] is True
        assert block["has_metadata"] is True
        assert block["is_instance_object"] is True
        assert block["already_exists"] is False
        assert block["codi"] == "SF-NAV-CO-001"
        assert block["material"] == "Montjuïc"

    def test_duplicate_block(self, monkeypatch, tmp_path, rhino_file_with_valid_block, supabase_block_exists):
        """Block already in DB → appears as duplicate, not valid."""
        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: rhino_file_with_valid_block)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid_blocks"] == 0
        assert data["duplicate_blocks"] == 1
        assert data["blocks"][0]["already_exists"] is True

    def test_invalid_iso_name(self, monkeypatch, tmp_path, supabase_no_existing):
        """Block name does not match ISO pattern → iso_valid=False."""
        idef_id = "aaaabbbb-0000-0000-0000-000000000002"
        idef = _make_mock_idef("invalid_block_name", idef_id)
        iref_obj = _make_mock_iref_obj(
            idef_id, [("Codi", "invalid_block_name"), ("Material", "Montjuïc")]
        )
        mock_file = MagicMock()
        mock_file.InstanceDefinitions = [idef]
        mock_file.Objects = [iref_obj]

        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: mock_file)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid_blocks"] == 0
        assert data["invalid_blocks"] == 1
        block = data["blocks"][0]
        assert block["iso_valid"] is False
        assert len(block["iso_issues"]) > 0

    def test_no_user_strings(self, monkeypatch, tmp_path, supabase_no_existing):
        """Block has no UserStrings → has_metadata=False."""
        idef_id = "aaaabbbb-0000-0000-0000-000000000003"
        idef = _make_mock_idef("SF-NAV-CO-002", idef_id)
        iref_obj = _make_mock_iref_obj(idef_id, [])  # empty user strings
        mock_file = MagicMock()
        mock_file.InstanceDefinitions = [idef]
        mock_file.Objects = [iref_obj]

        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: mock_file)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["blocks"][0]["has_metadata"] is False
        assert data["blocks"][0]["codi"] is None
        assert data["valid_blocks"] == 0

    def test_no_instance_object(self, monkeypatch, tmp_path, supabase_no_existing):
        """InstanceDefinition with 0 references → is_instance_object=False."""
        idef = _make_mock_idef("SF-NAV-CO-003")
        mock_file = MagicMock()
        mock_file.InstanceDefinitions = [idef]
        mock_file.Objects = []  # no objects in scene

        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: mock_file)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["blocks"][0]["is_instance_object"] is False

    def test_corrupt_file_returns_422(self, monkeypatch, tmp_path, supabase_no_existing):
        """File3dm.Read returns None → 422 Unprocessable Entity."""
        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: None)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 422

    def test_rhino3dm_unavailable_returns_500(self, monkeypatch, tmp_path):
        """rhino3dm is None (not installed) → 500."""
        monkeypatch.setattr("api.preview.rhino3dm", None)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 500

    def test_empty_3dm_no_idefs(self, monkeypatch, tmp_path, supabase_no_existing):
        """File with no InstanceDefinitions → total_blocks=0, valid_blocks=0."""
        mock_file = MagicMock()
        mock_file.InstanceDefinitions = []
        mock_file.Objects = []

        monkeypatch.setattr("api.preview.rhino3dm.File3dm.Read", lambda _: mock_file)
        client = _make_test_client()
        resp = _upload_dummy_file(client, tmp_path)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_blocks"] == 0
        assert data["valid_blocks"] == 0


class TestIngestionStatusEndpoint:
    def test_pending_task(self, monkeypatch):
        """Task not yet ready → ready=False, no counts."""
        mock_result = MagicMock()
        mock_result.ready.return_value = False
        mock_result.successful.return_value = False

        def mock_async_result(task_id, app):
            return mock_result

        monkeypatch.setattr("api.upload.AsyncResult", mock_async_result)
        client = _make_test_client()
        resp = client.get("/api/upload/ingestion-status/fake-task-id")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is False
        assert data["registered"] is None

    def test_successful_task(self, monkeypatch):
        """Completed task → ready=True, registered and skipped populated."""
        mock_result = MagicMock()
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"registered": 5, "skipped": 2, "block_ids": ["id1", "id2"]}

        def mock_async_result(task_id, app):
            return mock_result

        monkeypatch.setattr("api.upload.AsyncResult", mock_async_result)
        client = _make_test_client()
        resp = client.get("/api/upload/ingestion-status/fake-task-id")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["registered"] == 5
        assert data["skipped"] == 2
        assert "id1" in data["block_ids"]

    def test_failed_task(self, monkeypatch):
        """Failed task → ready=True, error populated."""
        mock_result = MagicMock()
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = Exception("Something went wrong\nLine 2")

        def mock_async_result(task_id, app):
            return mock_result

        monkeypatch.setattr("api.upload.AsyncResult", mock_async_result)
        client = _make_test_client()
        resp = client.get("/api/upload/ingestion-status/fake-task-id")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["error"] is not None
        assert "\n" not in data["error"]  # Only first line returned
