-- Grafana Timeline Query for LangGraph StateGraph Audit Trail
-- Ticket: T-1805-AGENT
-- Author: AI Assistant
-- Date: 2026-05-08
-- Purpose: Visualize StateGraph node execution timeline in Grafana dashboard
--
-- DASHBOARD CONFIGURATION:
-- Panel Type: Gantt Timeline (or Table with Time Series)
-- Refresh Rate: 30s (for real-time monitoring)
-- Data Source: PostgreSQL (Supabase connection)
-- Variables: $block_id (dropdown from blocks.id)
--
-- VISUALIZATION:
-- X-axis: created_at (timeline)
-- Y-axis: node_name (categorical)
-- Color: event_type (node_entered = blue, node_completed = green, transition_conditional = yellow)
-- Tooltip: state_snapshot (JSON formatted)
--
-- EXPECTED RESULT:
-- Gantt bars showing node execution duration
-- Happy path: 8 nodes × 2 events = 16 rows
-- Early rejection: 3 nodes × 2 events = 6 rows
-- Circuit breaker: +2 events (tripped + fallback)
-- Transitions: +3 events (conditional edges)

-- ═══════════════════════════════════════════════════════════════════════════
-- QUERY 1: Basic Timeline (All Events for Block)
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 
    node_name,
    event_type,
    state_snapshot->>'overall_status' AS status,
    state_snapshot->>'nomenclature_valid' AS nomenclature_ok,
    state_snapshot->>'geometry_valid' AS geometry_ok,
    state_snapshot->>'classification_method' AS classification,
    created_at
FROM events
WHERE block_id = $block_id  -- Grafana variable
ORDER BY created_at ASC;

-- Usage: Replace $block_id with actual UUID or use Grafana variable

-- ═══════════════════════════════════════════════════════════════════════════
-- QUERY 2: Node Execution Durations (Paired Enter/Exit Events)
-- ═══════════════════════════════════════════════════════════════════════════

WITH node_pairs AS (
    SELECT 
        node_name,
        MIN(CASE WHEN event_type = 'node_entered' THEN created_at END) AS entered_at,
        MAX(CASE WHEN event_type = 'node_completed' THEN created_at END) AS completed_at
    FROM events
    WHERE block_id = $block_id
        AND node_name IS NOT NULL
        AND event_type IN ('node_entered', 'node_completed')
    GROUP BY node_name
)
SELECT 
    node_name,
    entered_at,
    completed_at,
    EXTRACT(EPOCH FROM (completed_at - entered_at)) AS duration_seconds,
    CASE 
        WHEN completed_at IS NULL THEN 'INCOMPLETE'
        WHEN EXTRACT(EPOCH FROM (completed_at - entered_at)) > 10 THEN 'SLOW'
        ELSE 'OK'
    END AS performance_status
FROM node_pairs
ORDER BY entered_at ASC;

-- Expected durations:
-- ExtractGeometry: 2-5s (S3 download + rhino3dm parsing)
-- ClassifyTipologia: 3-8s (LLM API call)
-- ValidateNomenclature: <100ms
-- ValidateGeometry: <500ms
-- EnrichMetadata: <200ms
-- GenerateReport: <300ms (Jinja2 rendering)
-- MarkValidated/MarkRejected: <50ms

-- ═══════════════════════════════════════════════════════════════════════════
-- QUERY 3: Performance Metrics (Aggregate)
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 
    COUNT(DISTINCT block_id) AS total_blocks,
    COUNT(*) AS total_events,
    AVG(CASE 
        WHEN event_type IN ('node_entered', 'node_completed') 
        THEN 1 ELSE 0 
    END) * 100 AS pct_node_events,
    COUNT(CASE WHEN event_type = 'circuit_breaker_tripped' THEN 1 END) AS circuit_breaker_activations,
    COUNT(CASE WHEN event_type = 'fallback_activated' THEN 1 END) AS fallback_activations,
    MIN(created_at) AS earliest_event,
    MAX(created_at) AS latest_event
FROM events
WHERE created_at >= NOW() - INTERVAL '24 hours';

-- Dashboard metric tiles:
-- Total Blocks Processed (24h)
-- Circuit Breaker Activations
-- Fallback Usage Rate (%)
-- Event Volume (events/hour)

-- ═══════════════════════════════════════════════════════════════════════════
-- QUERY 4: Failed Validations (Early Rejections)
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 
    e.block_id,
    b.iso_code,
    COUNT(*) AS event_count,
    MIN(e.created_at) AS started_at,
    MAX(e.created_at) AS rejected_at,
    EXTRACT(EPOCH FROM (MAX(e.created_at) - MIN(e.created_at))) AS total_duration_seconds,
    MAX(e.state_snapshot->>'overall_status') AS final_status
FROM events e
LEFT JOIN blocks b ON e.block_id::text = b.id::text
WHERE e.created_at >= NOW() - INTERVAL '24 hours'
    AND EXISTS (
        SELECT 1 FROM events e2 
        WHERE e2.block_id = e.block_id 
            AND e2.node_name = 'MarkRejected'
    )
GROUP BY e.block_id, b.iso_code
HAVING COUNT(*) < 10  -- Less than 10 events = early rejection
ORDER BY rejected_at DESC;

-- Alert condition:
-- IF COUNT(event_count < 10) > 50 THEN 'High rejection rate - check nomenclature'

-- ═══════════════════════════════════════════════════════════════════════════
-- QUERY 5: Circuit Breaker Health Monitor
-- ═══════════════════════════════════════════════════════════════════════════

SELECT 
    DATE_TRUNC('hour', created_at) AS hour_bucket,
    COUNT(CASE WHEN event_type = 'circuit_breaker_tripped' THEN 1 END) AS cb_trips,
    COUNT(CASE WHEN event_type = 'fallback_activated' THEN 1 END) AS fallbacks,
    COUNT(CASE WHEN state_snapshot->>'classification_method' = 'llm_gpt4' THEN 1 END) AS llm_successes
FROM events
WHERE created_at >= NOW() - INTERVAL '7 days'
    AND node_name = 'ClassifyTipologia'
GROUP BY hour_bucket
ORDER BY hour_bucket DESC;

-- Alert thresholds:
-- cb_trips > 10/hour → OpenAI API degraded
-- fallbacks > 50/hour → High LLM failure rate
-- llm_successes < 100/hour → Circuit breaker stuck open

-- ═══════════════════════════════════════════════════════════════════════════
-- INDEX VERIFICATION (Performance Check)
-- ═══════════════════════════════════════════════════════════════════════════

-- Check if compound index is being used (should show Index Scan, not Seq Scan)
EXPLAIN ANALYZE
SELECT node_name, event_type, created_at
FROM events
WHERE block_id = '00000000-0000-0000-0000-000000000001'
ORDER BY created_at ASC;

-- Expected EXPLAIN output:
-- -> Index Scan using idx_events_block_node_time on events
-- Rows Removed by Filter: 0
-- Execution Time: <5ms (for 100 blocks)

-- If showing Seq Scan instead:
-- 1. Run VACUUM ANALYZE events;
-- 2. Check index exists: \d events (psql)
-- 3. Rebuild index: REINDEX INDEX idx_events_block_node_time;
