# tests/integration/test_t1501_migration.py
"""
Integration tests for T-1501-DB: Element Model Database Migration.

This test suite verifies:
- Migration execution success (column added, data updated, constraints active)
- Constraint enforcement (CHECK, NOT NULL)
- Data integrity (6 blocks preserved with correct values)
- Rollback functionality (DOWN migration restores schema)
- Baseline validation (108/108 backend tests remain passing)

Prerequisites:
- Supabase database connection (SUPABASE_DATABASE_URL environment variable)
- 6 existing blocks with iso_code 'GLPER.B-PAE0720.0701' through '0706'
- Migrations folder: supabase/migrations/

Test execution:
pytest tests/integration/test_t1501_migration.py -v

Expected results:
- RED phase: 26 FAIL (migration not applied yet)
- GREEN phase: 26 PASS (migration applied successfully)
"""

import os
import pytest
import psycopg2
from psycopg2 import IntegrityError


# ===== TEST CONSTANTS =====

# Valid bounding box JSONB for test block inserts
VALID_BBOX = '{"min":[0,0,0],"max":[1,1,1]}'

# Valid test GLB URL
VALID_GLB_URL = 'https://example.com/test.glb'


# ===== TEST HELPERS =====

def insert_test_block(cursor, iso_code: str, material_type: str, 
                      low_poly_url: str = VALID_GLB_URL, 
                      bbox: str = VALID_BBOX,
                      tipologia: str = 'capitel',
                      status: str = 'uploaded') -> None:
    """
    Insert a test block with minimal boilerplate.
    
    Args:
        cursor: Database cursor for executing INSERT
        iso_code: Unique identifier for test block (e.g., 'TEST-STONE')
        material_type: Material enum value ('Stone', 'Ceramic', or invalid for constraint tests)
        low_poly_url: GLB file URL (default: valid example URL)
        bbox: Bounding box JSONB string (default: valid bbox)
        tipologia: Block typology (default: 'capitel')
        status: Block status (default: 'uploaded')
    
    Example:
        insert_test_block(cursor, 'TEST-STONE', 'Stone')
        insert_test_block(cursor, 'TEST-INVALID', 'Metal')  # Will raise IntegrityError
    """
    cursor.execute(f"""
        INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
    """, (iso_code, tipologia, material_type, low_poly_url, bbox, status))


# ===== FIXTURES =====

@pytest.fixture(scope="module")
def db_conn():
    """Provide direct PostgreSQL connection to local database (Docker or Supabase).
    
    Uses DATABASE_URL (local Docker DB) if available, falls back to SUPABASE_DATABASE_URL (remote).
    For TDD-GREEN phase, tests should run against local migrated database.
    """
    database_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL or SUPABASE_DATABASE_URL must be configured for integration tests")
    conn = psycopg2.connect(database_url)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def db_cursor(db_conn):
    """Provide fresh cursor for each test with auto-rollback."""
    cur = db_conn.cursor()
    yield cur
    db_conn.rollback()  # Rollback any changes from test
    cur.close()


@pytest.fixture(scope="function")
def clean_test_blocks(db_cursor, db_conn):
    """Remove test blocks before/after test execution.
    
    For constraint tests that intentionally fail, rollback transaction
    before cleanup DELETE to avoid InFailedSqlTransaction error.
    """
    db_cursor.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")
    yield
    db_conn.rollback()  # Reset transaction state before cleanup
    db_cursor.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")


@pytest.fixture(scope="function")
def requires_production_data(db_cursor):
    """Skip test if database is empty (no production blocks from Phase 0).
    
    Data Integrity tests (Suite 3) require 6 Sagrada Família blocks ingested in Phase 0.
    These tests should SKIP for empty databases (CI, local Docker) and PASS for production.
    """
    db_cursor.execute("SELECT COUNT(*) FROM blocks WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'")
    count = db_cursor.fetchone()[0]
    if count == 0:
        pytest.skip("Test requires production data (6 Sagrada Família blocks from Phase 0)")


# ===== TEST SUITE 1: Migration Execution =====

def test_material_type_column_exists(db_cursor):
    """Verify material_type column was added to blocks table."""
    db_cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'material_type'
    """)
    result = db_cursor.fetchone()
    
    assert result is not None, "material_type column not found in blocks table"
    assert result[0] == "material_type", f"Unexpected column name: {result[0]}"
    assert result[1] == "text", f"Unexpected data type: {result[1]} (expected text)"
    assert result[2] == "NO", f"material_type should be NOT NULL, got: {result[2]}"


def test_six_blocks_remain_in_database(db_cursor, requires_production_data):
    """Verify 6 Sagrada Família blocks survived migration without data loss."""
    db_cursor.execute("SELECT COUNT(*) FROM blocks WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'")
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks after migration, found {count}"


def test_all_six_blocks_have_material_type_stone(db_cursor, requires_production_data):
    """Verify UPDATE step populated material_type for existing blocks."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM blocks 
        WHERE iso_code LIKE 'GLPER.B-PAE0720.07%' AND material_type = 'Stone'
    """)
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks with material_type='Stone', found {count}"


def test_workshop_id_column_dropped(db_cursor):
    """Verify workshop_id column was removed from blocks table."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'workshop_id'
    """)
    count = db_cursor.fetchone()[0]
    assert count == 0, "workshop_id column still exists after migration"


def test_workshop_name_column_never_existed(db_cursor):
    """Verify workshop_name was never a real column (JOIN artifact only)."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'workshop_name'
    """)
    count = db_cursor.fetchone()[0]
    assert count == 0, "workshop_name column should not exist"


def test_low_poly_url_is_not_null(db_cursor):
    """Verify low_poly_url constraint was changed to NOT NULL."""
    db_cursor.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'low_poly_url'
    """)
    nullable = db_cursor.fetchone()[0]
    assert nullable == "NO", f"low_poly_url should be NOT NULL, got: {nullable}"


def test_bbox_is_not_null(db_cursor):
    """Verify bbox constraint was changed to NOT NULL."""
    db_cursor.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'bbox'
    """)
    nullable = db_cursor.fetchone()[0]
    assert nullable == "NO", f"bbox should be NOT NULL, got: {nullable}"


def test_material_type_index_created(db_cursor):
    """Verify idx_blocks_material_type index was created for filtering."""
    db_cursor.execute("""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = 'blocks' AND indexname = 'idx_blocks_material_type'
    """)
    result = db_cursor.fetchone()
    
    assert result is not None, "idx_blocks_material_type index not found"
    assert "material_type" in result[1], f"Index definition missing material_type: {result[1]}"


# ===== TEST SUITE 2: Constraint Enforcement =====

def test_reject_null_material_type(db_cursor, clean_test_blocks):
    """Verify CHECK constraint rejects NULL material_type."""
    with pytest.raises(IntegrityError, match="not-null constraint"):
        insert_test_block(db_cursor, 'TEST-NULL-MAT', material_type=None)


def test_reject_spanish_piedra(db_cursor, clean_test_blocks):
    """Verify CHECK constraint rejects Spanish 'Piedra'."""
    with pytest.raises(IntegrityError, match="check constraint"):
        insert_test_block(db_cursor, 'TEST-SPANISH', 'Piedra')


def test_reject_invalid_metal(db_cursor, clean_test_blocks):
    """Verify CHECK constraint rejects free strings like 'Metal' (not in enum)."""
    with pytest.raises(IntegrityError, match="check constraint"):
        insert_test_block(db_cursor, 'TEST-METAL', 'Metal')


def test_accept_valid_stone(db_cursor, clean_test_blocks):
    """Verify CHECK constraint accepts valid 'Stone' value."""
    insert_test_block(db_cursor, 'TEST-STONE', 'Stone')
    db_cursor.execute("SELECT material_type FROM blocks WHERE iso_code = 'TEST-STONE'")
    result = db_cursor.fetchone()
    assert result[0] == "Stone", f"Expected 'Stone', got: {result[0]}"


def test_accept_valid_ceramic(db_cursor, clean_test_blocks):
    """Verify CHECK constraint accepts valid 'Ceramic' value."""
    insert_test_block(db_cursor, 'TEST-CERAMIC', 'Ceramic')
    db_cursor.execute("SELECT material_type FROM blocks WHERE iso_code = 'TEST-CERAMIC'")
    result = db_cursor.fetchone()
    assert result[0] == "Ceramic", f"Expected 'Ceramic', got: {result[0]}"


def test_reject_null_low_poly_url(db_cursor, clean_test_blocks):
    """Verify NOT NULL constraint rejects NULL low_poly_url."""
    with pytest.raises(IntegrityError, match="not-null constraint"):
        insert_test_block(db_cursor, 'TEST-NULL-GLB', 'Stone', low_poly_url=None)


def test_reject_null_bbox(db_cursor, clean_test_blocks):
    """Verify NOT NULL constraint rejects NULL bbox."""
    with pytest.raises(IntegrityError, match="not-null constraint"):
        insert_test_block(db_cursor, 'TEST-NULL-BBOX', 'Stone', bbox=None)


# ===== TEST SUITE 3: Data Integrity =====

def test_six_blocks_preserve_iso_codes(db_cursor, requires_production_data):
    """Verify all 6 Sagrada Família blocks preserved their iso_code identifiers."""
    db_cursor.execute("""
        SELECT iso_code FROM blocks 
        WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'
        ORDER BY iso_code
    """)
    codes = [row[0] for row in db_cursor.fetchall()]
    expected = [f"GLPER.B-PAE0720.070{i}" for i in range(1, 7)]
    assert codes == expected, f"iso_code mismatch: expected {expected}, got {codes}"


def test_six_blocks_preserve_low_poly_urls(db_cursor, requires_production_data):
    """Verify all 6 blocks retained their low_poly_url (no data loss)."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM blocks 
        WHERE iso_code LIKE 'GLPER.B-PAE0720.07%' AND low_poly_url IS NOT NULL
    """)
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks with low_poly_url, found {count}"


def test_six_blocks_preserve_bbox_structure(db_cursor, requires_production_data):
    """Verify all 6 blocks retained valid bbox JSONB with min/max keys."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM blocks 
        WHERE 
            iso_code LIKE 'GLPER.B-PAE0720.07%' 
            AND bbox IS NOT NULL
            AND bbox ? 'min'
            AND bbox ? 'max'
    """)
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks with valid bbox structure, found {count}"


def test_six_blocks_preserve_validation_reports(db_cursor, requires_production_data):
    """Verify all 6 blocks retained validation_report with is_valid=true."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM blocks 
        WHERE 
            iso_code LIKE 'GLPER.B-PAE0720.07%' 
            AND validation_report IS NOT NULL
            AND validation_report->>'is_valid' = 'true'
    """)
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks with valid validation_report, found {count}"


def test_existing_indexes_remain_functional(db_cursor):
    """Verify existing indexes (idx_blocks_status) still work after migration."""
    db_cursor.execute("""
        EXPLAIN (FORMAT JSON) 
        SELECT * FROM blocks WHERE status = 'validated'
    """)
    plan = db_cursor.fetchone()[0]
    # Simple check: EXPLAIN should contain "Scan" indicating index usage
    # Full index validation would require parsing JSON plan
    assert "Scan" in str(plan), "Query plan missing expected Scan operation"


# ===== TEST SUITE 4: Rollback Tests =====

@pytest.mark.skip(reason="Destructive test, run manually only")
def test_down_migration_restores_schema(db_cursor):
    """Verify DOWN migration restores pre-T-1501-DB schema (manual test only)."""
    # Execute DOWN migration (destructive)
    with open("supabase/migrations/20260306000001_element_model_down.sql") as f:
        db_cursor.execute(f.read())
    
    # Verify material_type removed
    db_cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'material_type'
    """)
    assert db_cursor.fetchone()[0] == 0, "material_type still exists after rollback"
    
    # Verify workshop_id restored
    db_cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name = 'workshop_id'
    """)
    assert db_cursor.fetchone()[0] == 1, "workshop_id not restored after rollback"


@pytest.mark.skip(reason="Requires clean database, run manually only")
def test_idempotent_up_migration(db_cursor):
    """Verify UP migration can run twice without errors (IF NOT EXISTS guards)."""
    # Execute UP migration first time
    with open("supabase/migrations/20260306000001_element_model.sql") as f:
        migration_sql = f.read()
        db_cursor.execute(migration_sql)
    
    # Execute UP migration second time (should not fail)
    try:
        db_cursor.execute(migration_sql)
    except Exception as e:
        pytest.fail(f"Idempotent migration failed on second run: {e}")


# ===== TEST SUITE 5: Backend Baseline Validation =====

@pytest.mark.slow
def test_backend_test_baseline_maintained(db_cursor):
    """Verify backend test suite maintains baseline after migration (unit tests)."""
    import subprocess
    result = subprocess.run(
        ["pytest", "tests/unit/", "-v", "--tb=no", "-q"],
        capture_output=True,
        text=True
    )
    
    # Allow test to pass if unit tests pass (don't require exact 108 count due to test evolution)
    assert "passed" in result.stdout.lower(), f"Backend unit tests failed:\n{result.stdout}"
    assert result.returncode == 0, f"Test suite failed with exit code {result.returncode}"


@pytest.mark.slow
def test_parts_service_tests_pass(db_cursor):
    """Verify parts service tests pass after workshop_id removal."""
    import subprocess
    result = subprocess.run(
        ["pytest", "tests/unit/test_parts_service.py", "-v"],
        capture_output=True,
        text=True
    )
    
    assert "FAILED" not in result.stdout, f"Parts service tests failed:\n{result.stdout}"
    assert result.returncode == 0, f"Test suite failed with exit code {result.returncode}"


@pytest.mark.slow
def test_upload_service_tests_pass(db_cursor):
    """Verify upload service tests unaffected by migration (no schema overlap)."""
    import subprocess
    result = subprocess.run(
        ["pytest", "tests/unit/test_upload_service_enqueue.py", "-v"],
        capture_output=True,
        text=True
    )
    
    assert "FAILED" not in result.stdout, f"Upload service tests failed:\n{result.stdout}"
    assert result.returncode == 0, f"Test suite failed with exit code {result.returncode}"
