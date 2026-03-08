-- Migration: Fix Element Model Constraints - Allow Async Geometry Processing
-- Date: 2026-03-07
-- Author: AI Assistant
-- Purpose: Revert overly strict NOT NULL constraints from 20260306000001_element_model.sql
--          to support the async workflow where blocks are created BEFORE geometry is processed.
--
-- Context: The current architecture is:
--   1. User uploads .3dm file
--   2. Backend creates upload event (confirm_upload) - NO block created yet
--   3. Celery worker parses .3dm file asynchronously
--   4. Worker creates blocks with geometry (low_poly_url + bbox) already calculated
--
-- Problem with previous migration:
--   - Made low_poly_url, bbox, material_type NOT NULL
--   - This prevents blocks from being created before geometry processing completes
--   - If GLB generation fails, block cannot be created at all (data loss)
--
-- Solution:
--   - Keep columns nullable but with sensible defaults
--   - Add CHECK constraints to ensure data quality
--   - Use application-level filtering to exclude incomplete blocks from 3D canvas
--
-- Design Principle:
--   Database should accept incomplete data during processing.
--   Application layer filters incomplete data from user-facing views.

BEGIN;

-- ============================================
-- STEP 1: Revert NOT NULL constraints (allow async processing)
-- ============================================
ALTER TABLE blocks 
  ALTER COLUMN low_poly_url DROP NOT NULL,
  ALTER COLUMN bbox DROP NOT NULL,
  ALTER COLUMN material_type DROP NOT NULL;

-- ============================================
-- STEP 2: Add sensible defaults
-- ============================================
-- Default for material_type: 'Stone' (Sagrada Família is primarily stone)
ALTER TABLE blocks 
  ALTER COLUMN material_type SET DEFAULT 'Stone';

-- No default for low_poly_url (empty string would be misleading)
-- No default for bbox (empty JSONB {} would break 3D rendering logic)

-- ============================================
-- STEP 3: Add CHECK constraint for bbox structure (when present)
-- ============================================
-- Purpose: If bbox is provided, ensure it has the correct structure
-- This allows NULL or empty {} but validates non-empty bboxes
ALTER TABLE blocks 
  DROP CONSTRAINT IF EXISTS blocks_bbox_structure_check;

ALTER TABLE blocks 
  ADD CONSTRAINT blocks_bbox_structure_check 
  CHECK (
    bbox IS NULL OR 
    bbox = '{}'::jsonb OR 
    (
      bbox ? 'min' AND 
      bbox ? 'max' AND
      jsonb_typeof(bbox->'min') = 'array' AND
      jsonb_typeof(bbox->'max') = 'array'
    )
  );

COMMENT ON CONSTRAINT blocks_bbox_structure_check ON blocks IS
'Ensures bbox, when present and non-empty, has {min: [...], max: [...]} structure required for 3D rendering. Allows NULL or empty {} during processing.';

-- ============================================
-- STEP 4: Update migration verification
-- ============================================
DO $$
DECLARE
    nullable_count INT;
    default_count INT;
    constraint_count INT;
BEGIN
    -- Verify columns are nullable
    SELECT COUNT(*) INTO nullable_count
    FROM information_schema.columns 
    WHERE 
        table_name = 'blocks' 
        AND column_name IN ('low_poly_url', 'bbox', 'material_type')
        AND is_nullable = 'YES';
    
    IF nullable_count <> 3 THEN
        RAISE EXCEPTION 'Migration failed: Expected 3 nullable geometry columns, found %', nullable_count;
    END IF;
    
    -- Verify material_type has default
    SELECT COUNT(*) INTO default_count
    FROM information_schema.columns 
    WHERE 
        table_name = 'blocks' 
        AND column_name = 'material_type'
        AND column_default IS NOT NULL;
    
    IF default_count <> 1 THEN
        RAISE EXCEPTION 'Migration failed: material_type default not set';
    END IF;
    
    -- Verify bbox CHECK constraint exists
    SELECT COUNT(*) INTO constraint_count
    FROM information_schema.constraint_column_usage
    WHERE table_name = 'blocks' 
      AND constraint_name = 'blocks_bbox_structure_check';
    
    IF constraint_count < 1 THEN
        RAISE EXCEPTION 'Migration failed: bbox structure CHECK constraint not created';
    END IF;
    
    RAISE NOTICE 'Migration successful: Geometry columns nullable with defaults + bbox validation';
END$$;

COMMIT;

-- ============================================
-- RECOMMENDED APPLICATION-LEVEL CHANGES
-- ============================================
-- 
-- Backend (parts_service.py):
--   Add filter: WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL
--   This excludes incomplete blocks from /api/parts endpoint
--
-- Frontend (PartsCanvas.tsx):
--   Skip rendering elements where !element.low_poly_url || !element.bbox
--   Display placeholder box for incomplete elements in list view
--
-- Agent (register_3dm_blocks.py):
--   ALWAYS provide low_poly_url + bbox when creating blocks
--   If GLB generation fails → use placeholder URL: 'error://glb-generation-failed'
--   If bbox calculation fails → use default box: {min: [0,0,0], max: [1,1,1]}
