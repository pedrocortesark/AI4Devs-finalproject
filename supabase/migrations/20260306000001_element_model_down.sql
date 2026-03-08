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
