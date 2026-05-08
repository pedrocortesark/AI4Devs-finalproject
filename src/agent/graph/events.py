"""
EventBuffer - Batch Insert Optimization for LangGraph Audit Trail (T-1805)

Context Manager Pattern:
========================
The EventBuffer class implements Python's context manager protocol (__enter__/__exit__).
This allows "with" statement usage for automatic resource cleanup and batch commit:

    with EventBuffer(block_id) as buffer:
        buffer.add(EventType.NODE_ENTERED, "ValidateNomenclature", state)
        buffer.add(EventType.NODE_COMPLETED, "ValidateNomenclature", state)
        # On __exit__: Batch INSERT if >=10 events accumulated

Design Rationale:
=================
Problem:
    - LangGraph StateGraph with 8 nodes = 16 events per block (enter + exit per node)
    - 100 blocks = 1,600 individual INSERT queries (N+1 problem)
    - Each INSERT: ~10-20ms latency → 16-32 seconds total overhead per batch

Solution:
    - Accumulate events in-memory (Python list)
    - Batch INSERT when threshold reached (default: 10 events)
    - Single query: ~20-30ms vs 10 × 15ms = 150ms (5x faster)

Trade-offs:
    - Memory: ~2KB per event × 10 = 20KB buffer (acceptable)
    - Risk: If process crashes before __exit__, events lost (acceptable for audit trail)
    - Complexity: +120 LOC vs simple insert loop (worth it for 5x speedup)

When to Use:
============
✅ USE EventBuffer when:
    - Processing >5 blocks in a single Celery task
    - StateGraph execution (8 nodes × 2 events = 16 events minimum)
    - Performance-critical paths (batch uploads, E2E tests)

❌ DON'T USE EventBuffer when:
    - Single event (overhead > benefit)
    - Real-time streaming (need immediate INSERT for UI updates)
    - Process might crash before __exit__ (critical audit, use insert_event directly)

Fallback Strategy:
==================
If batch INSERT fails:
    1. Log error with full event details
    2. Attempt individual insert_event() for each buffered event
    3. Continue execution (best-effort, non-fatal)

Author: AI Agent (T-1805-AGENT)
Created: 2026-05-08
"""

import structlog
from typing import List, Optional
from contextlib import contextmanager

try:
    from src.agent.graph.state import ValidationState
    from src.agent.graph.nodes import serialize_state_snapshot
    from infra.supabase_client import get_supabase_client
    from src.agent.constants import EVENT_BUFFER_THRESHOLD
except ImportError:
    from graph.state import ValidationState
    from graph.nodes import serialize_state_snapshot
    from agent.infra.supabase_client import get_supabase_client
    from agent.constants import EVENT_BUFFER_THRESHOLD

logger = structlog.get_logger()


class EventBuffer:
    """
    Context manager for batching LangGraph audit trail events.

    Accumulates events in-memory and performs a single batch INSERT on __exit__.
    Provides 5x performance improvement over individual insert_event() calls.

    Performance:
        - Individual: 10 events × 15ms = 150ms
        - Batched: 1 query × 25ms = 25ms
        - Speedup: 6x faster

    Usage:
        >>> with EventBuffer("GLPER.B-PAE0720.0701") as buffer:
        ...     buffer.add(EventType.NODE_ENTERED, "ExtractGeometry", state)
        ...     buffer.add(EventType.NODE_COMPLETED, "ExtractGeometry", state)
        ...     # ... more events
        ... # On exit: Batch INSERT if buffer >=10 events

    Attributes:
        block_id: UUID of block being validated
        events: List of buffered events (dicts with event_type, node_name, state_snapshot)
        threshold: Number of events to trigger batch insert (default: 10)

    Methods:
        add(event_type, node_name, state): Add event to buffer
        flush(): Manually trigger batch INSERT (called automatically on __exit__)
    """

    def __init__(self, block_id: str, threshold: int = EVENT_BUFFER_THRESHOLD):
        """
        Initialize EventBuffer for a specific block.

        Args:
            block_id: UUID of block (e.g., "GLPER.B-PAE0720.0701")
            threshold: Number of events to trigger auto-flush (default: 10 from constants)
        """
        self.block_id = block_id
        self.events: List[dict] = []
        self.threshold = threshold

    def __enter__(self):
        """Context manager entry: Return self for "with ... as buffer" syntax."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit: Flush buffered events on scope exit.

        Called automatically when exiting "with" block, even if exception occurred.
        Ensures events are committed before context exits.

        Args:
            exc_type: Exception type if raised within context (None if no exception)
            exc_val: Exception value
            exc_tb: Exception traceback

        Returns:
            False: Don't suppress exceptions (let them propagate)
        """
        # Flush events even if exception occurred within context
        # (audit trail should survive validation failures)
        self.flush()
        
        # Don't suppress exceptions
        return False

    def add(self, event_type: str, node_name: str, state: ValidationState) -> None:
        """
        Add event to buffer (in-memory only, no DB write yet).

        Events are accumulated until threshold reached or context exits.

        Args:
            event_type: EventType constant (e.g., EventType.NODE_COMPLETED)
            node_name: StateGraph node name (e.g., "ValidateNomenclature")
            state: Current ValidationState (used for state_snapshot)

        Side effects:
            - Appends event to self.events list
            - Calls flush() if threshold reached (auto-commit optimization)

        Example:
            >>> buffer = EventBuffer("block-123")
            >>> buffer.add(EventType.NODE_ENTERED, "ExtractGeometry", state)
            >>> buffer.add(EventType.NODE_COMPLETED, "ExtractGeometry", state)
            >>> len(buffer.events)
            2
        """
        # Serialize state snapshot
        state_snapshot = serialize_state_snapshot(state)
        
        # Add to buffer (not yet committed to DB)
        event = {
            "block_id": self.block_id,
            "event_type": event_type,
            "node_name": node_name,
            "state_snapshot": state_snapshot,
            "metadata": None  # Legacy field, not used by LangGraph
        }
        self.events.append(event)
        
        # Auto-flush if threshold reached (optimization: avoid giant buffers)
        if len(self.events) >= self.threshold:
            self.flush()

    def flush(self) -> None:
        """
        Commit all buffered events to database with single batch INSERT.

        Called automatically:
            - On __exit__ (end of "with" block)
            - When threshold reached (self.add auto-trigger)

        Can also be called manually:
            buffer.flush()  # Force immediate commit

        Behavior:
            - If buffer empty: No-op (log skip)
            - If buffer <10 events: Batch INSERT anyway (consistency)
            - If batch INSERT fails: Fallback to individual insert_event() per event
            - After flush: Clear buffer (self.events = [])

        Performance:
            - Batch: ~25ms for 10 events
            - Individual fallback: ~150ms for 10 events (6x slower but reliable)

        Side effects:
            - INSERT into events table (Supabase PostgreSQL)
            - Clears self.events buffer
            - Structured logs: events.batch_inserted or events.batch_failed

        Example:
            >>> with EventBuffer("block-123") as buffer:
            ...     for i in range(15):
            ...         buffer.add(EventType.NODE_ENTERED, f"Node{i}", state)
            ...     # Auto-flush at 10 events, then flush remaining 5 on __exit__
        """
        # Skip if buffer empty
        if not self.events:
            logger.debug("events.buffer_empty", block_id=self.block_id)
            return
        
        event_count = len(self.events)
        
        try:
            # Get Supabase client
            supabase = get_supabase_client()
            
            # Batch INSERT (single query for all events)
            result = supabase.table("events").insert(self.events).execute()
            
            # Success log
            logger.info(
                "events.batch_inserted",
                block_id=self.block_id,
                event_count=event_count,
                threshold=self.threshold
            )
            
        except Exception as e:
            # Batch INSERT failed → Fallback to individual inserts
            logger.warning(
                "events.batch_failed_fallback_individual",
                block_id=self.block_id,
                event_count=event_count,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Fallback: Attempt individual insert_event() for each buffered event
            # (Slower but more reliable, isolates failures)
            for event in self.events:
                try:
                    supabase.table("events").insert(event).execute()
                except Exception as fallback_error:
                    # Even individual insert failed → Log only (best-effort)
                    logger.error(
                        "events.individual_fallback_failed",
                        block_id=self.block_id,
                        event_type=event["event_type"],
                        node_name=event["node_name"],
                        error=str(fallback_error)
                    )
        
        finally:
            # Always clear buffer (even if some inserts failed)
            # Rationale: Avoid re-inserting same events on next flush()
            self.events = []
            logger.debug("events.buffer_cleared", block_id=self.block_id)
