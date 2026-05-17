-- Migration: Remove obsolete material_type column
-- Date: 2026-05-16
-- Reason: material_type implementation was incorrect (searched wrong location in Rhino file)
--         Always returned default "Montjuïc" regardless of actual material
--         Actual material data is in rhino_metadata.userstrings.Material

-- Drop index (if exists)
DROP INDEX IF EXISTS idx_blocks_material_type;

-- Drop column
ALTER TABLE blocks DROP COLUMN IF EXISTS material_type;

-- Note: Actual material information is preserved in rhino_metadata JSONB column
-- Frontend can read material from rhino_metadata->>'userstrings'->>'Material'
