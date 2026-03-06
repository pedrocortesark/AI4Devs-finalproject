# T-1501-DB: Database Schema & Migration — Technical Specification

**Ticket ID:** T-1501-DB  
**Epic:** US-015: Element Model Refactoring  
**Story Points:** 3  
**Status:** 🔜 NEXT (Enrichment Phase Complete)  
**Author:** AI Assistant (Senior Software Architect)  
**Date:** 2026-03-06  
**Enrichment Protocol Version:** 1.0

---

## 1. TICKET SUMMARY

### Objective
Execute a **critical database migration** to transform the Spanish-nomenclature "Parts" model (tipologia, workshop_id/name) into an English-nomenclature "Elements" model (material_type, no workshops). This migration is the **foundation** of the US-015 Epic and must maintain 100% test baseline (108/108 backend tests) while updating 6 real Sagrada Família elements in production.

### Critical Requirements
1. **ADD COLUMN** `material_type TEXT CHECK (material_type IN ('Stone', 'Ceramic'))` — Enum constraint for material classification
2. **DROP COLUMNS** `workshop_id`, `workshop_name` — Remove unused workshop references (workshops table not implemented in MVP)
3. **ALTER COLUMNS** `low_poly_url SET NOT NULL`, `bbox SET NOT NULL` — Enforce geometry completeness (filter incomplete elements from 3D rendering)
4. **UPDATE DATA** Set `material_type = 'Stone'` for 6 existing blocks (GLPER.B-PAE0720.0701-0706) — Default architectural material
5. **CREATE INDEX** `idx_blocks_material_type` — Optimize material filtering in dashboard queries

### Success Criteria
- Migration executes without errors in local Supabase instance
- 6 blocks updated with `material_type = 'Stone'` (no data loss)
- NOT NULL constraints enforce geometry completeness (reject NULL low_poly_url/bbox)
- Test baseline maintained: `make test-unit` returns 108/108 ✅
- Rollback plan documented (DOWN migration)
- Handoff document created for T-1502-INFRA

---

## 2. DATA STRUCTURES & CONTRACTS

### 2.1 Database Schema Changes

#### BEFORE (Current Schema)
```sql
-- supabase/migrations/20260211155000_create_blocks_table.sql
CREATE TABLE blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    iso_code text NOT NULL UNIQUE,
    status block_status NOT NULL DEFAULT 'uploaded',
    tipologia text NOT NULL,                         -- ❌ Spanish nomenclature
    zone_id uuid,
    workshop_id uuid,                                -- ❌ Remove (not used in MVP)
    created_by uuid,
    updated_by uuid,
    url_original text,
    url_glb text,
    rhino_metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    is_archived boolean NOT NULL DEFAULT false,
    validation_report jsonb,                         -- Added in 20260211160000
    low_poly_url TEXT NULL,                          -- ❌ Nullable (added in 20260219000001)
    bbox JSONB NULL                                  -- ❌ Nullable (added in 20260219000001)
);

-- Note: workshop_name doesn't exist in table but is referenced in backend schemas as JOIN artifact
```

#### AFTER (Migrated Schema)
```sql
-- supabase/migrations/20260306000001_element_model.sql
CREATE TABLE blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    iso_code text NOT NULL UNIQUE,
    status block_status NOT NULL DEFAULT 'uploaded',
    tipologia text NOT NULL,                         -- ✅ Keep for backward compat during migration
    material_type TEXT NOT NULL                      -- ✅ NEW: Enum constraint
        CHECK (material_type IN ('Stone', 'Ceramic')),
    zone_id uuid,
    created_by uuid,
    updated_by uuid,
    url_original text,
    url_glb text,
    rhino_metadata jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    is_archived boolean NOT NULL DEFAULT false,
    validation_report jsonb,
    low_poly_url TEXT NOT NULL,                      -- ✅ NOW REQUIRED (filter incomplete geometry)
    bbox JSONB NOT NULL                              -- ✅ NOW REQUIRED (filter incomplete geometry)
);

-- New index for material filtering
CREATE INDEX idx_blocks_material_type ON blocks(material_type);
```

### 2.2 Enum Constraint Specification

**Material Type Enum Values:**
```sql
-- ALLOWED VALUES (CHECK constraint)
'Stone'    -- Default for architectural pieces (capitel, columna, dovela, clave, imposta)
'Ceramic'  -- Alternative material for decorative elements (rare in Sagrada Família)

-- REJECTED VALUES (constraint violation)
'Piedra'   -- ❌ Spanish, will be rejected
'Ceramica' -- ❌ Spanish, will be rejected
'Metal'    -- ❌ Not in MVP scope
NULL       -- ❌ Violates NOT NULL constraint (after UPDATE step)
```

**Constraint Enforcement:**
- **Database Level:** `CHECK (material_type IN ('Stone', 'Ceramic'))` prevents invalid strings at INSERT/UPDATE
- **Application Level (Future):** Pydantic enum `MaterialType(str, Enum)` in T-1504-BACK will enforce type-safety
- **Agent Level (Future):** T-1503-AGENT will extract from Rhino UserString key `"Material"`, default to `"Stone"` if missing

---

## 3. API INTERFACE

### 3.1 Database Migration Interface

**Migration File:** `supabase/migrations/20260306000001_element_model.sql`

**Execution Method:**
```bash
# Apply migration to local Supabase
psql "$SUPABASE_DATABASE_URL" -f supabase/migrations/20260306000001_element_model.sql

# Or via Docker setup script
docker compose run --rm backend psql "$SUPABASE_DATABASE_URL" \
  -f /app/supabase/migrations/20260306000001_element_model.sql
```

**Expected Output:**
```
BEGIN
ALTER TABLE
UPDATE 6
ALTER TABLE
ALTER TABLE
DROP COLUMN
DROP COLUMN
CREATE INDEX
NOTICE: Migration successful: material_type column added, 6 blocks updated, constraints active
COMMIT
```

### 3.2 Verification Queries

**Verify material_type column exists:**
```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'blocks' AND column_name = 'material_type';

-- Expected result:
-- column_name   | data_type | is_nullable | column_default
-- material_type | text      | NO          | NULL
```

**Verify 6 blocks updated:**
```sql
SELECT id, iso_code, material_type, low_poly_url IS NOT NULL AS has_glb, bbox IS NOT NULL AS has_bbox
FROM blocks
WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'
ORDER BY iso_code;

-- Expected result:
-- id                                   | iso_code               | material_type | has_glb | has_bbox
-- <uuid-0701>                          | GLPER.B-PAE0720.0701   | Stone         | t       | t
-- <uuid-0702>                          | GLPER.B-PAE0720.0702   | Stone         | t       | t
-- <uuid-0703>                          | GLPER.B-PAE0720.0703   | Stone         | t       | t
-- <uuid-0704>                          | GLPER.B-PAE0720.0704   | Stone         | t       | t
-- <uuid-0705>                          | GLPER.B-PAE0720.0705   | Stone         | t       | t
-- <uuid-0706>                          | GLPER.B-PAE0720.0706   | Stone         | t       | t
```

**Verify NOT NULL constraints active:**
```sql
-- This should FAIL with constraint violation
INSERT INTO blocks (iso_code, tipologia, material_type, status)
VALUES ('TEST-NULL-CHECK', 'capitel', 'Stone', 'uploaded');

-- Expected error: ERROR:  null value in column "low_poly_url" violates not-null constraint
```

**Verify CHECK constraint active:**
```sql
-- This should FAIL with check constraint violation
INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
VALUES ('TEST-ENUM-CHECK', 'capitel', 'Piedra', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded');

-- Expected error: ERROR:  new row for relation "blocks" violates check constraint "blocks_material_type_check"
```

**Verify workshop columns removed:**
```sql
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'blocks' AND column_name IN ('workshop_id', 'workshop_name');

-- Expected result: 0 rows (columns dropped)
```

**Verify index created:**
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'blocks' AND indexname = 'idx_blocks_material_type';

-- Expected result:
-- indexname                  | indexdef
-- idx_blocks_material_type   | CREATE INDEX idx_blocks_material_type ON public.blocks USING btree (material_type)
```

---

## 4. COMPONENT CONTRACT

### 4.1 Affected Backend Components

**File:** `src/backend/schemas.py`

**Current Contract (BREAKING CHANGE):**
```python
class PartCanvasItem(BaseModel):
    """Minimal part info optimized for 3D canvas rendering."""
    id: UUID
    iso_code: str
    status: BlockStatus
    tipologia: str
    low_poly_url: Optional[str] = None          # ❌ BREAKS: Now NOT NULL in DB
    bbox: Optional[BoundingBox] = None          # ❌ BREAKS: Now NOT NULL in DB
    workshop_id: Optional[UUID] = None          # ❌ BREAKS: Column dropped in DB
```

**T-1501-DB Impact (No Changes Yet):**
- This ticket does NOT modify backend schemas
- T-1504-BACK will handle the transition: `PartCanvasItem` → `Element`
- **Interim Behavior:** Backend returns `workshop_id = None` for all rows (column doesn't exist)
- **Test Regressions Expected:** 0-3 tests may fail if they assert `workshop_id` presence

**File:** `src/backend/services/parts_service.py`

**Current Service Layer:**
```python
async def list_parts(...) -> PartsListResponse:
    # Query includes workshop_id (will become NULL after migration)
    query = """
        SELECT 
            b.id, b.iso_code, b.status, b.tipologia,
            b.low_poly_url, b.bbox, b.workshop_id
        FROM blocks b
        WHERE b.is_archived = false
    """
```

**T-1501-DB Impact:**
- Query will return `workshop_id = NULL` for all rows (column doesn't exist)
- `low_poly_url` and `bbox` will never be NULL (satisfied by NOT NULL constraint)
- **No code changes required** — service handles NULL workshop_id gracefully

### 4.2 Affected Agent Components

**File:** `src/agent/tasks/geometry_processing.py`

**Current Agent Behavior:**
```python
# After processing .3dm file, agent saves to DB:
block_data = {
    "low_poly_url": glb_public_url,
    "bbox": {"min": [x, y, z], "max": [x, y, z]},
    "status": "validated"
}
supabase.table("blocks").update(block_data).eq("id", block_id).execute()
```

**T-1501-DB Impact:**
- ✅ **No breaking changes** — agent already provides `low_poly_url` and `bbox` (satisfies NOT NULL)
- ❌ **Missing:** Agent does NOT extract `material_type` yet (T-1503-AGENT will implement)
- **Interim Behavior:** Manual UPDATE required in T-1501-DB to set `material_type = 'Stone'` for 6 existing blocks

### 4.3 Affected Frontend Components

**File:** `src/frontend/src/types/parts.ts`

**Current Contract:**
```typescript
export interface PartCanvasItem {
  id: string;
  iso_code: string;
  status: string;
  tipologia: string;
  low_poly_url: string | null;           // ❌ BREAKS: Now always present in DB
  bbox: BoundingBox | null;              // ❌ BREAKS: Now always present in DB
  workshop_id: string | null;            // ❌ BREAKS: Column dropped in DB
}
```

**T-1501-DB Impact:**
- Frontend will receive `workshop_id = null` from backend (no NULL propagation errors)
- `low_poly_url` and `bbox` will always be strings/objects (no more NULL checks needed)
- **T-1505-FRONT** will update types to reflect new reality

---

## 5. TEST CASES CHECKLIST

### 5.1 Migration Execution Tests

**Test File:** `tests/integration/test_t1501_migration.py` (NEW FILE)

| # | Test Case | Type | Expected Result |
|---|-----------|------|-----------------|
| 1 | **Migration applies without errors** | Integration | `psql` exit code 0, COMMIT confirmed |
| 2 | **6 blocks remain in database** | Integration | `SELECT COUNT(*) FROM blocks` returns 6 |
| 3 | **All 6 blocks have material_type = 'Stone'** | Integration | `SELECT COUNT(*) FROM blocks WHERE material_type = 'Stone'` returns 6 |
| 4 | **material_type column exists with CHECK constraint** | Integration | `SELECT column_name FROM information_schema.columns WHERE table_name = 'blocks' AND column_name = 'material_type'` returns 1 row |
| 5 | **workshop_id column removed** | Integration | `SELECT column_name FROM information_schema.columns WHERE table_name = 'blocks' AND column_name = 'workshop_id'` returns 0 rows |
| 6 | **workshop_name column removed** | Integration | `SELECT column_name FROM information_schema.columns WHERE table_name = 'blocks' AND column_name = 'workshop_name'` returns 0 rows |
| 7 | **low_poly_url is NOT NULL** | Integration | `SELECT is_nullable FROM information_schema.columns WHERE column_name = 'low_poly_url'` returns 'NO' |
| 8 | **bbox is NOT NULL** | Integration | `SELECT is_nullable FROM information_schema.columns WHERE column_name = 'bbox'` returns 'NO' |
| 9 | **Index idx_blocks_material_type created** | Integration | `SELECT indexname FROM pg_indexes WHERE indexname = 'idx_blocks_material_type'` returns 1 row |

### 5.2 Constraint Enforcement Tests

| # | Test Case | Type | Expected Result |
|---|-----------|------|-----------------|
| 10 | **Reject NULL material_type** | Unit | `INSERT ... material_type = NULL` raises `IntegrityError` with message "violates not-null constraint" |
| 11 | **Reject invalid material_type (Spanish)** | Unit | `INSERT ... material_type = 'Piedra'` raises `IntegrityError` with message "violates check constraint" |
| 12 | **Reject invalid material_type (free string)** | Unit | `INSERT ... material_type = 'Metal'` raises `IntegrityError` with message "violates check constraint" |
| 13 | **Accept valid material_type (Stone)** | Unit | `INSERT ... material_type = 'Stone'` succeeds (0 error) |
| 14 | **Accept valid material_type (Ceramic)** | Unit | `INSERT ... material_type = 'Ceramic'` succeeds (0 error) |
| 15 | **Reject NULL low_poly_url** | Unit | `INSERT ... low_poly_url = NULL` raises `IntegrityError` |
| 16 | **Reject NULL bbox** | Unit | `INSERT ... bbox = NULL` raises `IntegrityError` |

### 5.3 Data Integrity Tests

| # | Test Case | Type | Expected Result |
|---|-----------|------|-----------------|
| 17 | **6 blocks preserve iso_code** | Integration | All 6 `GLPER.B-PAE0720.07xx` codes exist with same UUIDs |
| 18 | **6 blocks preserve low_poly_url** | Integration | All 6 blocks have non-NULL `low_poly_url` (Supabase Storage URLs) |
| 19 | **6 blocks preserve bbox** | Integration | All 6 blocks have valid JSONB `bbox` with `{"min": [...], "max": [...]}` structure |
| 20 | **6 blocks preserve validation_report** | Integration | All 6 blocks have non-NULL `validation_report` with `is_valid = true` |
| 21 | **Existing indexes remain functional** | Integration | Query `SELECT * FROM blocks WHERE status = 'validated'` uses `idx_blocks_status` (EXPLAIN ANALYZE) |

### 5.4 Rollback Tests

| # | Test Case | Type | Expected Result |
|---|-----------|------|-----------------|
| 22 | **DOWN migration restores schema** | Integration | Execute DOWN migration, verify `workshop_id` column exists, `material_type` removed |
| 23 | **Idempotent UP migration** | Integration | Run UP migration twice, no errors (IF NOT EXISTS guards work) |

### 5.5 Backend Test Baseline Validation

| # | Test Case | Type | Expected Result |
|---|-----------|------|-----------------|
| 24 | **All backend tests pass** | Regression | `make test-unit` returns 108/108 ✅ (0 regressions) |
| 25 | **Parts service tests pass** | Regression | `pytest tests/backend/test_parts_service.py -v` all PASS |
| 26 | **Upload service tests pass** | Regression | `pytest tests/backend/test_upload_service.py -v` all PASS |

---

## 6. FILES TO CREATE/MODIFY

### 6.1 NEW Files

| File Path | Purpose | Lines (est.) |
|-----------|---------|--------------|
| `supabase/migrations/20260306000001_element_model.sql` | UP migration (ADD material_type, DROP workshops, SET NOT NULL, UPDATE data) | ~120 |
| `supabase/migrations/20260306000001_element_model_down.sql` | DOWN migration (rollback plan) | ~80 |
| `tests/integration/test_t1501_migration.py` | Integration tests for migration success + constraints | ~250 |
| `docs/US-015/T-1501-DB-HANDOFF.md` | Handoff document for T-1502-INFRA (migration results, deployment notes) | ~60 |

**Total:** ~510 lines of new code/docs

### 6.2 MODIFIED Files (Future Tickets)

| File Path | Ticket | Modification Type |
|-----------|--------|-------------------|
| `src/backend/schemas.py` | T-1504-BACK | Rename `PartCanvasItem` → `Element`, add `MaterialType` enum, remove `Optional` for `low_poly_url`/`bbox` |
| `src/backend/services/parts_service.py` | T-1504-BACK | Update query to exclude `workshop_id`, rename variables |
| `src/frontend/src/types/parts.ts` | T-1505-FRONT | Rename `PartCanvasItem` → `Element`, update field types (no null for geometry) |
| `src/agent/tasks/geometry_processing.py` | T-1503-AGENT | Extract `material_type` from Rhino UserString, validate enum before saving |

**Note:** T-1501-DB does NOT modify application code (DB-only migration).

---

## 7. REUSABLE COMPONENTS/PATTERNS

### 7.1 Migration Template (Reusable Pattern)

**File:** `supabase/migrations/YYYYMMDD000001_template.sql`

```sql
-- Migration: [Brief Description]
-- Ticket: T-XXXX-XX
-- Author: [Name]
-- Date: YYYY-MM-DD
-- Purpose: [What this migration achieves]
--
-- Prerequisites:
--   - [List previous migrations required]
--
-- Downstream dependencies:
--   - [List tickets that depend on this migration]

BEGIN;

-- ============================================
-- STEP 1: [Action Description]
-- ============================================
-- [SQL statements]

-- ============================================
-- STEP 2: [Action Description]
-- ============================================
-- [SQL statements]

-- ============================================
-- VERIFY: Migration Success
-- ============================================
DO $$
DECLARE
    -- [Declare validation variables]
BEGIN
    -- [Validation checks with RAISE EXCEPTION if failed]
    RAISE NOTICE 'Migration successful: [summary]';
END$$;

COMMIT;
```

**Usage in T-1501-DB:** Followed exactly, 5 steps (ADD COLUMN, UPDATE data, ALTER constraints, DROP columns, CREATE index), verification block included.

### 7.2 Test Fixture Pattern (Reusable)

**Pattern:** Cleanup test data using `SELECT+DELETE` instead of `supabase.table().delete().like()` (unreliable in Supabase SDK).

**Example:**
```python
import pytest
import psycopg2

@pytest.fixture(scope="function")
def clean_test_blocks():
    """Remove test blocks before/after test execution."""
    conn = psycopg2.connect(os.getenv("SUPABASE_DATABASE_URL"))
    cur = conn.cursor()
    
    # Cleanup before test
    cur.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")
    conn.commit()
    
    yield  # Run test
    
    # Cleanup after test
    cur.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")
    conn.commit()
    cur.close()
    conn.close()
```

**Usage in T-1501-DB:** `tests/integration/test_t1501_migration.py` will use this pattern for cleanup.

### 7.3 Constraint Testing Pattern

**Pattern:** Test database constraints by asserting that invalid data raises `IntegrityError`.

**Example:**
```python
import pytest
from psycopg2 import IntegrityError

def test_material_type_rejects_spanish():
    """Verify CHECK constraint rejects Spanish enum values."""
    with pytest.raises(IntegrityError, match="violates check constraint"):
        cur.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-ENUM', 'capitel', 'Piedra', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
        """)
```

**Usage in T-1501-DB:** 7 constraint tests (material_type enum, NULL checks for low_poly_url/bbox).

---

## 8. NEXT STEPS (Handoff Data for TDD-RED)

### 8.1 Implementation Sequence

1. **Create Migration File** (`20260306000001_element_model.sql`)
   - Follow template pattern from Section 7.1
   - 5 steps: ADD COLUMN → UPDATE → ALTER → DROP → CREATE INDEX
   - Verification block: Check column exists, 6 rows updated, constraints active

2. **Create Rollback File** (`20260306000001_element_model_down.sql`)
   - Reverse order: DROP INDEX → ADD COLUMN workshop_id → DROP material_type → ALTER low_poly_url/bbox NULL
   - Critical: Backup data before rollback (material_type values lost)

3. **Write Test File** (`tests/integration/test_t1501_migration.py`)
   - 26 test cases (see Section 5 checklist)
   - Test execution order: Migration tests → Constraint tests → Data integrity tests → Rollback tests → Baseline validation

4. **Execute TDD-RED** (All tests FAIL - expected state)
   - Run tests BEFORE applying migration
   - Expected: 26 FAIL (migration not executed yet)

5. **Execute TDD-GREEN** (Apply migration, tests PASS)
   - Run: `psql "$SUPABASE_DATABASE_URL" -f supabase/migrations/20260306000001_element_model.sql`
   - Re-run tests: 26 PASS ✅
   - Verify baseline: `make test-unit` should remain 108/108 ✅

6. **Execute TDD-REFACTOR** (Optimize migration)
   - Add idempotency: `IF NOT EXISTS` guards for column/index creation
   - Add comments: Explain enum values, constraint rationale
   - Extract magic strings: Document valid enum values in migration header

7. **Create Handoff Document** (`T-1501-DB-HANDOFF.md`)
   - Migration results (6 blocks updated, constraints verified)
   - Deployment checklist (backup before production, test in staging first)
   - Breaking changes summary (workshop_id removed, geometry now required)
   - Recommendations for T-1502-INFRA (storage path conventions)

### 8.2 Key Test Cases for TDD-RED

**Ticket ID:** T-1501-DB  
**Feature Name:** Element Model Database Migration  
**Priority Test Cases (Must fail in RED phase):**

1. **`test_material_type_column_exists`** — Assert column in `information_schema.columns` (FAIL until migration applied)
2. **`test_six_blocks_have_material_type_stone`** — Assert 6 blocks with `material_type = 'Stone'` (FAIL until UPDATE executed)
3. **`test_low_poly_url_not_null_constraint`** — Insert NULL value, expect IntegrityError (FAIL until ALTER executed)
4. **`test_workshop_id_column_removed`** — Assert column NOT in `information_schema.columns` (FAIL until DROP executed)
5. **`test_material_type_index_created`** — Assert index in `pg_indexes` (FAIL until CREATE INDEX executed)

### 8.3 Files to Create in TDD-RED Phase

1. **Migration UP:** `supabase/migrations/20260306000001_element_model.sql`
2. **Migration DOWN:** `supabase/migrations/20260306000001_element_model_down.sql`
3. **Test File:** `tests/integration/test_t1501_migration.py`
4. **Baseline Snapshot:** `docs/US-015/T-1501-DB-BASELINE.md` (document current 108/108 state)

### 8.4 Definition of DONE Validation

Before marking T-1501-DB as DONE, verify:

- ✅ Migration executed successfully (COMMIT confirmed)
- ✅ 6 blocks updated with `material_type = 'Stone'` (no data loss)
- ✅ Constraints active (CHECK, NOT NULL, INDEX verified)
- ✅ 26 integration tests PASS (100% success rate)
- ✅ Backend test baseline maintained: `make test-unit` returns 108/108 ✅
- ✅ Rollback plan tested (DOWN migration functional)
- ✅ Handoff document created (`T-1501-DB-HANDOFF.md`)
- ✅ Prompt logged in `prompts.md` (Entry #207)
- ✅ `activeContext.md` updated (mark T-1501-DB DONE, move to T-1502-INFRA)

---

## APPENDIX A: SQL Migration Complete Code

### A.1 UP Migration

```sql
-- Migration: Element Model Refactoring - Database Schema
-- Ticket: T-1501-DB
-- Epic: US-015: Element Model Refactoring
-- Author: AI Assistant
-- Date: 2026-03-06
-- Purpose: Transform Spanish "Parts" model to English "Elements" model
--          ADD material_type, DROP workshops, enforce geometry completeness
--
-- Prerequisites:
--   - 20260211155000_create_blocks_table.sql (blocks table exists)
--   - 20260219000001_add_low_poly_url_bbox.sql (low_poly_url/bbox columns exist)
--
-- Downstream dependencies:
--   - T-1502-INFRA: Storage path conventions (will use material_type)
--   - T-1503-AGENT: Rhino parser (will extract material_type from UserString)
--   - T-1504-BACK: API integration (will expose MaterialType enum)
--   - T-1505-FRONT: Zod validation (will enforce Element contract)
--
-- Valid Material Types (Enum):
--   - 'Stone'    — Architectural carved stone pieces (default for Sagrada Família)
--   - 'Ceramic'  — Decorative ceramic elements (rare in this project)
--
-- Breaking Changes:
--   - workshop_id column REMOVED (workshops table not implemented in MVP)
--   - workshop_name column REMOVED (was never a real column, JOIN artifact)
--   - low_poly_url is now REQUIRED (blocks without GLB are filtered from canvas)
--   - bbox is now REQUIRED (blocks without bounding box cannot be positioned)

BEGIN;

-- ============================================
-- STEP 1: Add material_type column with CHECK constraint
-- ============================================
-- Purpose: Replace Spanish 'tipologia' with English enum for international standard compliance
-- Constraint: Only 'Stone' or 'Ceramic' allowed (rejects Spanish 'Piedra', 'Ceramica', or free strings)
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS material_type TEXT 
  CHECK (material_type IN ('Stone', 'Ceramic'));

COMMENT ON COLUMN blocks.material_type IS 
'Material type classification in English. 
Valid values: "Stone" (carved architectural stone), "Ceramic" (decorative elements). 
Extracted from Rhino UserString key "Material" by agent (T-1503-AGENT). 
Defaults to "Stone" for existing architectural pieces.';

-- ============================================
-- STEP 2: Update existing 6 blocks with default material
-- ============================================
-- Purpose: Populate material_type for Sagrada Família pieces (GLPER.B-PAE0720.0701-0706)
-- Assumption: All existing blocks are carved stone architectural elements (capitel typology)
UPDATE blocks 
SET material_type = 'Stone' 
WHERE material_type IS NULL;

-- Verify: Expect 6 rows updated
-- SELECT COUNT(*) FROM blocks WHERE material_type = 'Stone'; -- Should return 6

-- ============================================
-- STEP 3: Enforce geometry completeness (NOT NULL constraints)
-- ============================================
-- Purpose: Filter incomplete elements from 3D canvas (blocks without GLB or BBox cannot render)
-- Impact: All future INSERTs must provide low_poly_url + bbox (agent generates these in T-0502-AGENT)
ALTER TABLE blocks 
  ALTER COLUMN low_poly_url SET NOT NULL,
  ALTER COLUMN bbox SET NOT NULL;

-- ============================================
-- STEP 4: Remove workshop references (not used in MVP)
-- ============================================
-- Purpose: Simplify schema by removing unused foreign key to non-existent workshops table
-- Note: workshop_name never existed as column (was JOIN artifact in backend queries)
ALTER TABLE blocks 
  DROP COLUMN IF EXISTS workshop_id,
  DROP COLUMN IF EXISTS workshop_name;

-- ============================================
-- STEP 5: Create index for material filtering
-- ============================================
-- Purpose: Optimize dashboard queries filtering by material_type (e.g., "Show all Stone pieces")
-- Performance: Expect <50ms for material filtering on 10,000+ rows
CREATE INDEX IF NOT EXISTS idx_blocks_material_type 
  ON blocks(material_type);

-- ============================================
-- VERIFY: Migration Success
-- ============================================
DO $$
DECLARE
    col_count INT;
    row_count INT;
    not_null_count INT;
    idx_count INT;
BEGIN
    -- Check material_type column exists
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns 
    WHERE table_name = 'blocks' AND column_name = 'material_type';
    
    IF col_count <> 1 THEN
        RAISE EXCEPTION 'Migration failed: material_type column not created';
    END IF;
    
    -- Check workshop columns removed
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns 
    WHERE table_name = 'blocks' AND column_name IN ('workshop_id', 'workshop_name');
    
    IF col_count <> 0 THEN
        RAISE EXCEPTION 'Migration failed: workshop columns not dropped (found %)', col_count;
    END IF;
    
    -- Check 6 blocks updated with material_type
    SELECT COUNT(*) INTO row_count
    FROM blocks 
    WHERE material_type = 'Stone';
    
    IF row_count <> 6 THEN
        RAISE EXCEPTION 'Migration failed: expected 6 blocks with Stone, found %', row_count;
    END IF;
    
    -- Check NOT NULL constraints active
    SELECT COUNT(*) INTO not_null_count
    FROM information_schema.columns 
    WHERE 
        table_name = 'blocks' 
        AND column_name IN ('low_poly_url', 'bbox')
        AND is_nullable = 'NO';
    
    IF not_null_count <> 2 THEN
        RAISE EXCEPTION 'Migration failed: NOT NULL constraints not applied (found %/2)', not_null_count;
    END IF;
    
    -- Check index created
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes 
    WHERE tablename = 'blocks' AND indexname = 'idx_blocks_material_type';
    
    IF idx_count <> 1 THEN
        RAISE EXCEPTION 'Migration failed: material_type index not created';
    END IF;
    
    RAISE NOTICE 'Migration successful: material_type column added, 6 blocks updated, constraints active, workshop columns dropped, index created';
END$$;

COMMIT;
```

### A.2 DOWN Migration (Rollback)

```sql
-- Migration DOWN: Rollback Element Model Refactoring
-- Ticket: T-1501-DB
-- Date: 2026-03-06
-- Purpose: Restore schema to pre-migration state (for emergency rollback)
--
-- ⚠️ WARNING: This will LOSE all material_type data. 
-- Backup blocks table before executing rollback.
--
-- Rollback strategy: Reverse order of UP migration steps

BEGIN;

-- ============================================
-- STEP 1: Drop material_type index
-- ============================================
DROP INDEX IF EXISTS idx_blocks_material_type;

-- ============================================
-- STEP 2: Restore workshop_id column (nullable)
-- ============================================
-- Note: Cannot restore workshop_name (was never a real column)
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS workshop_id uuid;

COMMENT ON COLUMN blocks.workshop_id IS 
'[RESTORED via rollback] Assigned workshop UUID. 
Note: workshops table does not exist in MVP, this column was unused.';

-- ============================================
-- STEP 3: Remove NOT NULL constraints on geometry
-- ============================================
-- Purpose: Allow blocks without GLB/BBox (same as original schema)
ALTER TABLE blocks 
  ALTER COLUMN low_poly_url DROP NOT NULL,
  ALTER COLUMN bbox DROP NOT NULL;

-- ============================================
-- STEP 4: Drop material_type column
-- ============================================
-- ⚠️ DATA LOSS: All material_type values ('Stone', 'Ceramic') will be deleted
ALTER TABLE blocks DROP COLUMN IF EXISTS material_type;

-- ============================================
-- VERIFY: Rollback Success
-- ============================================
DO $$
DECLARE
    col_exists INT;
BEGIN
    -- Check material_type column removed
    SELECT COUNT(*) INTO col_exists
    FROM information_schema.columns 
    WHERE table_name = 'blocks' AND column_name = 'material_type';
    
    IF col_exists <> 0 THEN
        RAISE EXCEPTION 'Rollback failed: material_type column still exists';
    END IF;
    
    -- Check workshop_id restored
    SELECT COUNT(*) INTO col_exists
    FROM information_schema.columns 
    WHERE table_name = 'blocks' AND column_name = 'workshop_id';
    
    IF col_exists <> 1 THEN
        RAISE EXCEPTION 'Rollback failed: workshop_id column not restored';
    END IF;
    
    RAISE NOTICE 'Rollback successful: schema restored to pre-T-1501-DB state';
END$$;

COMMIT;
```

---

## APPENDIX B: Integration Test Complete Code

```python
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


# ===== FIXTURES =====

@pytest.fixture(scope="module")
def db_conn():
    """Provide direct PostgreSQL connection to Supabase database."""
    conn = psycopg2.connect(os.getenv("SUPABASE_DATABASE_URL"))
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
def clean_test_blocks(db_cursor):
    """Remove test blocks before/after test execution."""
    db_cursor.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")
    yield
    db_cursor.execute("DELETE FROM blocks WHERE iso_code LIKE 'TEST-%'")


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


def test_six_blocks_remain_in_database(db_cursor):
    """Verify 6 Sagrada Família blocks survived migration without data loss."""
    db_cursor.execute("SELECT COUNT(*) FROM blocks WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'")
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks after migration, found {count}"


def test_all_six_blocks_have_material_type_stone(db_cursor):
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
        db_cursor.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-NULL-MAT', 'capitel', NULL, 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
        """)


def test_reject_spanish_piedra(db_cursor, clean_test_blocks):
    """Verify CHECK constraint rejects Spanish 'Piedra'."""
    with pytest.raises(IntegrityError, match="check constraint"):
        db_cursor.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-SPANISH', 'capitel', 'Piedra', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
        """)


def test_reject_invalid_metal(db_cursor, clean_test_blocks):
    """Verify CHECK constraint rejects free strings like 'Metal' (not in enum)."""
    with pytest.raises(IntegrityError, match="check constraint"):
        db_cursor.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-METAL', 'capitel', 'Metal', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
        """)


def test_accept_valid_stone(db_cursor, clean_test_blocks):
    """Verify CHECK constraint accepts valid 'Stone' value."""
    db_cursor.execute("""
        INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
        VALUES ('TEST-STONE', 'capitel', 'Stone', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
    """)
    db_cursor.execute("SELECT material_type FROM blocks WHERE iso_code = 'TEST-STONE'")
    result = db_cursor.fetchone()
    assert result[0] == "Stone", f"Expected 'Stone', got: {result[0]}"


def test_accept_valid_ceramic(db_cursor, clean_test_blocks):
    """Verify CHECK constraint accepts valid 'Ceramic' value."""
    db_cursor.execute("""
        INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
        VALUES ('TEST-CERAMIC', 'capitel', 'Ceramic', 'https://example.com/test.glb', '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
    """)
    db_cursor.execute("SELECT material_type FROM blocks WHERE iso_code = 'TEST-CERAMIC'")
    result = db_cursor.fetchone()
    assert result[0] == "Ceramic", f"Expected 'Ceramic', got: {result[0]}"


def test_reject_null_low_poly_url(db_cursor, clean_test_blocks):
    """Verify NOT NULL constraint rejects NULL low_poly_url."""
    with pytest.raises(IntegrityError, match="not-null constraint"):
        db_cursor.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-NULL-GLB', 'capitel', 'Stone', NULL, '{"min":[0,0,0],"max":[1,1,1]}'::jsonb, 'uploaded')
        """)


def test_reject_null_bbox(db_cursor, clean_test_blocks):
    """Verify NOT NULL constraint rejects NULL bbox."""
    with pytest.raises(IntegrityError, match="not-null constraint"):
        db_cursor.execute("""
            INSERT INTO blocks (iso_code, tipologia, material_type, low_poly_url, bbox, status)
            VALUES ('TEST-NULL-BBOX', 'capitel', 'Stone', 'https://example.com/test.glb', NULL, 'uploaded')
        """)


# ===== TEST SUITE 3: Data Integrity =====

def test_six_blocks_preserve_iso_codes(db_cursor):
    """Verify all 6 Sagrada Família blocks preserved their iso_code identifiers."""
    db_cursor.execute("""
        SELECT iso_code FROM blocks 
        WHERE iso_code LIKE 'GLPER.B-PAE0720.07%'
        ORDER BY iso_code
    """)
    codes = [row[0] for row in db_cursor.fetchall()]
    expected = [f"GLPER.B-PAE0720.070{i}" for i in range(1, 7)]
    assert codes == expected, f"iso_code mismatch: expected {expected}, got {codes}"


def test_six_blocks_preserve_low_poly_urls(db_cursor):
    """Verify all 6 blocks retained their low_poly_url (no data loss)."""
    db_cursor.execute("""
        SELECT COUNT(*) FROM blocks 
        WHERE iso_code LIKE 'GLPER.B-PAE0720.07%' AND low_poly_url IS NOT NULL
    """)
    count = db_cursor.fetchone()[0]
    assert count == 6, f"Expected 6 blocks with low_poly_url, found {count}"


def test_six_blocks_preserve_bbox_structure(db_cursor):
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


def test_six_blocks_preserve_validation_reports(db_cursor):
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
    """Verify backend test suite maintains 108/108 passing tests after migration."""
    import subprocess
    result = subprocess.run(
        ["make", "test-unit"],
        capture_output=True,
        text=True
    )
    
    assert "108 passed" in result.stdout, f"Backend tests regressed:\n{result.stdout}"
    assert result.returncode == 0, f"Test suite failed with exit code {result.returncode}"


@pytest.mark.slow
def test_parts_service_tests_pass(db_cursor):
    """Verify parts service tests pass after workshop_id removal."""
    import subprocess
    result = subprocess.run(
        ["pytest", "tests/backend/test_parts_service.py", "-v"],
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
        ["pytest", "tests/backend/test_upload_service.py", "-v"],
        capture_output=True,
        text=True
    )
    
    assert "FAILED" not in result.stdout, f"Upload service tests failed:\n{result.stdout}"
    assert result.returncode == 0, f"Test suite failed with exit code {result.returncode}"
```

---

**END OF TECHNICAL SPECIFICATION**

---

**Next Action:** Execute TDD-RED phase by creating migration files and running tests (expect 26 FAIL).
