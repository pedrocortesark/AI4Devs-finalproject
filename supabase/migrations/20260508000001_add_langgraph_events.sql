-- Migration: Add LangGraph event tracking columns
-- Ticket: T-1805-AGENT
-- Author: AI Assistant
-- Date: 2026-05-08
-- Purpose: Enable granular audit trail of LangGraph StateGraph node transitions
--
-- This migration adds:
-- 1. block_id column (if using file_id) or ensures compatibility with existing block_id
-- 2. node_name VARCHAR(100) to identify StateGraph node
-- 3. state_snapshot JSONB for lightweight state tracking
-- 4. Compound index on (block_id, node_name, created_at) for Grafana queries
--
-- Expected state_snapshot structure:
-- {
--   "overall_status": "validated" | "rejected" | "processing",
--   "nomenclature_valid": boolean,
--   "geometry_valid": boolean,
--   "classification_method": "llm_gpt4" | "fallback_regex" | "manual_override",
--   "validation_path_length": number
-- }

BEGIN;

-- 1. Add block_id column if it doesn't exist (compatibility with file_id)
-- This is defensive: if table still uses file_id from T-004, rename it
DO $$ BEGIN
    -- Check if file_id exists and block_id doesn't
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'events' AND column_name = 'file_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'events' AND column_name = 'block_id'
    ) THEN
        -- Rename file_id to block_id for consistency with data model
        ALTER TABLE events RENAME COLUMN file_id TO block_id;
        
        -- Update index name
        ALTER INDEX IF EXISTS idx_events_file_id RENAME TO idx_events_block_id;
    END IF;
    
    -- If neither exists, add block_id (fresh install)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'events' AND column_name IN ('file_id', 'block_id')
    ) THEN
        ALTER TABLE events ADD COLUMN block_id UUID NOT NULL;
        CREATE INDEX idx_events_block_id ON events(block_id);
    END IF;
END $$;

-- 2. Add node_name column for LangGraph node identification
ALTER TABLE events
ADD COLUMN IF NOT EXISTS node_name VARCHAR(100);

-- 3. Add state_snapshot JSONB for lightweight state tracking
ALTER TABLE events
ADD COLUMN IF NOT EXISTS state_snapshot JSONB DEFAULT NULL;

-- 4. Create compound index for Grafana timeline queries
-- Optimizes: SELECT * FROM events WHERE block_id = $1 ORDER BY created_at
CREATE INDEX IF NOT EXISTS idx_events_block_node_time 
ON events(block_id, node_name, created_at DESC);

-- 5. Create index on node_name for filtering by node type
CREATE INDEX IF NOT EXISTS idx_events_node_name 
ON events(node_name) 
WHERE node_name IS NOT NULL;

-- 6. Create partial index for LangGraph events (excludes legacy events)
CREATE INDEX IF NOT EXISTS idx_events_langgraph 
ON events(block_id, created_at DESC) 
WHERE node_name IS NOT NULL;

-- 7. Add comments for documentation
COMMENT ON COLUMN events.node_name IS 
'LangGraph StateGraph node name (e.g., ValidateNomenclature, ClassifyTipologia). NULL for legacy events.';

COMMENT ON COLUMN events.state_snapshot IS 
'Lightweight snapshot of ValidationState at node transition. Contains only: overall_status, nomenclature_valid, geometry_valid, classification_method, validation_path_length. Excludes heavy fields like geometry_metadata.';

COMMENT ON INDEX idx_events_block_node_time IS 
'Covering index for Grafana timeline queries: WHERE block_id = $1 ORDER BY created_at. Performance target: <50ms for 100 blocks.';

COMMIT;
