-- Migration: Fix Element Model (Corrective Migration)
-- Ticket: T-1501-DB (Recovery)
-- Date: 2026-03-10
-- Purpose: Re-apply element model changes after accidental rollback
--
-- Context: Previous migration 20260306000001_element_model_down.sql was executed
--          by mistake (it's a rollback script that should not be in /migrations/).
--          This migration re-applies all necessary schema changes.
--
-- Changes:
--   1. Add material_type column (TEXT, CHECK constraint)
--   2. Drop workshop_id column (obsolete, workshops not in MVP)
--   3. Create idx_blocks_material_type index
--   4. Add bbox structure CHECK constraint
--   5. Update existing blocks with default material_type

BEGIN;

-- ============================================
-- STEP 1: Add material_type column
-- ============================================
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS material_type TEXT;

-- Update existing blocks with default value
UPDATE blocks 
SET material_type = 'Montjuïc' 
WHERE material_type IS NULL;

COMMENT ON COLUMN blocks.material_type IS 
'Real material classification (62 Sagrada Família materials).
NOT "Stone"/"Ceramic" enum - those were placeholder values.
Example: "Montjuïc" (Barcelona sandstone), "Ulldecona", "Girona Granite".
Extracted from Rhino UserString key "Material" by agent (T-1504-AGENT).
Defaults to "Montjuïc" for existing architectural pieces.';

-- ============================================
-- STEP 2: Drop workshop_id column (workshops not in MVP)
-- ============================================
ALTER TABLE blocks DROP COLUMN IF EXISTS workshop_id;

-- ============================================
-- STEP 3: Create material_type index
-- ============================================
CREATE INDEX IF NOT EXISTS idx_blocks_material_type ON blocks(material_type);

-- ============================================
-- STEP 4: Add bbox structure CHECK constraint
-- ============================================
-- Ensure bbox JSON has correct structure when present
ALTER TABLE blocks DROP CONSTRAINT IF EXISTS blocks_bbox_structure_check;
ALTER TABLE blocks ADD CONSTRAINT blocks_bbox_structure_check
  CHECK (
    bbox IS NULL OR (
      jsonb_typeof(bbox -> 'min') = 'array' AND
      jsonb_typeof(bbox -> 'max') = 'array' AND
      jsonb_array_length(bbox -> 'min') = 3 AND
      jsonb_array_length(bbox -> 'max') = 3
    )
  );

COMMENT ON CONSTRAINT blocks_bbox_structure_check ON blocks IS
'Validates bbox structure: {min: [x,y,z], max: [x,y,z]}. 
Rejects invalid shapes like 2D arrays or missing keys.
NULL values allowed (async processing workflow).';

-- ============================================
-- STEP 5: Verification
-- ============================================
DO $$
DECLARE
  material_count INT;
  workshop_exists BOOLEAN;
  index_exists BOOLEAN;
  constraint_exists BOOLEAN;
BEGIN
  -- Check material_type column populated
  SELECT COUNT(*) INTO material_count FROM blocks WHERE material_type IS NOT NULL;
  
  -- Check workshop_id doesn't exist
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'blocks' AND column_name = 'workshop_id'
  ) INTO workshop_exists;
  
  -- Check index exists
  SELECT EXISTS (
    SELECT 1 FROM pg_indexes 
    WHERE tablename = 'blocks' AND indexname = 'idx_blocks_material_type'
  ) INTO index_exists;
  
  -- Check constraint exists
  SELECT EXISTS (
    SELECT 1 FROM information_schema.constraint_column_usage 
    WHERE table_name = 'blocks' AND constraint_name = 'blocks_bbox_structure_check'
  ) INTO constraint_exists;

  IF NOT workshop_exists AND index_exists AND constraint_exists THEN
    RAISE NOTICE 'Migration successful: Element model schema complete';
    RAISE NOTICE '  - material_type: % blocks populated', material_count;
    RAISE NOTICE '  - workshop_id: dropped ✓';
    RAISE NOTICE '  - idx_blocks_material_type: created ✓';
    RAISE NOTICE '  - blocks_bbox_structure_check: created ✓';
  ELSE
    RAISE EXCEPTION 'Migration incomplete. workshop_exists=%, index_exists=%, constraint_exists=%', 
      workshop_exists, index_exists, constraint_exists;
  END IF;
END $$;

COMMIT;
