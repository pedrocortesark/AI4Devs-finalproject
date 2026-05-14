-- Migration: Enable Realtime and RLS read policy for blocks table
-- Required for BlockIngestionStatus frontend component (Supabase Realtime)
-- Date: 2026-04-07

BEGIN;

-- 1. Enable REPLICA IDENTITY FULL so Realtime sends full row data on UPDATE/DELETE
ALTER TABLE blocks REPLICA IDENTITY FULL;

-- 2. Add blocks to the supabase_realtime publication
--    (required for postgres_changes subscriptions from the frontend)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime' AND tablename = 'blocks'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE blocks;
    END IF;
END $$;

-- 3. RLS policy: allow anon and authenticated roles to SELECT blocks
--    The frontend only reads, never writes — so SELECT only.
DROP POLICY IF EXISTS blocks_select_public ON blocks;
CREATE POLICY blocks_select_public ON blocks
    FOR SELECT
    TO anon, authenticated
    USING (true);

COMMIT;
