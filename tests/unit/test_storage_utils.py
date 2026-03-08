"""
Unit tests for backend.utils.storage module (T-1502-INFRA).

This test suite validates the storage path generation logic for Supabase Storage,
ensuring unique paths, collision prevention, and format compliance.

TDD Phase: RED - All tests defined, function not yet implemented.
Expected Result: 0/12 tests passing (NotImplementedError)
"""

import pytest
from uuid import UUID
from datetime import datetime, timezone, timedelta
from utils.storage import generate_glb_storage_path


class TestGenerateGlbStoragePath:
    """Test suite for generate_glb_storage_path() function."""

    # ===== Happy Path Tests =====

    def test_valid_uuid_and_timestamp_generates_correct_path(self):
        """Test 1: Standard input generates expected path format."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path = generate_glb_storage_path(block_id, timestamp)

        expected = "models/low-poly/550e8400-e29b-41d4-a716-446655440000_2026-03-06T15:30:45Z.glb"
        assert path == expected

    def test_path_has_no_leading_slash(self):
        """Test 2: Path is relative (no leading slash for Supabase Storage)."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path = generate_glb_storage_path(block_id, timestamp)

        assert not path.startswith("/"), "Path must not start with /"

    def test_timestamp_defaults_to_current_utc(self):
        """Test 3: When timestamp is None, uses current UTC time."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        before = datetime.now(timezone.utc).replace(microsecond=0)

        path = generate_glb_storage_path(block_id)  # No timestamp

        after = datetime.now(timezone.utc).replace(microsecond=0)

        # Extract timestamp from path (format: ..._YYYY-MM-DDTHH:MM:SSZ.glb)
        timestamp_str = path.split("_")[1].replace(".glb", "")
        path_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

        # Verify it's within 2 seconds of current time (test execution tolerance)
        assert before <= path_timestamp <= after + timedelta(seconds=2)

    def test_idempotency_same_inputs_same_output(self):
        """Test 4: Same inputs always produce same output."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path1 = generate_glb_storage_path(block_id, timestamp)
        path2 = generate_glb_storage_path(block_id, timestamp)

        assert path1 == path2

    # ===== Edge Case Tests =====

    def test_different_timestamps_different_paths(self):
        """Test 5: Different timestamps prevent path collision."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp1 = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)
        timestamp2 = datetime(2026, 3, 6, 15, 30, 46, tzinfo=timezone.utc)

        path1 = generate_glb_storage_path(block_id, timestamp1)
        path2 = generate_glb_storage_path(block_id, timestamp2)

        assert path1 != path2

    def test_uppercase_uuid_converts_to_lowercase(self):
        """Test 6: UUID uppercase letters are converted to lowercase."""
        block_id = UUID("550E8400-E29B-41D4-A716-446655440000")  # Uppercase
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path = generate_glb_storage_path(block_id, timestamp)

        assert "550e8400-e29b-41d4-a716-446655440000" in path

    def test_non_utc_timezone_converts_to_utc(self):
        """Test 7: Non-UTC timezone is converted to UTC."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        pst = timezone(timedelta(hours=-8))
        timestamp_pst = datetime(2026, 3, 6, 7, 30, 45, tzinfo=pst)  # 7:30 AM PST

        path = generate_glb_storage_path(block_id, timestamp_pst)

        # 7:30 AM PST = 15:30 UTC
        assert "_2026-03-06T15:30:45Z.glb" in path

    # ===== Error Handling Tests =====

    def test_invalid_block_id_type_raises_valueerror(self):
        """Test 8: Non-UUID type raises ValueError."""
        block_id = "550e8400-e29b-41d4-a716-446655440000"  # String, not UUID
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="UUID instance"):
            generate_glb_storage_path(block_id, timestamp)

    def test_naive_datetime_raises_valueerror(self):
        """Test 9: Naive datetime (no timezone) raises ValueError."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45)  # No tzinfo

        with pytest.raises(ValueError, match="timezone-aware"):
            generate_glb_storage_path(block_id, timestamp)

    def test_iso8601_format_uses_z_suffix(self):
        """Test 10: Timestamp uses 'Z' suffix (not '+00:00')."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path = generate_glb_storage_path(block_id, timestamp)

        assert path.endswith("Z.glb"), "Timestamp must use 'Z' suffix"

    # ===== Integration Tests =====

    @pytest.mark.integration
    @pytest.mark.skip(reason="Integration test: requires live Supabase connection")
    def test_path_valid_for_supabase_storage(self):
        """Test 11: Path format accepted by Supabase Storage."""
        # This test will be implemented after GREEN phase
        # Requires: Upload file to real Supabase Storage
        pass

    @pytest.mark.integration
    def test_format_matches_agent_compatibility(self):
        """Test 12: Path format compatible with agent expectations."""
        block_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        timestamp = datetime(2026, 3, 6, 15, 30, 45, tzinfo=timezone.utc)

        path = generate_glb_storage_path(block_id, timestamp)

        # Agent expects: "models/low-poly/" prefix (not "low-poly/" alone)
        assert path.startswith("models/low-poly/")
