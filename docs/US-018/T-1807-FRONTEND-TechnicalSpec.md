# T-1807: Frontend Progress Indicator — Technical Specification

**Epic:** US-018 StateGraph+LLM MVP  
**Story Points:** 2 SP  
**Status:** ✅ Complete  
**Commit:** 8e45c9c  
**Branch:** `feature/US-018-T-1801-stategraph-setup`  

---

## 1. Overview

### Purpose
Provide real-time visual feedback to users during the LangGraph validation workflow by displaying progress through the 8-node StateGraph, tracking active steps, showing estimated completion time, and surfacing errors immediately.

### Key Features
- **Real-time progress tracking:** Subscribes to Supabase `events` table via Realtime API
- **8-step visual indicator:** Displays all StateGraph nodes from ExtractGeometry → MarkValidated/Rejected
- **ETA calculation:** Auto-calculates estimated time based on average duration of completed steps
- **Error surfacing:** Shows error messages immediately when nodes fail
- **Auto-close:** Drawer automatically closes 5 seconds after workflow completion
- **Custom UI:** No external libraries (no Ant Design) — uses Apple-inspired design system

### Architecture Decision
We chose **Zustand** over Redux for state management due to:
- Simpler boilerplate (1 file vs. 3+ for Redux)
- Better TypeScript integration
- Perfect fit for single-domain state (upload progress)
- No provider wrapper needed in React 18

---

## 2. Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React 18)                      │
├─────────────────────────────────────────────────────────────────┤
│  App.tsx                                                        │
│  └─> confirmUpload()                                            │
│       ├─> Query blocks table for block_id                       │
│       └─> setTrackingBlockId() → setIsDrawerOpen(true)          │
│                                                                  │
│  UploadDrawer                                                   │
│  ├─> useUploadProgressStore() [Zustand]                         │
│  ├─> useSupabaseEvents(blockId) [Realtime Subscription]         │
│  └─> <ProgressSteps steps={steps} currentStep={currentStep} />  │
├─────────────────────────────────────────────────────────────────┤
│  useSupabaseEvents Hook                                         │
│  └─> supabase.channel('upload-progress-{blockId}')              │
│       .on('postgres_changes', { event: 'INSERT', table: 'events' })│
│       .subscribe((payload) => handleEvent(payload.new))          │
│                                                                  │
│  handleEvent()                                                  │
│  ├─> Map EventType to StepStatus                                │
│  ├─> Get step index from node_name                              │
│  └─> updateStepStatus(index, status, errorMessage?)             │
├─────────────────────────────────────────────────────────────────┤
│  uploadProgress.store.ts [Zustand]                              │
│  ├─> steps: ProgressStep[8]                                     │
│  ├─> currentStep: number                                        │
│  ├─> status: UploadProgressStatus                               │
│  ├─> eta: number | null                                         │
│  └─> Actions:                                                   │
│       ├─> startProgress(blockId, filename)                      │
│       ├─> updateStepStatus(stepIndex, status, errorMessage?)    │
│       ├─> advanceToNextStep()                                   │
│       ├─> markCompleted(message)                                │
│       ├─> markFailed(message)                                   │
│       ├─> calculateETA()                                        │
│       └─> reset()                                               │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Realtime Subscription
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Supabase Cloud (PostgreSQL)                  │
├─────────────────────────────────────────────────────────────────┤
│  events table                                                   │
│  ├─> id (uuid, PK)                                              │
│  ├─> block_id (uuid, FK → blocks.id)                            │
│  ├─> event_type (EventType enum)                                │
│  ├─> node_name (text)                                           │
│  ├─> timestamp (timestamptz)                                    │
│  └─> details (jsonb)                                            │
│                                                                  │
│  Realtime Publication: ENABLED                                  │
│  RLS: ENABLED (authenticated users can SELECT)                  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ INSERT events
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  Backend (Python 3.11, FastAPI)                 │
├─────────────────────────────────────────────────────────────────┤
│  StateGraph Workflow                                            │
│  └─> @with_audit_trail decorator on each node                   │
│       └─> Emits events to Supabase events table                 │
│            (GRAPH_STARTED, NODE_ENTERED, NODE_COMPLETED, etc.)  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User uploads file** → `App.tsx` calls `confirmUpload(file_id, file_key)`
2. **Backend creates block** → New row in `blocks` table
3. **Frontend queries block_id** → `SELECT id FROM blocks WHERE url_original = file_key LIMIT 1`
4. **Drawer opens** → `setTrackingBlockId(blockId)`, `setIsDrawerOpen(true)`
5. **Store initializes** → `startProgress(blockId, filename)` creates 8 idle steps
6. **Hook subscribes** → `useSupabaseEvents(blockId)` connects to Realtime channel
7. **Backend emits events** → StateGraph nodes call `@with_audit_trail` → INSERT into `events`
8. **Realtime triggers** → Supabase sends `postgres_changes` notification to frontend
9. **Event handler updates store** → Maps EventType → StepStatus, updates step, calculates ETA
10. **UI rerenders** → ProgressSteps shows updated status, UploadDrawer shows ETA
11. **Workflow completes** → `markCompleted()` sets status='completed'
12. **Auto-close** → 5-second timer closes drawer

---

## 3. Component Structure

### 3.1 File Organization

```
src/frontend/src/
├── types/
│   └── upload.ts                           # TypeScript interfaces
│       ├── StepStatus type
│       ├── ProgressStep interface
│       ├── UploadProgressStatus type
│       └── UploadProgressState interface
│
├── constants/
│   └── stategraph.constants.ts             # StateGraph definitions
│       ├── STATEGRAPH_NODES: readonly array[8]
│       ├── NODE_LABELS: Record<StateGraphNode, string>
│       ├── EventType enum
│       ├── getStepIndexByNodeName(nodeName: string): number
│       └── createInitialSteps(): ProgressStep[]
│
├── stores/
│   ├── uploadProgress.store.ts             # Zustand store (main)
│   └── uploadProgress.store.test.ts        # Unit tests (16 tests)
│
├── hooks/
│   └── useSupabaseEvents.ts                # Realtime subscription hook
│
└── components/
    ├── ProgressSteps.tsx                   # 8-step visual indicator
    ├── ProgressSteps.test.tsx              # Unit tests (7 tests)
    └── UploadDrawer.tsx                    # Slide-in drawer container
```

### 3.2 Component Hierarchy

```
<UploadDrawer>                              [Container, Zustand consumer]
  ├─> useUploadProgressStore()              [State management]
  ├─> useSupabaseEvents(blockId)            [Realtime subscription]
  │
  ├─> <div overlay>                         [Click-to-close background]
  └─> <div drawer>                          [Slide-in panel]
      ├─> <div header>                      [Title + close button]
      │     └─> "Procesando archivo"
      │
      ├─> <div content>                     [Main scrollable area]
      │     ├─> {status === 'completed' && <div success-banner />}
      │     ├─> {eta && <div eta-display>Tiempo estimado: {formatETA(eta)}</div>}
      │     └─> <ProgressSteps steps={steps} currentStep={currentStep} />
      │
      └─> <div footer>                      [Block ID display]
            └─> "Block ID: {blockId}"
```

```
<ProgressSteps>                             [Presentational, no state]
  └─> steps.map((step, index) =>
        <div step-container key={index}>
          ├─> <div icon>
          │     {step.status === 'active' ? <Spinner /> : STEP_VISUALS[step.status].icon}
          │
          ├─> <div label>
          │     {step.label}
          │
          ├─> <div description>
          │     {getStatusDescription(step)}
          │
          └─> {step.completedAt && <div duration>
                {formatDuration(step.startedAt, step.completedAt)}
              </div>}
        </div>
      )
```

---

## 4. State Management

### 4.1 Zustand Store Interface

```typescript
// src/frontend/src/stores/uploadProgress.store.ts

export interface UploadProgressStore extends UploadProgressState {
  // Actions
  startProgress: (blockId: string, filename: string) => void;
  updateStepStatus: (stepIndex: number, status: StepStatus, errorMessage?: string) => void;
  advanceToNextStep: () => void;
  markCompleted: (message: string) => void;
  markFailed: (message: string) => void;
  calculateETA: () => void;
  reset: () => void;
}
```

### 4.2 State Shape

```typescript
export interface UploadProgressState {
  blockId: string | null;              // UUID from blocks table
  filename: string | null;             // User's original filename
  steps: ProgressStep[];               // Array of 8 steps (StateGraph nodes)
  currentStep: number;                 // Index 0-7
  status: UploadProgressStatus;        // 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
  startedAt: string | null;            // ISO timestamp when workflow started
  eta: number | null;                  // Estimated seconds to completion
  finalMessage?: string;               // Success/error message shown at end
}

export interface ProgressStep {
  index: number;                       // 0-7
  nodeName: string;                    // 'ExtractGeometry', 'ValidateNomenclature', etc.
  label: string;                       // Spanish UI label
  status: StepStatus;                  // 'idle' | 'active' | 'completed' | 'error' | 'warning'
  startedAt: string | null;            // ISO timestamp when step started
  completedAt: string | null;          // ISO timestamp when step finished
  errorMessage?: string;               // Error text if status='error'
}
```

### 4.3 Action Descriptions

#### startProgress(blockId, filename)
```typescript
set({
  blockId,
  filename,
  status: 'processing',
  startedAt: new Date().toISOString(),
  steps: createInitialSteps(),  // 8 steps with status='idle'
  currentStep: 0,
  eta: null
});
```

#### updateStepStatus(stepIndex, status, errorMessage?)
```typescript
const updatedSteps = [...current.steps];
const step = updatedSteps[stepIndex];

step.status = status;
if (status === 'active' && !step.startedAt) {
  step.startedAt = new Date().toISOString();
}
if (['completed', 'error', 'warning'].includes(status) && !step.completedAt) {
  step.completedAt = new Date().toISOString();
}
if (errorMessage) {
  step.errorMessage = errorMessage;
}

set({ steps: updatedSteps });
get().calculateETA();  // Recalculate ETA after each step update
```

#### advanceToNextStep()
```typescript
const next = get().currentStep + 1;
if (next < get().steps.length) {
  set({ currentStep: next });
}
```

#### markCompleted(message)
```typescript
set({
  status: 'completed',
  finalMessage: message,
  eta: 0
});
```

#### markFailed(message)
```typescript
set({
  status: 'error',
  finalMessage: message,
  eta: null
});
```

#### calculateETA()
```typescript
const completedSteps = steps.filter(s => s.status === 'completed');
if (completedSteps.length === 0) return;

const totalDuration = completedSteps.reduce((sum, step) => {
  if (step.startedAt && step.completedAt) {
    return sum + (new Date(step.completedAt).getTime() - new Date(step.startedAt).getTime());
  }
  return sum;
}, 0);

const avgDuration = totalDuration / completedSteps.length;
const remainingSteps = steps.length - currentStep - 1;
const etaMs = avgDuration * remainingSteps;

set({ eta: Math.ceil(etaMs / 1000) });  // Convert ms → seconds
```

#### reset()
```typescript
set(initialState);  // Return to factory defaults
```

---

## 5. Event Mapping

### 5.1 EventType → StepStatus Mapping

```typescript
// src/frontend/src/hooks/useSupabaseEvents.ts

function handleEvent(event: EventRecord) {
  const stepIndex = getStepIndexByNodeName(event.node_name);
  if (stepIndex === -1) return;  // Unknown node, skip
  
  const { updateStepStatus, advanceToNextStep, markCompleted, markFailed } = useUploadProgressStore.getState();

  switch (event.event_type) {
    case EventType.GRAPH_STARTED:
      // No-op, startProgress() already called
      break;

    case EventType.NODE_ENTERED:
      updateStepStatus(stepIndex, 'active');
      break;

    case EventType.NODE_COMPLETED:
      updateStepStatus(stepIndex, 'completed');
      advanceToNextStep();
      break;

    case EventType.NODE_FAILED:
      const errorMsg = event.details?.error || 'Error desconocido';
      updateStepStatus(stepIndex, 'error', errorMsg);
      markFailed(`Error en ${NODE_LABELS[event.node_name]}: ${errorMsg}`);
      break;

    case EventType.TRANSITION_CONDITIONAL:
      // If transitioning to MarkRejected, show warning
      if (event.details?.target_node === 'MarkRejected') {
        updateStepStatus(stepIndex, 'warning', 'Validación rechazada');
      }
      break;

    case EventType.FALLBACK_ACTIVATED:
      // Show warning icon on ClassifyTipologia step
      if (event.node_name === 'ClassifyTipologia') {
        updateStepStatus(stepIndex, 'warning', 'Usando clasificación por regex (fallback)');
      }
      break;

    case EventType.GRAPH_COMPLETED:
      markCompleted('¡Procesamiento completado exitosamente!');
      break;

    case EventType.GRAPH_FAILED:
      const failMsg = event.details?.error || 'El workflow falló';
      markFailed(failMsg);
      break;
  }
}
```

### 5.2 Event Examples from Backend

**Example 1: NODE_ENTERED (ExtractGeometry)**
```json
{
  "id": "12345678-1234-1234-1234-123456789012",
  "block_id": "abcd1234-5678-90ab-cdef-1234567890ab",
  "event_type": "NODE_ENTERED",
  "node_name": "ExtractGeometry",
  "timestamp": "2026-02-09T15:30:00.000Z",
  "details": {}
}
```

**Example 2: NODE_COMPLETED (ValidateNomenclature)**
```json
{
  "id": "22345678-1234-1234-1234-123456789012",
  "block_id": "abcd1234-5678-90ab-cdef-1234567890ab",
  "event_type": "NODE_COMPLETED",
  "node_name": "ValidateNomenclature",
  "timestamp": "2026-02-09T15:30:05.500Z",
  "details": {
    "nomenclature_errors": []
  }
}
```

**Example 3: NODE_FAILED (ValidateGeometry)**
```json
{
  "id": "32345678-1234-1234-1234-123456789012",
  "block_id": "abcd1234-5678-90ab-cdef-1234567890ab",
  "event_type": "NODE_FAILED",
  "node_name": "ValidateGeometry",
  "timestamp": "2026-02-09T15:30:08.200Z",
  "details": {
    "error": "2 geometry errors detected: [DEGENERATE_BREP, INVALID_BBOX]"
  }
}
```

**Example 4: FALLBACK_ACTIVATED (ClassifyTipologia)**
```json
{
  "id": "42345678-1234-1234-1234-123456789012",
  "block_id": "abcd1234-5678-90ab-cdef-1234567890ab",
  "event_type": "FALLBACK_ACTIVATED",
  "node_name": "ClassifyTipologia",
  "timestamp": "2026-02-09T15:30:12.000Z",
  "details": {
    "reason": "OpenAI circuit breaker OPEN (3 failures)",
    "fallback_method": "FALLBACK_REGEX"
  }
}
```

---

## 6. Integration Points

### 6.1 App.tsx Integration

**Location:** `src/frontend/src/App.tsx` (lines ~300-350)

**Added Imports:**
```typescript
import { UploadDrawer } from './components/UploadDrawer';
import { getSupabaseClient } from './services/supabase.client';
```

**Added State:**
```typescript
const [isDrawerOpen, setIsDrawerOpen] = useState(false);
const [trackingBlockId, setTrackingBlockId] = useState<string | null>(null);
```

**Modified handleConfirm():**
```typescript
async function handleConfirm() {
  try {
    // ... existing upload logic ...
    await confirmUpload(file_id, file_key);
    setFileKey(file_key);
    fetchParts();  // Refresh parts list
    
    // NEW: Query blocks table for block_id
    const supabase = getSupabaseClient();
    const { data: blocks, error: blockError } = await supabase
      .from('blocks')
      .select('id')
      .eq('url_original', file_key)
      .limit(1);
    
    if (blockError) {
      console.warn('Failed to fetch block ID:', blockError);
    } else if (blocks && blocks.length > 0) {
      setTrackingBlockId(blocks[0].id);
      setIsDrawerOpen(true);
    }
  } catch (drawerError) {
    console.warn('Failed to open progress drawer:', drawerError);
  }
}
```

**Added Drawer at End of JSX:**
```typescript
<UploadDrawer
  isOpen={isDrawerOpen}
  blockId={trackingBlockId}
  filename={selectedFile?.name ?? null}
  onClose={() => setIsDrawerOpen(false)}
/>
```

### 6.2 Supabase Realtime Subscription

**Hook:** `src/frontend/src/hooks/useSupabaseEvents.ts`

**Subscription Pattern:**
```typescript
useEffect(() => {
  if (!blockId) {
    return;  // No blockId → no subscription
  }

  const supabase = getSupabaseClient();
  const channel = supabase
    .channel(`upload-progress-${blockId}`)  // Unique channel per block
    .on(
      'postgres_changes',
      {
        event: 'INSERT',                     // Only listen for new events
        schema: 'public',
        table: 'events',
        filter: `block_id=eq.${blockId}`,    // Only events for this block
      },
      (payload) => {
        handleEvent(payload.new as EventRecord);
      }
    )
    .subscribe();

  // Cleanup on unmount or blockId change
  return () => {
    channel.unsubscribe();
  };
}, [blockId]);
```

**Channel Lifecycle:**
- **Created:** When `blockId` changes from `null` → UUID
- **Active:** During entire workflow (listening for INSERT events)
- **Destroyed:** When drawer closes or component unmounts

### 6.3 Backend Event Emission

**Decorator:** `@with_audit_trail` (from T-1805)

**Applied to:** All 8 StateGraph nodes

**Example Usage:**
```python
# src/agent/graph/graph.py

@with_audit_trail(
    event_type=EventType.NODE_ENTERED,
    node_name="ExtractGeometry"
)
def extract_geometry_node(state: ValidationState) -> ValidationState:
    # ... extraction logic ...
    return state
```

**Event Buffer:** Events are batched and flushed every 100ms to reduce Supabase API calls.

---

## 7. Testing Strategy

### 7.1 Test Coverage

| Component | Tests | File | Status |
|-----------|-------|------|--------|
| **uploadProgress.store** | 16 | `uploadProgress.store.test.ts` | ✅ All PASS |
| **ProgressSteps** | 7 | `ProgressSteps.test.tsx` | ✅ All PASS |
| **Total** | **23** | — | **100% PASS** |

### 7.2 Store Unit Tests (16 tests)

**File:** `src/frontend/src/stores/uploadProgress.store.test.ts`

**Test Categories:**

1. **Initialization (1 test)**
   - `should have correct initial state`

2. **startProgress() (1 test)**
   - `should set blockId, filename, and status to processing`

3. **updateStepStatus() (4 tests)**
   - `should update step status to active`
   - `should update step status to completed and set timestamp`
   - `should set error message when status is error`
   - `should handle warning status`

4. **advanceToNextStep() (2 tests)**
   - `should increment currentStep`
   - `should not advance beyond last step`

5. **markCompleted() (1 test)**
   - `should set status to completed and finalMessage`

6. **markFailed() (1 test)**
   - `should set status to error and finalMessage`

7. **calculateETA() (3 tests)**
   - `should calculate ETA based on completed steps`
   - `should return 0 if no steps completed`
   - `should handle edge case of all steps completed`

8. **reset() (1 test)**
   - `should reset all state to initial values`

9. **Integration (2 tests)**
   - `should handle full happy path workflow`
   - `should handle error workflow with failed step`

**Example Test:**
```typescript
it('should update step status to completed and set timestamp', () => {
  const { result } = renderHook(() => useUploadProgressStore());
  
  // Arrange: Start progress
  act(() => {
    result.current.startProgress('block-123', 'test.3dm');
  });
  
  // Act: Mark first step as active, then completed
  act(() => {
    result.current.updateStepStatus(0, 'active');
  });
  
  const timestampBefore = new Date().toISOString();
  
  act(() => {
    result.current.updateStepStatus(0, 'completed');
  });
  
  // Assert: Step 0 should be completed with timestamp
  expect(result.current.steps[0].status).toBe('completed');
  expect(result.current.steps[0].completedAt).not.toBeNull();
  expect(new Date(result.current.steps[0].completedAt!).getTime())
    .toBeGreaterThanOrEqual(new Date(timestampBefore).getTime());
});
```

### 7.3 Component Unit Tests (7 tests)

**File:** `src/frontend/src/components/ProgressSteps.test.tsx`

**Test Categories:**

1. **Rendering (3 tests)**
   - `should render all 8 steps`
   - `should show completed status icon for completed step`
   - `should apply custom className`

2. **Status Display (3 tests)**
   - `should show "Procesando..." for active step`
   - `should show "Completado" description for completed steps`
   - `should show error message when step has error`

3. **Time Display (1 test)**
   - `should show duration for completed steps`

**Example Test:**
```typescript
it('should show error message when step has error', () => {
  const stepsWithError = createInitialSteps();
  stepsWithError[2].status = 'error';
  stepsWithError[2].errorMessage = 'Geometría inválida detectada';
  
  const { getByText } = render(
    <ProgressSteps steps={stepsWithError} currentStep={2} />
  );
  
  expect(getByText('Geometría inválida detectada')).toBeInTheDocument();
});
```

### 7.4 Manual Testing Checklist

**Scenario 1: Happy Path (All Steps Pass)**
- [ ] Upload a valid .3dm file with correct nomenclature
- [ ] Drawer opens immediately after confirmUpload
- [ ] All 8 steps transition from idle → active → completed
- [ ] ETA decreases as steps complete
- [ ] Drawer shows "¡Procesamiento completado exitosamente!" banner
- [ ] Drawer auto-closes after 5 seconds

**Scenario 2: Early Rejection (Invalid Nomenclature)**
- [ ] Upload a .3dm file with invalid name (e.g., `bad-name.3dm`)
- [ ] Drawer opens
- [ ] Steps 1-2 complete normally
- [ ] Step 2 (ValidateNomenclature) shows error status
- [ ] Drawer shows error message in finalMessage
- [ ] Remaining steps stay in idle state
- [ ] No auto-close (user must manually close)

**Scenario 3: Fallback Activation (OpenAI Timeout)**
- [ ] Trigger circuit breaker OPEN state (simulate 3 OpenAI failures)
- [ ] Upload a file
- [ ] Step 4 (ClassifyTipologia) shows warning icon
- [ ] Description shows "Usando clasificación por regex (fallback)"
- [ ] Workflow continues and completes successfully

**Scenario 4: Network Disconnection**
- [ ] Upload file, wait for workflow to start
- [ ] Disconnect network during processing
- [ ] Realtime subscription should retry automatically
- [ ] Reconnect network
- [ ] Drawer should resume showing updates (may miss some intermediate steps)

**Scenario 5: Multiple Uploads**
- [ ] Upload file A → drawer opens for block A
- [ ] Upload file B while A is processing → drawer switches to block B
- [ ] Verify blockId in footer matches file B
- [ ] Verify events for file A are not shown

---

## 8. Known Limitations

### 8.1 Technical Constraints

1. **No Retry Logic**
   - If a step fails, the workflow stops immediately
   - No automatic retry mechanism (future enhancement)
   - User must upload file again to retry

2. **Auto-Close Only on Success**
   - Drawer auto-closes after 5 seconds if `status === 'completed'`
   - If `status === 'error'`, drawer stays open indefinitely
   - User must manually click overlay or close button

3. **No Pause/Resume**
   - Once workflow starts, it cannot be paused
   - If user closes drawer, workflow continues in background
   - No way to cancel in-progress validation

4. **ETA Calculation Simplistic**
   - Uses average duration of completed steps × remaining steps
   - Doesn't account for varying node complexity
   - First step has no ETA (need at least 1 completed step)

5. **Single Block Tracking**
   - Only tracks one upload at a time
   - If user uploads multiple files, drawer shows most recent
   - No history of previous uploads (future: upload queue UI)

### 8.2 Edge Cases

1. **Rapid Upload + Close + Re-Open**
   - If user closes drawer and uploads new file quickly, Realtime channel may not unsubscribe fully
   - Old events might briefly appear
   - Mitigated by checking `blockId` in `handleEvent()`

2. **Backend Crashes Mid-Workflow**
   - Frontend has no heartbeat detection
   - Drawer will show last known step indefinitely
   - No timeout mechanism (future: 5-minute stale detection)

3. **Database RLS Blocking Events**
   - If user is unauthenticated or RLS policy changes, Realtime subscription will silently fail
   - No error shown to user (only console warning)
   - Future: Add connection health indicator

---

## 9. Future Enhancements

### 9.1 Planned Improvements (T-1809, T-1810)

1. **Agent Error Recovery (T-1809):**
   - Add retry logic with exponential backoff
   - Show "Retry" button on error steps
   - Track retry attempts in state

2. **Circuit Breaker Monitoring (T-1810):**
   - Add circuit breaker status indicator to ClassifyTipologia step
   - Show health metrics (failures, state, reset time)
   - Proactive warning before fallback activation

### 9.2 Long-Term Enhancements

1. **Upload Queue UI:**
   - Show list of all in-progress uploads
   - Switch between multiple workflows
   - Persistent history in localStorage

2. **Advanced ETA:**
   - Machine learning model trained on historical durations
   - Per-node complexity estimation
   - Confidence intervals

3. **Live Logs Panel:**
   - Expandable section showing raw event stream
   - Filter by event type
   - Export logs as JSON

4. **Notification System:**
   - Browser notifications when workflow completes
   - Email notifications for long-running workflows
   - Slack integration for team updates

5. **Performance Metrics:**
   - Show total workflow duration
   - Per-node duration breakdown
   - Historical comparison (this upload vs. average)

---

## 10. Code Examples

### 10.1 Using UploadDrawer in a Component

```typescript
import { useState } from 'react';
import { UploadDrawer } from '@/components/UploadDrawer';

function MyUploadPage() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [blockId, setBlockId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);

  async function handleUpload(file: File) {
    // 1. Upload file to Supabase Storage
    const { fileKey } = await uploadFile(file);
    
    // 2. Confirm upload → backend creates block
    await confirmUpload(fileKey);
    
    // 3. Query blocks table for block_id
    const { data: blocks } = await supabase
      .from('blocks')
      .select('id')
      .eq('url_original', fileKey)
      .limit(1);
    
    if (blocks && blocks.length > 0) {
      setBlockId(blocks[0].id);
      setFilename(file.name);
      setIsDrawerOpen(true);  // Open drawer → triggers Realtime subscription
    }
  }

  return (
    <div>
      <button onClick={() => handleUpload(selectedFile)}>
        Upload
      </button>
      
      <UploadDrawer
        isOpen={isDrawerOpen}
        blockId={blockId}
        filename={filename}
        onClose={() => setIsDrawerOpen(false)}
      />
    </div>
  );
}
```

### 10.2 Manually Updating Progress (For Testing)

```typescript
import { useUploadProgressStore } from '@/stores/uploadProgress.store';

function TestProgressButton() {
  const {
    startProgress,
    updateStepStatus,
    advanceToNextStep,
    markCompleted
  } = useUploadProgressStore();

  function simulateWorkflow() {
    // 1. Start
    startProgress('test-block-123', 'test-file.3dm');
    
    // 2. Simulate 8 steps
    setTimeout(() => updateStepStatus(0, 'active'), 500);
    setTimeout(() => updateStepStatus(0, 'completed'), 1000);
    setTimeout(() => advanceToNextStep(), 1000);
    
    setTimeout(() => updateStepStatus(1, 'active'), 1500);
    setTimeout(() => updateStepStatus(1, 'completed'), 2000);
    setTimeout(() => advanceToNextStep(), 2000);
    
    // ... repeat for steps 2-7 ...
    
    // 9. Mark completed
    setTimeout(() => markCompleted('¡Test exitoso!'), 10000);
  }

  return <button onClick={simulateWorkflow}>Simulate Workflow</button>;
}
```

### 10.3 Custom Event Handler (Advanced)

```typescript
import { useEffect } from 'react';
import { getSupabaseClient } from '@/services/supabase.client';
import { useUploadProgressStore } from '@/stores/uploadProgress.store';

function useCustomEventHandler(blockId: string | null) {
  const { updateStepStatus } = useUploadProgressStore();

  useEffect(() => {
    if (!blockId) return;

    const supabase = getSupabaseClient();
    const channel = supabase
      .channel(`custom-${blockId}`)
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'events',
        filter: `block_id=eq.${blockId}`,
      }, (payload) => {
        const event = payload.new;
        
        // Custom logic: Log all events
        console.log('[Custom Handler]', event);
        
        // Custom logic: Show browser notification on error
        if (event.event_type === 'NODE_FAILED') {
          new Notification('Upload Failed', {
            body: event.details?.error || 'Unknown error',
          });
        }
        
        // Still update store
        // ... (standard handleEvent logic)
      })
      .subscribe();

    return () => channel.unsubscribe();
  }, [blockId]);
}
```

---

## 11. References

### Related Documentation
- **T-1805: Audit Trail** — Event emission pattern
- **T-1806: E2E LangGraph Tests** — StateGraph workflow validation
- **CLAUDE.md** — Zustand over Redux decision
- **memory-bank/systemPatterns.md** — Supabase Realtime patterns

### External Resources
- [Zustand Documentation](https://docs.pmnd.rs/zustand/getting-started/introduction)
- [Supabase Realtime Guide](https://supabase.com/docs/guides/realtime)
- [TypeScript Strict Mode](https://www.typescriptlang.org/tsconfig#strict)

### Test Files
- `tests/fixtures/test-model03.3dm` — Valid .3dm file for integration testing
- `src/frontend/src/test/setup.ts` — Vitest global configuration

---

## 12. Changelog

| Date | Commit | Change |
|------|--------|--------|
| 2026-02-09 | 8e45c9c | Initial implementation (T-1807) |

---

**End of Technical Specification**
