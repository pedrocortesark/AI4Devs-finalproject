-- Rollback: Restore material_type column
-- Date: 2026-05-16
-- Warning: This will re-add the column but data will be lost. All values will be NULL.

-- Recreate column
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS material_type TEXT;

-- Recreate index
CREATE INDEX IF NOT EXISTS idx_blocks_material_type ON blocks(material_type);

-- Note: Original data is LOST. Cannot recover from rhino_metadata without re-processing.
-- This rollback is for schema consistency only, not data recovery.
