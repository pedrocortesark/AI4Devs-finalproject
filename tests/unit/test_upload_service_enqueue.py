"""
Unit tests for UploadService enqueue flow.

Tests for UploadService.enqueue_register_blocks() and confirm_upload() after
the architecture change from "one PENDING block per upload" to
"N blocks per upload via register_3dm_blocks task".

Tests:
  1. enqueue_register_blocks sends celery task and returns task_id
  2. enqueue_register_blocks raises if no celery client provided
  3. confirm_upload returns 4-tuple with task_id (not None)
  4. confirm_upload does NOT enqueue if file not found
  5. confirm_upload does NOT enqueue if event creation fails
"""

import pytest
from unittest.mock import MagicMock

from services import UploadService
from constants import TASK_REGISTER_3DM_BLOCKS


# --- Fixtures ---

@pytest.fixture
def mock_supabase():
    """Mock Supabase client with fluent API."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_celery():
    """Mock Celery client with send_task."""
    client = MagicMock()
    mock_result = MagicMock()
    mock_result.id = "celery-task-uuid-123"
    client.send_task.return_value = mock_result
    return client


@pytest.fixture
def upload_service(mock_supabase, mock_celery):
    """UploadService with both supabase and celery clients injected."""
    return UploadService(mock_supabase, celery_client=mock_celery)


@pytest.fixture
def upload_service_no_celery(mock_supabase):
    """UploadService without celery client (legacy behavior)."""
    return UploadService(mock_supabase)


# --- Test: enqueue_register_blocks ---

class TestEnqueueRegisterBlocks:
    """Tests for UploadService.enqueue_register_blocks()."""

    def test_sends_celery_task_and_returns_task_id(self, upload_service, mock_celery):
        """
        enqueue_register_blocks() should call celery.send_task() with the
        register_3dm_blocks task name and file_key as sole argument,
        and return the task ID.
        """
        file_key = "uploads/550e8400/model.3dm"

        # Act
        task_id = upload_service.enqueue_register_blocks(file_key)

        # Assert
        assert task_id == "celery-task-uuid-123"
        mock_celery.send_task.assert_called_once_with(
            TASK_REGISTER_3DM_BLOCKS,
            args=[file_key]
        )

    def test_raises_if_no_celery_client(self, upload_service_no_celery):
        """
        enqueue_register_blocks() should raise if celery client not configured.
        """
        with pytest.raises(RuntimeError):
            upload_service_no_celery.enqueue_register_blocks("uploads/x/model.3dm")


# --- Test: confirm_upload (modified flow) ---

class TestConfirmUploadWithEnqueue:
    """Tests for the confirm_upload() flow: verify → magic bytes → event → enqueue."""

    def test_returns_4_tuple_with_task_id(self, upload_service, mock_supabase):
        """
        confirm_upload() should return (success, event_id, task_id, error).
        task_id should NOT be None when the full flow succeeds.
        """
        # Arrange: file exists in storage
        mock_supabase.storage.from_.return_value.list.return_value = [
            {"name": "model.3dm"}
        ]
        # Arrange: event creation succeeds
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "event-uuid-123"}
        ]

        # Act
        result = upload_service.confirm_upload(
            file_id="550e8400-e29b-41d4-a716-446655440000",
            file_key="uploads/550e8400/model.3dm"
        )

        # Assert: 4-tuple with non-None task_id
        assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple"
        success, event_id, task_id, error = result
        assert success is True
        assert event_id is not None
        assert task_id is not None
        assert error is None

    def test_no_block_or_task_when_file_not_found(self, upload_service, mock_supabase):
        """
        When file_key doesn't exist in storage, the flow fails immediately.
        No event and no task should be created.
        """
        # Arrange: file NOT found
        mock_supabase.storage.from_.return_value.list.return_value = []

        # Act
        result = upload_service.confirm_upload(
            file_id="999e8400-e29b-41d4-a716-000000000999",
            file_key="non-existent/fake-file.3dm"
        )

        # Assert
        success, event_id, task_id, error = result
        assert success is False
        assert task_id is None

    def test_no_task_when_event_creation_fails(self, upload_service, mock_supabase):
        """
        If event creation fails, no task should be enqueued.
        """
        # Arrange: file exists
        mock_supabase.storage.from_.return_value.list.return_value = [
            {"name": "model.3dm"}
        ]
        # Arrange: event creation fails
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
            "Event table error"
        )

        # Act
        result = upload_service.confirm_upload(
            file_id="550e8400-e29b-41d4-a716-446655440000",
            file_key="uploads/550e8400/model.3dm"
        )

        # Assert: should fail gracefully
        success, _event_id, task_id, _error = result
        assert success is False
        assert task_id is None
