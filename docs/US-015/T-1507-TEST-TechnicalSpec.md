# Technical Specification: T-1507-TEST

**Status:** ENRICHED — Ready for TDD-RED Phase  
**Date:** 2026-03-09  
**Author:** Staff Engineer + Tech Lead  
**Sprint:** US-015 Element Model Refactoring (Sprint 7)

---

## 1. Ticket Summary

- **Tipo:** TEST (Multi-layer Integration — Backend + Frontend)
- **Alcance:** E2E integration test verifying Upload → Agent Processing → Element API → Canvas Render flow
- **Story Points:** 3
- **Dependencias:**
  - ✅ T-1501-DB: Element schema migration applied
  - ✅ T-1502-INFRA: Storage path conventions implemented
  - ✅ T-1504-AGENT: Material extraction with 62 real stone types
  - ✅ T-1504-BACK: Element API endpoints (`GET /api/elements`, `GET /api/elements/{id}`)
  - ✅ T-1505-FRONT: Zod schemas + services + store for Element contract

---

## 2. Context & Design Decision

### Backlog Requirement vs Project Reality

**Backlog Statement:**  
> "Write Cypress test: Upload .3dm → Wait for processing → Verify canvas render"

**Project Reality:**  
- ✅ Backend uses **pytest** + FastAPI TestClient (`tests/integration/`)
- ✅ Frontend uses **Vitest** + @testing-library/react (`src/frontend/src/tests/`)
- ❌ **Cypress is NOT installed** in the project
- ❌ **No e2e/ folder** exists
- ⚠️ `readme-official.md` mentions Playwright (10% E2E tests) but not configured either

### Architectural Decision: Multi-Layer Integration Testing

**RECOMMENDED APPROACH (Pragmatic, TDD-Compatible):**

Instead of installing a new E2E testing framework (Cypress/Playwright) which would require:
- New dependencies (~150MB node_modules)
- Docker service configuration
- CI/CD pipeline updates
- Learning curve for maintenance

We implement **two complementary integration test suites**:

#### **Backend Integration Test** (`tests/integration/test_element_e2e_flow.py`)
- Uses existing **pytest** + **FastAPI TestClient** infrastructure
- Verifies **Upload → Celery Processing → Element API** pipeline
- Uses **Celery eager mode** (conftest.py fixture) for synchronous execution
- Real database interactions via Supabase
- Real file processing with `tests/fixtures/test-model.3dm`

#### **Frontend Integration Test** (`src/frontend/src/tests/integration/element-canvas-integration.test.tsx`)
- Uses existing **Vitest** + **@testing-library/react** infrastructure
- Verifies **Element API response → Canvas 3D rendering**
- Uses **MSW (Mock Service Worker)** for API mocking
- Tests material color mapping (62 MATERIAL_COLORS)
- Tests bbox positioning logic

**Coverage Equivalence:**

```
┌─────────────────────────────────────────────────────────────────┐
│         Cypress E2E Test (Hypothetical)                         │
│  [Upload] → [Wait] → [API Call] → [Canvas Render]              │
└─────────────────────────────────────────────────────────────────┘
                            ↓ SPLIT INTO ↓
┌──────────────────────────────────────────┐ ┌───────────────────┐
│  Backend Integration Test (pytest)       │ │ Frontend Test     │
│  [Upload] → [Celery] → [DB] → [API]     │ │ [Mock API] → [3D] │
└──────────────────────────────────────────┘ └───────────────────┘
```

**Advantages:**
1. ✅ No new dependencies or infrastructure
2. ✅ Runs in existing CI/CD pipeline (no changes needed)
3. ✅ TDD-compatible (RED→GREEN→REFACTOR workflow)
4. ✅ Faster execution (<10s vs ~30s for Cypress)
5. ✅ Easier debugging (Python/JS native tools)
6. ✅ Maintains project consistency

**Trade-offs:**
- ❌ No visual browser testing (screenshots, video recording)
- ❌ No real DOM interaction (click, drag, keyboard)
- ⚠️ Frontend test uses mocked API (not real backend)

**Future Enhancement (Post-MVP):**  
If visual E2E testing becomes critical, install **Playwright** (mentioned in readme-official.md) and create `e2e/` folder as a separate epic.

---

## 3. Data Structures & Contracts

### Backend Schema (Already Implemented — T-1504-BACK)

```python
# src/backend/schemas.py (EXISTING)
from pydantic import BaseModel, HttpUrl, validator
from typing import List, Optional
from enum import Enum
from .constants import MATERIAL_COLORS

class ElementStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR_PROCESSING = "error_processing"
    IN_FABRICATION = "in_fabrication"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class BoundingBox(BaseModel):
    min: List[float]  # [x, y, z]
    max: List[float]  # [x, y, z]

class Element(BaseModel):
    """Schema optimizado para renderizado 3D"""
    id: str
    iso_code: str
    status: ElementStatus
    material_type: str                 # Validated against 62 materials
    low_poly_url: Optional[HttpUrl]    # Nullable (async processing)
    bbox: Optional[BoundingBox]        # Nullable (async processing)
    
    @validator('material_type')
    def validate_material(cls, v):
        if v not in MATERIAL_COLORS:
            raise ValueError(f"Invalid material: {v}")
        return v

class ElementsListResponse(BaseModel):
    elements: List[Element]
    meta: dict  # { total: int, filtered: int }
```

### Frontend Types (Already Implemented — T-1505-FRONT)

```typescript
// src/frontend/src/types/elements.ts (EXISTING)
export type MaterialType = keyof typeof MATERIAL_COLORS;

export enum ElementStatus {
  Uploaded = "uploaded",
  Processing = "processing",
  Validated = "validated",
  Rejected = "rejected",
  ErrorProcessing = "error_processing",
  InFabrication = "in_fabrication",
  Completed = "completed",
  Archived = "archived",
}

export interface BoundingBox {
  min: [number, number, number];
  max: [number, number, number];
}

export interface Element {
  id: string;
  iso_code: string;
  status: ElementStatus;
  material_type: string;
  low_poly_url: string;
  bbox: BoundingBox;
}

export interface ElementsListResponse {
  elements: Element[];
  meta: {
    total: number;
    filtered: number;
  };
}
```

### Test Fixture Data

```python
# tests/fixtures/test-model.3dm (EXISTING)
# Valid Rhino .3dm file with UserString "Codi" set to valid ISO code
# Expected UserStrings (from T-1503-AGENT):
#   - "Codi": "GLPER.B-PAE0720.0701" (or similar Sagrada Familia format)
#   - "Material": "Montjuïc" (or one of 62 valid materials)
# File size: ~10KB (simple geometry for fast processing)
# Contains valid 3D geometry for GLB generation
```

---

## 4. API Interface (Already Implemented)

### Upload Flow (US-001 — Already Working)

**Step 1: Generate Presigned URL**
- **Endpoint:** `POST /api/upload/url`
- **Auth:** Public (no auth required for upload)
- **Request:**
  ```json
  {
    "filename": "test-model.3dm",
    "size": 10240,
    "checksum": "sha256:abc123..."
  }
  ```
- **Response 200:**
  ```json
  {
    "upload_url": "https://xxxxxxxxxxxxxxxxxxx.supabase.co/storage/v1/object/...",
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "test-model.3dm"
  }
  ```

**Step 2: Confirm Upload (Triggers Celery Task)**
- **Endpoint:** `POST /api/upload/confirm`
- **Auth:** Public
- **Request:**
  ```json
  {
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_key": "raw-uploads/test-model.3dm"
  }
  ```
- **Response 200:**
  ```json
  {
    "success": true,
    "event_id": "evt_123",
    "task_id": "task_456"
  }
  ```

### Element Retrieval (T-1504-BACK — Already Working)

**Step 3: List Elements**
- **Endpoint:** `GET /api/elements?status=validated`
- **Auth:** Optional (service role for full access, workshop user for scoped access)
- **Response 200:**
  ```json
  {
    "elements": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "iso_code": "GLPER.B-PAE0720.0701",
        "status": "validated",
        "material_type": "Montjuïc",
        "low_poly_url": "https://xxxxxxxxxxxxxxxxxxx.supabase.co/storage/v1/object/models/low-poly/550e8400_20260309T120000Z.glb",
        "bbox": {
          "min": [-0.5, -0.5, 0.0],
          "max": [0.5, 0.5, 1.0]
        }
      }
    ],
    "meta": {
      "total": 1,
      "filtered": 1
    }
  }
  ```

**Step 4: Get Element Detail**
- **Endpoint:** `GET /api/elements/{element_id}`
- **Auth:** Optional
- **Response 200:**
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "iso_code": "GLPER.B-PAE0720.0701",
    "status": "validated",
    "material_type": "Montjuïc",
    "low_poly_url": "https://...",
    "bbox": { "min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 1.0] },
    "validation_report": {
      "is_valid": true,
      "errors": [],
      "metadata": {
        "user_strings": { "Codi": "GLPER.B-PAE0720.0701", "Material": "Montjuïc" }
      }
    },
    "rhino_metadata": { "layers": [...], "objects": [...] },
    "created_at": "2026-03-09T12:00:00Z",
    "updated_at": "2026-03-09T12:05:00Z"
  }
  ```

---

## 5. Component Contract (Frontend Test)

### Component Under Test
- **Component Name:** `Dashboard3D` + `ModelLoader` (integration)
- **Files:**
  - `src/frontend/src/components/Dashboard3D.tsx` (existing)
  - `src/frontend/src/components/ModelLoader.tsx` (existing)
  - `src/frontend/src/services/elements.service.ts` (T-1505-FRONT)
  - `src/frontend/src/stores/elements.store.ts` (T-1505-FRONT)

### Test Scenario Structure

```typescript
// Test file: src/frontend/src/tests/integration/element-canvas-integration.test.tsx

describe('Element Canvas Integration (T-1507-TEST)', () => {
  it('HP-INT-01: renders element in 3D canvas with correct material color', async () => {
    // GIVEN: Mock API returns element with material "Montjuïc"
    // WHEN: Dashboard3D component mounts
    // THEN: Canvas renders mesh with RGB [230, 180, 100]
  });

  it('HP-INT-02: positions element using bbox center', async () => {
    // GIVEN: Element has bbox { min: [-0.5, -0.5, 0], max: [0.5, 0.5, 1] }
    // WHEN: ModelLoader calculates position
    // THEN: Mesh positioned at [0, 0, 0.5] (center of bbox)
  });

  it('EC-INT-01: handles element with null low_poly_url gracefully', async () => {
    // GIVEN: Element has low_poly_url: null (still processing)
    // WHEN: Canvas attempts to render
    // THEN: Shows loading spinner, no crash
  });

  it('ERR-INT-01: displays error message for invalid material_type', async () => {
    // GIVEN: API returns invalid material "Wood"
    // WHEN: Zod validation runs
    // THEN: Error boundary shows user-friendly message
  });
});
```

### Mock Service Worker Setup

```typescript
// src/frontend/src/tests/mocks/handlers.ts (NEW FILE)
import { http, HttpResponse } from 'msw';
import { MATERIAL_COLORS } from '../../constants/materials';

export const handlers = [
  http.get('/api/elements', () => {
    return HttpResponse.json({
      elements: [
        {
          id: '550e8400-e29b-41d4-a716-446655440000',
          iso_code: 'GLPER.B-PAE0720.0701',
          status: 'validated',
          material_type: 'Montjuïc',
          low_poly_url: 'https://example.com/test.glb',
          bbox: {
            min: [-0.5, -0.5, 0.0],
            max: [0.5, 0.5, 1.0]
          }
        }
      ],
      meta: { total: 1, filtered: 1 }
    });
  }),

  http.get('/api/elements/:id', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      iso_code: 'GLPER.B-PAE0720.0701',
      status: 'validated',
      material_type: 'Montjuïc',
      low_poly_url: 'https://example.com/test.glb',
      bbox: { min: [-0.5, -0.5, 0.0], max: [0.5, 0.5, 1.0] },
      validation_report: { is_valid: true, errors: [] },
      rhino_metadata: {},
      created_at: '2026-03-09T12:00:00Z',
      updated_at: '2026-03-09T12:05:00Z'
    });
  })
];
```

---

## 6. Test Cases Checklist

### Backend Integration Tests (`tests/integration/test_element_e2e_flow.py`)

#### Happy Path (Upload → Process → Verify)
- [ ] **HP-BE-01:** Upload .3dm file → Confirm upload → Task returns success → Element created in DB
- [ ] **HP-BE-02:** Verify Element has `material_type` from MATERIAL_COLORS (62 valid materials)
- [ ] **HP-BE-03:** Verify Element has `low_poly_url` with HTTPS absolute URL
- [ ] **HP-BE-04:** Verify Element has `bbox` with structure `{min: [x,y,z], max: [x,y,z]}`
- [ ] **HP-BE-05:** Verify Element `iso_code` matches UserString "Codi" from .3dm file
- [ ] **HP-BE-06:** Verify `GET /api/elements` returns the processed element
- [ ] **HP-BE-07:** Verify `GET /api/elements/{id}` returns full element detail

#### Edge Cases
- [ ] **EC-BE-01:** Upload file with missing UserString "Codi" → Agent assigns PENDING iso_code
- [ ] **EC-BE-02:** Upload file with invalid material → Agent defaults to "Montjuïc"
- [ ] **EC-BE-03:** Query `GET /api/elements` before processing complete → Returns empty list (application-level filter excludes null low_poly_url)
- [ ] **EC-BE-04:** Query with invalid UUID → Returns 400 Bad Request

#### Error Handling
- [ ] **ERR-BE-01:** Confirm upload with non-existent file_key → Returns 404
- [ ] **ERR-BE-02:** Confirm upload with invalid file_id format → Returns 422 Validation Error
- [ ] **ERR-BE-03:** Upload file > 500MB → Rejected at presigned URL generation

#### Integration / Infrastructure
- [ ] **INT-BE-01:** Verify Celery task completes within timeout (540s soft, 600s hard)
- [ ] **INT-BE-02:** Verify database transaction rollback on processing error
- [ ] **INT-BE-03:** Verify storage cleanup on failed processing (delete temp files)

### Frontend Integration Tests (`src/frontend/src/tests/integration/element-canvas-integration.test.tsx`)

#### Happy Path (API → Canvas Render)
- [ ] **HP-FE-01:** Render element with material "Montjuïc" → Mesh has RGB color [230, 180, 100]
- [ ] **HP-FE-02:** Position mesh using `bbox.center` → Mesh at [(min.x+max.x)/2, (min.y+max.y)/2, (min.z+max.z)/2]
- [ ] **HP-FE-03:** Load GLB model from `low_poly_url` → useGLTF hook fetches successfully
- [ ] **HP-FE-04:** Display element `iso_code` in UI overlay → Text matches API response

#### Edge Cases
- [ ] **EC-FE-01:** Element with `low_poly_url: null` → Shows loading spinner, no render attempt
- [ ] **EC-FE-02:** Element with `bbox: null` → Uses default position [0, 0, 0]
- [ ] **EC-FE-03:** Material type not in MATERIAL_COLORS → Falls back to default color
- [ ] **EC-FE-04:** API returns empty elements array → Shows "No elements found" message

#### Error Handling
- [ ] **ERR-FE-01:** API returns 500 error → Error boundary displays user-friendly message
- [ ] **ERR-FE-02:** Zod validation fails (invalid material_type) → ElementApiError thrown
- [ ] **ERR-FE-03:** GLB file 404 → ModelLoader shows error placeholder

#### Integration / Performance
- [ ] **INT-FE-01:** Load 10 elements → All render within 3 seconds
- [ ] **INT-FE-02:** Verify Zustand store updates after API call → `elements` state populated
- [ ] **INT-FE-03:** Verify MATERIAL_COLORS dictionary matches backend (62 entries)

### Full Test Suite Baseline Verification
- [ ] **BASELINE-01:** Run backend test suite → 119/119 PASS (no regression)
- [ ] **BASELINE-02:** Run frontend test suite → 38/38 Element tests PASS + existing tests (365+/407 target 90%+)
- [ ] **BASELINE-03:** Run agent test suite → 37/37 PASS (no regression from new material extraction)

---

## 7. Files to Create/Modify

### Create (8 new files)

**Backend Tests (4 files):**
1. `tests/integration/test_element_e2e_flow.py` (~350 lines)
   - Class `TestElementE2EFlow` with 12 backend integration tests
   - Helper functions: `_upload_test_file()`, `_wait_for_processing()`, `_verify_element_contract()`

2. `tests/integration/test_element_api_contract.py` (~200 lines)
   - Class `TestElementAPIContract` with 7 API contract tests
   - Verifies Pydantic schema alignment

3. `tests/fixtures/helpers.py` (~100 lines)
   - Reusable helpers: `upload_and_confirm()`, `cleanup_test_elements()`

4. `tests/integration/test_material_colors_sync.py` (~80 lines)
   - Verifies MATERIAL_COLORS dictionary consistency backend ↔ frontend

**Frontend Tests (4 files):**
5. `src/frontend/src/tests/integration/element-canvas-integration.test.tsx` (~400 lines)
   - 12 frontend integration tests with MSW mocking

6. `src/frontend/src/tests/mocks/handlers.ts` (~150 lines)
   - MSW request handlers for `/api/elements` endpoints

7. `src/frontend/src/tests/mocks/server.ts` (~30 lines)
   - MSW server setup for Vitest

8. `src/frontend/src/tests/helpers/element-helpers.ts` (~80 lines)
   - Test utilities: `mockElement()`, `waitForCanvas()`, `getRenderedMeshes()`

### Modify (6 existing files)

**Backend:**
1. `tests/conftest.py` → Add fixture `cleanup_test_elements_fixture()` for teardown
2. `tests/integration/test_celery_worker.py` → Add test for new material extraction task

**Frontend:**
3. `src/frontend/vitest.config.ts` → Configure MSW setup file
4. `src/frontend/src/tests/setup.ts` → Import MSW server initialization
5. `src/frontend/src/components/Dashboard3D.test.tsx` → Update assertions for Element contract (replacing old Part contract)
6. `src/frontend/src/components/ModelLoader.test.tsx` → Update material color assertions (62 materials)

**Documentation:**
7. `docs/09-mvp-backlog.md` → Update T-1507-TEST status to [DONE] after completion
8. `memory-bank/activeContext.md` → Register T-1507-TEST completion

---

## 8. Reusable Components/Patterns

### Backend Patterns (Already Established)

**Pattern 1: FastAPI TestClient Integration**
```python
# tests/integration/test_upload_flow.py (EXISTING)
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_endpoint_integration():
    response = client.post("/api/endpoint", json={...})
    assert response.status_code == 200
```
**Reuse for:** `test_element_e2e_flow.py` — Same pattern for Element API calls

**Pattern 2: Celery Eager Mode (Synchronous Testing)**
```python
# tests/conftest.py (EXISTING)
@pytest.fixture(scope="function", autouse=True)
def celery_eager_mode():
    celery_app.conf.task_always_eager = True  # Makes .delay() synchronous
    yield
    celery_app.conf.task_always_eager = False
```
**Reuse for:** `test_element_e2e_flow.py` — No changes needed (autouse fixture)

**Pattern 3: Supabase Cleanup Helper**
```python
# tests/integration/test_confirm_upload_enqueue.py (EXISTING)
def _cleanup_pending_blocks(supabase_client, iso_prefix: str):
    supabase_client.table("blocks").delete().like(
        "iso_code", f"PENDING-{iso_prefix}%"
    ).execute()
```
**Reuse for:** `test_element_e2e_flow.py` — Extend to `_cleanup_test_elements(file_id)`

### Frontend Patterns (Already Established)

**Pattern 4: MSW API Mocking**
```typescript
// src/frontend/src/tests/integration/viewer-integration.test.tsx (US-010)
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  http.get('/api/parts/:id', () => {
    return HttpResponse.json({ id: '123', ... });
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```
**Reuse for:** `element-canvas-integration.test.tsx` — Same pattern for Element API

**Pattern 5: Three.js Mock (Canvas Testing)**
```typescript
// src/frontend/src/tests/setup.ts (EXISTING)
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: any) => <div data-testid="canvas">{children}</div>,
  useFrame: vi.fn(),
  useThree: vi.fn(() => ({ camera: {}, scene: {} }))
}));
```
**Reuse for:** `element-canvas-integration.test.tsx` — No changes needed (global mock)

**Pattern 6: Zustand Store Testing**
```typescript
// src/frontend/src/stores/elements.store.ts (T-1505-FRONT)
import { create } from 'zustand';

export const useElementsStore = create<ElementsStore>((set) => ({
  elements: [],
  loadElements: async () => {
    const data = await fetchElements();
    set({ elements: data.elements });
  }
}));

// In test:
const { loadElements, elements } = useElementsStore.getState();
await loadElements();
expect(elements).toHaveLength(1);
```
**Reuse for:** `element-canvas-integration.test.tsx` — Test store updates

---

## 9. Technical Constraints & Assumptions

### Constraints
1. **No Cypress/Playwright:** Maintain project consistency (pytest + Vitest only)
2. **Celery Eager Mode:** Tests run synchronously, no real background worker
3. **Storage Limits:** Test fixture `test-model.3dm` must be < 500MB (current: ~10KB ✅)
4. **Timeout:** Celery tasks must complete within 600s (hard limit)
5. **Database State:** Tests must cleanup after themselves (no test pollution)

### Assumptions
1. **MATERIAL_COLORS Sync:** Frontend constants match backend exactly (verified in INT-FE-03)
2. **Fixture Validity:** `tests/fixtures/test-model.3dm` has valid UserStrings ("Codi", "Material")
3. **Storage Access:** Supabase Storage bucket `raw-uploads` exists and is writable
4. **Database Schema:** T-1501-DB migration applied (element_model schema)
5. **Agent Processing:** T-1504-AGENT material extraction works with 62 materials

### Performance Targets
- Backend test suite: < 60 seconds total
- Frontend test suite: < 30 seconds total
- Individual E2E test: < 15 seconds (upload → process → verify)

---

## 10. Definition of Done (DoD)

### Code Quality
- [ ] All test files follow project conventions (pytest: `test_*.py`, Vitest: `*.test.tsx`)
- [ ] 100% of test cases in checklist implemented
- [ ] No `pytest.skip()` or `test.skip()` without justification comment
- [ ] Clean Architecture: Test helpers extracted to separate modules
- [ ] Zero hardcoded credentials (use fixtures/env vars)

### Test Coverage
- [ ] Backend integration: 12/12 tests PASS
- [ ] Frontend integration: 12/12 tests PASS
- [ ] Baseline verification: Backend 119/119 ✅, Frontend 38/38 Element ✅
- [ ] Zero regressions in existing test suites

### Documentation
- [ ] Technical spec (this file) reviewed and approved
- [ ] Test case descriptions include Given/When/Then structure
- [ ] Complex test logic documented with inline comments
- [ ] README updated with instructions to run E2E tests

### Integration
- [ ] Tests run successfully in Docker (`make test`, `make test-front`)
- [ ] CI/CD pipeline passes (no new failures introduced)
- [ ] Test fixtures committed to Git (`tests/fixtures/test-model.3dm`)
- [ ] Mock server handlers documented

### Handoff
- [ ] `docs/09-mvp-backlog.md` updated (T-1507-TEST marked [DONE])
- [ ] `memory-bank/activeContext.md` updated (recently completed section)
- [ ] `memory-bank/progress.md` registered (Sprint 7 entry)
- [ ] `prompts.md` logged (ENRICH + RED + GREEN + REFACTOR phases)

---

## 11. Next Steps: TDD Workflow

This spec is ready for **TDD-RED Phase**. Use the following data:

```bash
=============================================
READY FOR TDD-RED PHASE - Copy these values:
=============================================
Ticket ID:       T-1507-TEST
Feature name:    Element E2E Integration Test
Key test cases:
  Backend:
    - HP-BE-01: Upload → Process → Element created
    - HP-BE-03: Verify low_poly_url HTTPS absolute
    - HP-BE-05: Verify iso_code matches UserString
    - EC-BE-03: Query before processing complete
    - ERR-BE-01: Confirm upload with non-existent file
  
  Frontend:
    - HP-FE-01: Render with correct material color
    - HP-FE-02: Position using bbox center
    - EC-FE-01: Handle null low_poly_url
    - ERR-FE-02: Zod validation failure
    - INT-FE-03: Verify MATERIAL_COLORS sync

Files to create:
  Backend:
    - tests/integration/test_element_e2e_flow.py
    - tests/integration/test_element_api_contract.py
    - tests/integration/test_material_colors_sync.py
    - tests/fixtures/helpers.py
  
  Frontend:
    - src/frontend/src/tests/integration/element-canvas-integration.test.tsx
    - src/frontend/src/tests/mocks/handlers.ts
    - src/frontend/src/tests/mocks/server.ts
    - src/frontend/src/tests/helpers/element-helpers.ts

Expected Behavior:
  1. Upload test-model.3dm via POST /api/upload/url + /confirm
  2. Celery processes file in eager mode (synchronous)
  3. Agent extracts material_type (62 materials), generates GLB
  4. Database creates element with low_poly_url + bbox
  5. GET /api/elements returns element with valid contract
  6. Frontend renders mesh with correct material color + position

Test Baseline:
  - Backend: 119 existing tests (maintain)
  - Frontend: 38 Element tests + 365+ general (maintain)
  - Agent: 37 tests (maintain)

DoD Verification:
  - 24 new tests created (12 backend + 12 frontend)
  - All tests PASS (0 FAILED)
  - Zero regression in baseline
  - Documentation updated (backlog + activeContext + prompts.md)
=============================================
```

---

## 12. Appendix: Alternative Approaches Considered

### Option A: Pure Playwright E2E (Rejected)

**Pros:**
- ✅ True browser testing with visual verification
- ✅ Records videos and screenshots for debugging
- ✅ Tests real user interactions (click, drag, keyboard)

**Cons:**
- ❌ Requires installing Playwright (~200MB dependencies)
- ❌ Need Docker service for headless browser
- ❌ CI/CD pipeline changes (new job, environment setup)
- ❌ Slower execution (~30-60s per test)
- ❌ Harder to debug (async timing issues)

**Verdict:** Deferred to post-MVP phase (separate epic)

### Option B: Hybrid (Playwright Visual + Existing Tests) (Rejected)

**Pros:**
- ✅ Best of both worlds (visual + fast unit tests)

**Cons:**
- ❌ Doubles maintenance burden (two test suites)
- ❌ Still requires Playwright setup

**Verdict:** Complexity outweighs benefits for MVP

### Option C: Multi-Layer Integration (SELECTED)

**Pros:**
- ✅ No new dependencies or infrastructure
- ✅ Runs in existing CI/CD without changes
- ✅ TDD-compatible (RED→GREEN→REFACTOR)
- ✅ Fast execution (<10s total)
- ✅ Easier debugging (Python/JS native tools)

**Cons:**
- ❌ No visual browser verification
- ❌ Frontend test uses mocked API (not real backend)

**Verdict:** Best fit for MVP scope and timeline

---

**End of Technical Specification**

**Status:** ✅ READY FOR TDD-RED PHASE  
**Next Action:** Create test files with failing assertions (Step 2/5: TDD-RED)
