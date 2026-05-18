-- Migration: Add pgvector + block_embeddings for RAG ("The Archivist")
-- Ticket: US-019 (RAG MVP) — Capa 2
-- Author: AI Assistant
-- Date: 2026-05-18
-- Purpose: Enable semantic search over blocks for the conversational RAG layer.
--
-- This migration adds:
--   1. pgvector extension (`vector`) — available on Supabase, not yet installed
--   2. block_embeddings table: one embedding per block (upsert by block_id),
--      ON DELETE CASCADE so admin reset-blocks / deletes also drop embeddings
--   3. match_blocks(query_embedding, match_count): cosine similarity search
--
-- MVP note: no ANN index (ivfflat/hnsw) — block counts are small (hundreds),
-- exact cosine scan is instant and more accurate. Add an ivfflat/hnsw index
-- later if the inventory grows large. RLS is intentionally NOT enabled:
-- block_embeddings is only read/written server-side via the service role
-- (backend) and the match_blocks function.
--
-- text-embedding-3-small → 1536 dimensions.

BEGIN;

-- 1. pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Embeddings table (one row per block)
CREATE TABLE IF NOT EXISTS block_embeddings (
    block_id   uuid PRIMARY KEY REFERENCES blocks(id) ON DELETE CASCADE,
    content    text NOT NULL,
    embedding  vector(1536) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE block_embeddings IS
'Semantic-search embeddings for the RAG layer (The Archivist). One row per block; '
'content is the natural-language summary that was embedded. Populated by '
'infra/generate_embeddings.py and consumed by POST /api/chat/ask via match_blocks().';

-- 3. Cosine similarity search function
CREATE OR REPLACE FUNCTION match_blocks(
    query_embedding vector(1536),
    match_count int DEFAULT 5
)
RETURNS TABLE (block_id uuid, content text, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT
        be.block_id,
        be.content,
        1 - (be.embedding <=> query_embedding) AS similarity
    FROM block_embeddings be
    ORDER BY be.embedding <=> query_embedding
    LIMIT match_count;
$$;

COMMENT ON FUNCTION match_blocks(vector, int) IS
'Returns the match_count blocks most similar (cosine) to query_embedding, '
'with similarity = 1 - cosine_distance.';

-- 4. Verify
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Migration failed: vector extension not installed';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'block_embeddings'
    ) THEN
        RAISE EXCEPTION 'Migration failed: block_embeddings table not created';
    END IF;
    RAISE NOTICE 'Migration successful: pgvector + block_embeddings + match_blocks';
END$$;

COMMIT;
