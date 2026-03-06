# Test Baseline - Before US-015

**Date:** 2026-03-06  
**Context:** Test suite status BEFORE starting US-015 implementation  
**Purpose:** Establish baseline to track regressions during Element model refactoring

---

## 📊 Test Results Summary

### Backend Tests (Python + pytest)
```bash
Command: make test-unit
Duration: 1.38s
```

**Results:**
- ✅ **108 tests PASSED**
- ⏭️  **1 test SKIPPED**
- ⚠️  **13 warnings** (Pydantic deprecations, gotrue deprecations)
- ❌ **0 tests FAILED**

**Success Rate:** 108/108 = **100%** 🎉

**Warnings (non-blocking):**
- Pydantic v2 class-based config deprecation (6 warnings in test_validation_schema_presence.py)
- gotrue package deprecation (use supabase_auth instead)

---

### Frontend Tests (Vitest)
```bash
Command: npm test -- --run
Duration: 47.08s
```

**Results:**
- ✅ **333 tests PASSED**
- ❌ **68 tests FAILED**
- ⏭️  **4 tests SKIPPED**
- 📝 **2 tests TODO**
- 🐛 **3 uncaught exceptions** (ModelLoader.test.tsx)

**Total Tests:** 407  
**Success Rate:** 333/407 = **81.8%**

**Known Issues (pre-existing):**
1. **ModelLoader.test.tsx failures:** 3 uncaught exceptions
   - Error: `[GLBModel] Scene is not a valid Three.js Object3D`
   - Tests affected: LOADING-02, CALLBACK-01, PROPS-02
   - Root cause: Three.js mocks in setup.ts not returning valid Object3D structure
   - Impact: Non-blocking for US-015 (3D viewer tests, not related to Element model)

2. **Other failing tests:** 65 additional failures (breakdown needed)
   - Run `npm test` to see detailed list
   - Most likely: Component tests with outdated mocks or props

---

## 🎯 US-015 Commitment

**Quality Gate:** Each ticket MUST maintain or improve test pass rates.

### Execution Strategy

**After each ticket implementation:**
1. ✅ Run backend tests: `make test-unit`
2. ✅ Run frontend tests: `cd src/frontend && npm test -- --run`
3. ✅ Document results in ticket HANDOFF document
4. ✅ Fix any NEW regressions before marking ticket as DONE

**Target Metrics:**
- Backend: Maintain **100% pass rate** (108/108) ✅
- Frontend: Improve towards **90%+ pass rate** (from 81.8%) 📈
  - Fix ModelLoader mocks during T-1505-FRONT (3D canvas refactoring)
  - Update component tests during T-1504-BACK and T-1505-FRONT (Element rename)

---

## 📋 Expected Regressions by Ticket

### T-1501-DB: Database Schema & Migration
**Expected Backend Impact:** 0 regressions (schema-only change)
**Expected Frontend Impact:** 0 regressions (no code changes yet)
**New Tests:** +5 migration tests

---

### T-1502-INFRA: Storage Path Conventions
**Expected Backend Impact:** 0 regressions (new function, not replacing existing)
**Expected Frontend Impact:** 0 regressions (backend-only change)
**New Tests:** +8 storage path tests

---

### T-1503-AGENT: Rhino Parser + GLB Generator
**Expected Backend Impact:** ~3-5 tests to update
- Tests that mock UserString extraction
- Tests that validate Rhino file structure
**Expected Frontend Impact:** 0 regressions
**New Tests:** +12 material_type extraction tests
**Action:** Update fixtures in `tests/fixtures/*.3dm` with material_type UserString

---

### T-1504-BACK: API Integration with Element Contract
**Expected Backend Impact:** ~30-40 tests to update ⚠️
- **Breaking change:** `PartCanvasItem` → `Element` rename
- All tests importing schemas.py
- All tests using PartCanvasItem fixtures
- All tests asserting on tipologia field
**Expected Frontend Impact:** 0 regressions (frontend not updated yet)
**New Tests:** +15 Element contract tests
**Action:** 
1. Global search/replace: `PartCanvasItem` → `Element`
2. Update fixtures: `tipologia="Piedra"` → `material_type="Stone"`
3. Update assertions: `part.tipologia` → `element.material_type`

---

### T-1505-FRONT: Zod Validation with Element Schemas
**Expected Backend Impact:** 0 regressions
**Expected Frontend Impact:** ~60-80 tests to update ⚠️
- **Breaking change:** Component interfaces renamed
- All tests importing types/parts.ts
- All tests using PartCanvasItem mocks
- All component tests with workshop_id/workshop_name props
**Expected Fixes:** ModelLoader.test.tsx failures (fix Three.js mocks)
**New Tests:** +20 Zod validation tests
**Action:**
1. Global search/replace: `PartCanvasItem` → `Element` in test files
2. Update mocks: Remove workshop fields, rename tipologia
3. Fix Three.js setup.ts mocks (resolve Object3D structure issue)
4. Update component snapshots if using snapshot testing

---

### T-1507-TEST: E2E Integration Test
**Expected Backend Impact:** 0 regressions (validation only)
**Expected Frontend Impact:** 0 regressions (validation only)
**New Tests:** +1 E2E test (upload → process → render with material_type)
**Final Check:** Run FULL test suite across backend + frontend
**Target:** Backend 100%, Frontend 90%+

---

## 🔧 Test Commands Quick Reference

```bash
# Backend (from project root)
make test-unit                          # Unit + integration tests
make test-unit-quick                    # Unit tests only (faster)
docker compose run --rm backend pytest tests/unit/test_parts_service.py -v  # Single file

# Frontend (from src/frontend/)
npm test                                # Watch mode
npm test -- --run                       # Run once, exit
npm test -- --run src/components/Dashboard3D.test.tsx  # Single file
npm test -- --run --coverage            # With coverage report

# Full suite (from project root)
make test                               # Backend + Frontend (if configured)
```

---

## 📈 Success Criteria

**US-015 will be considered successful if:**
1. ✅ Backend tests: **108/108 passing** (maintain 100%)
2. ✅ Frontend tests: **≥365/407 passing** (improve to ≥90%)
3. ✅ ModelLoader.test.tsx: **3 uncaught exceptions FIXED** (during T-1505-FRONT)
4. ✅ Zero new test failures introduced by Element model refactoring
5. ✅ All contract tests (JSON-CONTRACTS.md) implemented and passing

**Acceptable exceptions:**
- Tests that explicitly test deprecated features (workshop_id, tipologia string)
- Tests marked as TODO or skipped before US-015 (4 skipped + 2 TODO = keep as-is)

---

## 📝 Test Baseline Archive

This document serves as the **reference baseline** for US-015. Any ticket that causes test regressions below this baseline will be **BLOCKED** until fixed.

**Next Update:** After T-1501-DB completion (track progress ticket-by-ticket)

---

**Last Updated:** 2026-03-06 00:56  
**Baseline Snapshot ID:** `pre-us015-20260306`  
**Git Commit:** (Document commit hash when US-015 branch is created)
