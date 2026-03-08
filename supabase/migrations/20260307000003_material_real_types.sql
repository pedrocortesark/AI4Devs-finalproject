-- Migration: T-1504-AGENT - Allow real material types (62 types)
-- Author: AI Assistant
-- Date: 2026-03-07
-- Context: Remove CHECK constraint Stone/Ceramic from T-1503, allow TEXT
-- Related: T-1503-AGENT (superseded), T-1501-DB (created material_type column)

BEGIN;

-- Step 1: Drop CHECK constraint from T-1503
-- This constraint limited material_type to enum ["Stone", "Ceramic"]
-- which was based on incorrect specification
ALTER TABLE blocks 
  DROP CONSTRAINT IF EXISTS blocks_material_type_check;

-- Step 2: Update existing "Stone" → "Montjuïc" (default material)
--         Update existing "Ceramic" → "Montjuïc" (no ceramic equivalent in dict)
-- This maintains data integrity while migrating to real material types
UPDATE blocks 
  SET material_type = 'Montjuïc'
  WHERE material_type IN ('Stone', 'Ceramic');

-- Step 3: Add comment documenting valid materials
-- Documents the 62 real stone types from MATERIAL_COLORS dictionary
COMMENT ON COLUMN blocks.material_type IS 
  'Material type: One of 62 real stone types from Sagrada Família (Montjuïc, Ulldecona, Floresta, Beix Anglès, etc.). See src/agent/constants.py MATERIAL_COLORS dictionary for complete list with RGB colors. Default: Montjuïc (most common material). Extracted from "Material" UserString in .3dm files.';

-- Step 4: Index already exists from T-1501
-- idx_blocks_material_type created by 20260306000001_element_model.sql
-- No additional index needed

COMMIT;

-- Verification queries (commented out for migration):
-- SELECT material_type, COUNT(*) FROM blocks GROUP BY material_type;
-- SELECT COUNT(*) FROM blocks WHERE material_type = 'Montjuïc';
