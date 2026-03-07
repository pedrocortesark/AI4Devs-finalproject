-- Migration: Element Model Refactoring - Database Schema
-- Ticket: T-1501-DB
-- Epic: US-015: Element Model Refactoring
-- Author: AI Assistant
-- Date: 2026-03-06
-- Purpose: Transform Spanish "Parts" model to English "Elements" model
--          ADD material_type, DROP workshops, enforce geometry completeness
--
-- ⚠️ IMPORTANT: PARTIALLY SUPERSEDED by 20260307000002_fix_element_model_constraints.sql
--    The NOT NULL constraints on low_poly_url/bbox/material_type were REVERTED in the
--    subsequent migration to support async geometry processing workflow.
--    Current schema: These columns are NULLABLE with CHECK constraints for validation.
--
-- Prerequisites:
--   - 20260211155000_create_blocks_table.sql (blocks table exists)
--   - 20260219000001_add_low_poly_url_bbox.sql (low_poly_url/bbox columns exist)
--
-- Downstream dependencies:
--   - 20260307000002_fix_element_model_constraints.sql (REVERTS NOT NULL constraints)
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
--   ⚠️  NOTE: The following constraints were REVERTED in migration 20260307000002:
--   - low_poly_url: Set NOT NULL → REVERTED to NULLABLE (async processing)
--   - bbox: Set NOT NULL → REVERTED to NULLABLE (async processing)
--   - material_type: Set NOT NULL → REVERTED to NULLABLE with DEFAULT 'Stone'

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
Defaults to "Stone" for existing architectural pieces.
Example query: SELECT COUNT(*) FROM blocks WHERE material_type = ''Stone'';';

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
-- ⚠️  SUPERSEDED: These constraints were REVERTED in 20260307000002_fix_element_model_constraints.sql
-- ============================================
-- Original Purpose: Filter incomplete elements from 3D canvas (blocks without GLB or BBox cannot render)
-- Original Impact: All future INSERTs must provide low_poly_url + bbox (agent generates these in T-0502-AGENT)
--
-- Current State (after 20260307000002):
--   - Columns are NULLABLE (async Celery workers create blocks before geometry ready)
--   - Application layer filters incomplete blocks (WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL)
--   - CHECK constraints validate structure when data is present
--
-- The code below executes but is immediately reverted by the next migration:
ALTER TABLE blocks 
  ALTER COLUMN low_poly_url SET NOT NULL,
  ALTER COLUMN bbox SET NOT NULL,
  ALTER COLUMN material_type SET NOT NULL;

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
    
    -- Check blocks updated with material_type (idempotent: allows 0 or 6)
    -- Why idempotent? Empty DB (CI/local) = 0 blocks, Production = 6 Sagrada Família blocks
    -- This allows migration to succeed in both environments without manual intervention
    SELECT COUNT(*) INTO row_count
    FROM blocks 
    WHERE material_type = 'Stone';
    
    -- Allow 0 blocks (empty DB) or 6 blocks (with Sagrada Família data)
    IF row_count <> 0 AND row_count <> 6 THEN
        RAISE EXCEPTION 'Migration failed: expected 0 or 6 blocks with Stone, found %', row_count;
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
