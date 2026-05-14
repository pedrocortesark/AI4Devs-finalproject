/**
 * useSupabaseEvents Hook - T-1807
 * 
 * Subscribes to Supabase Realtime events table changes
 * and updates the upload progress store accordingly.
 * 
 * Listens for INSERT events on the 'events' table filtered by block_id.
 */

import { useEffect, useRef } from 'react';
import { getSupabaseClient } from '../services/supabase.client';
import { useUploadProgressStore } from '../stores/uploadProgress.store';
import { 
  EventType, 
  getStepIndexByNodeName,
} from '../constants/stategraph.constants';

/**
 * Shape of an event record from the events table
 * (Matches backend src/backend/schemas.py EventCreate)
 */
interface EventRecord {
  id: string;
  block_id: string;
  event_type: string; // EventType enum value
  node_name: string | null;
  timestamp: string;
  details: Record<string, any> | null;
}

/**
 * Hook to subscribe to Supabase Realtime events for a specific block
 * 
 * @param blockId - The block UUID to listen for events (null = no subscription)
 * 
 * @example
 * ```tsx
 * function MyComponent() {
 *   const blockId = useUploadProgressStore(state => state.blockId);
 *   useSupabaseEvents(blockId);
 *   // Store will auto-update when events are received
 * }
 * ```
 */
export function useSupabaseEvents(blockId: string | null) {
  const channelRef = useRef<any>(null);
  const { updateStepStatus, advanceToNextStep, markCompleted, markFailed } = useUploadProgressStore();
  
  useEffect(() => {
    // No subscription if blockId is null
    if (!blockId) {
      return;
    }
    
    const supabase = getSupabaseClient();
    const channelName = `upload-progress-${blockId}`;
    
    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes' as any,
        {
          event: 'INSERT', // Only listen for new events
          schema: 'public',
          table: 'events',
          filter: `block_id=eq.${blockId}`,
        },
        (payload: any) => {
          const event = payload.new as EventRecord;
          if (!event) return;
          
          console.log('[useSupabaseEvents] Event received:', event);
          
          handleEvent(event);
        }
      )
      .subscribe((status: string) => {
        if (status === 'SUBSCRIBED') {
          console.log(`[useSupabaseEvents] Subscribed to events for block ${blockId}`);
        }
        if (status === 'CHANNEL_ERROR') {
          console.error('[useSupabaseEvents] Failed to connect to Realtime channel');
        }
      });
    
    channelRef.current = channel;
    
    // Cleanup on unmount or blockId change
    return () => {
      console.log(`[useSupabaseEvents] Unsubscribing from block ${blockId}`);
      channel.unsubscribe();
    };
  }, [blockId]);
  
  /**
   * Handle an event from Supabase and update the store
   */
  function handleEvent(event: EventRecord) {
    const eventType = event.event_type as EventType;
    const nodeName = event.node_name;
    
    switch (eventType) {
      case EventType.GRAPH_STARTED:
        console.log('[useSupabaseEvents] Graph started');
        // No specific action needed (progress already started)
        break;
      
      case EventType.NODE_ENTERED:
        if (nodeName) {
          const stepIndex = getStepIndexByNodeName(nodeName);
          if (stepIndex >= 0) {
            updateStepStatus(stepIndex, 'active');
          }
        }
        break;
      
      case EventType.NODE_COMPLETED:
        if (nodeName) {
          const stepIndex = getStepIndexByNodeName(nodeName);
          if (stepIndex >= 0) {
            updateStepStatus(stepIndex, 'completed');
            advanceToNextStep();
          }
        }
        break;
      
      case EventType.NODE_FAILED:
        if (nodeName) {
          const stepIndex = getStepIndexByNodeName(nodeName);
          const errorMessage = event.details?.error ?? 'Node failed';
          if (stepIndex >= 0) {
            updateStepStatus(stepIndex, 'error', errorMessage);
          }
        }
        break;
      
      case EventType.FALLBACK_ACTIVATED:
        if (nodeName) {
          const stepIndex = getStepIndexByNodeName(nodeName);
          const fallbackReason = event.details?.reason ?? 'Fallback activated';
          if (stepIndex >= 0) {
            updateStepStatus(stepIndex, 'warning', fallbackReason);
          }
        }
        break;
      
      case EventType.TRANSITION_CONDITIONAL:
        // Advance to next step (already handled by NODE_COMPLETED)
        console.log('[useSupabaseEvents] Conditional transition:', event.details);
        break;
      
      case EventType.GRAPH_COMPLETED:
        const finalStatus = event.details?.overall_status ?? 'validated';
        markCompleted(`Validación completada: ${finalStatus}`);
        break;
      
      case EventType.GRAPH_FAILED:
        const errorMsg = event.details?.error ?? 'Graph execution failed';
        markFailed(errorMsg);
        break;
      
      default:
        console.warn('[useSupabaseEvents] Unknown event type:', eventType);
    }
  }
}
