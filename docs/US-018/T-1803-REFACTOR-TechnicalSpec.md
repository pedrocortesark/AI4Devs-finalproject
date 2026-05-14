# T-1803: Refactor Existing Validators as LangGraph Nodes

**Ticket:** US-018/T-1803  
**Story Points:** 3 SP  
**Duration:** 3 días (20 horas)  
**Status:** ✅ COMPLETED  
**Branch:** `feature/US-018-T-1801-stategraph-setup`

---

## 1. Context

**Problem Statement:**  
T-1801 created 8 StateGraph nodes with **stub implementations** (placeholders returning hard-coded success). US-002 has **production-ready validators** (NomenclatureValidator, GeometryValidator, UserStringExtractor) with 26 passing tests. T-1803 must **refactor 4 stub nodes** to call real validators **without modifying US-002 code** (zero regression requirement).

**Constraints:**
- **Zero Regression:** 26 US-002 tests must continue to PASS (validators 100% unchanged)
- **Testability:** Validators must remain usable independently (outside StateGraph)
- **LangGraph Integration:** Nodes must return partial state updates (dicts), not full objects
- **Fail-Fast:** Invalid nomenclature/geometry should skip downstream nodes

**Related Tickets:**
- T-1801: StateGraph Setup (stub nodes, 11 tests)
- T-1802: LLM Classification + Circuit Breaker (ClassifyTipologia node, 32 tests)
- US-002: Validation Services (NomenclatureValidator, GeometryValidator, 26 tests)

---

## 2. Solution: Adapter Pattern

**Pattern Choice:** Adapter (Wrapper) Pattern

**Rationale:**
- Adapters **wrap** existing validators (US-002) without modifying them
- **Extract state** → **call validator** → **update state** pattern
- Validators remain **reusable** (CLI tools, standalone scripts, other graphs)
- Clear **separation of concerns**: Validators = business logic, Adapters = state transformation
- Easy **testing**: Validators isolated (unit tests US-002), Adapters integrated (StateGraph tests T-1803)

**Architecture Diagram:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                         LangGraph StateGraph                         │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ Extract      │───▶│ Validate     │───▶│ Validate     │          │
│  │ Geometry     │    │ Nomenclature │    │ Geometry     │          │
│  │ (Adapter)    │    │ (Adapter)    │    │ (Adapter)    │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                  │
│         │ calls             │ calls             │ calls            │
│         ▼                   ▼                   ▼                  │
│  ┌─────────────────────────────────────────────────────┐          │
│  │            US-002 Validators (UNCHANGED)            │          │
│  │                                                     │          │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │          │
│  │  │ Rhino        │  │ Nomenclature │  │ Geometry│ │          │
│  │  │ ParserService│  │ Validator    │  │Validator│ │          │
│  │  │              │  │              │  │         │ │          │
│  │  │ parse_file() │  │ validate_    │  │validate_│ │          │
│  │  │   ↓          │  │ nomenclature()  geometry()│ │          │
│  │  │ UserString   │  │   ↓          │  │    ↓    │ │          │
│  │  │ Extractor    │  │ errors[]     │  │ errors[]│ │          │
│  │  └──────────────┘  └──────────────┘  └─────────┘ │          │
│  │                                                     │          │
│  │          26 tests PASS (zero regression)           │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Graph Flow Redesign

**Original Flow (T-1801 stubs):**
```
ValidateNomenclature → ExtractGeometry → ValidateGeometry → ...
```

**Problem:** ValidateNomenclature needs `layers` from .3dm file, but ExtractGeometry runs AFTER → circular dependency.

**New Flow (T-1803 refactored):**
```
ExtractGeometry → ValidateNomenclature → ValidateGeometry → ClassifyTipologia → EnrichMetadata → GenerateReport → MarkValidated
       ↓                    ↓                   ↓
   MarkRejected        MarkRejected        MarkRejected
(file not found)   (nomenclature fail)  (geometry fail)
```

**Conditional Edges (Fail-Fast):**
1. **After ExtractGeometry:** If file download/parse fails → MarkRejected (skip all validation)
2. **After ValidateNomenclature:** If nomenclature_valid=False → MarkRejected (skip geometry + LLM)
3. **After ValidateGeometry:** If geometry_valid=False → MarkRejected (skip LLM classification)

---

## 4. Adapter Implementations

### 4.1. ExtractGeometry Adapter (~180 LOC)

**Purpose:** Download .3dm from Supabase Storage, parse with rhino3dm, extract metadata

**Implementation:**
```python
def node_extract_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    T-1803 ADAPTER: Downloads .3dm file, parses with RhinoParserService.
    
    Extracts:
    - Layers (for ValidateNomenclature)
    - Geometry metadata (bbox, volume, vertices_count)
    - UserStrings (for EnrichMetadata)
    - rhino_model (for ValidateGeometry)
    """
    from infra.supabase_client import get_supabase_client
    from src.agent.services.rhino_parser_service import RhinoParserService
    from constants import STORAGE_BUCKET_RAW_UPLOADS
    
    block_id = state["block_id"]
    
    # Download from Supabase Storage
    supabase = get_supabase_client()
    file_key = f"{block_id}.3dm"
    file_content = supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).download(file_key)
    
    # Save to /tmp for rhino3dm parsing
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.3dm', delete=False) as temp_file:
        temp_file.write(file_content)
        temp_file_path = temp_file.name
    
    # Parse with RhinoParserService (US-002, UNCHANGED)
    parser = RhinoParserService()
    result = parser.parse_file(temp_file_path)
    
    # Load rhino3dm model for geometry extraction
    model = rhino3dm.File3dm.Read(temp_file_path)
    
    # Calculate bbox, volume, vertices from model
    # ... (geometry calculation code ~50 LOC)
    
    return {
        "geometry_metadata": {
            "layers": result.layers,  # List[LayerInfo] for ValidateNomenclature
            "bbox": bbox_dict,
            "volume": volume,
            "vertices_count": vertices_count,
            "rhino_model": model,  # For ValidateGeometry
            "user_strings": result.user_strings,  # For EnrichMetadata
            "file_exists_in_storage": True,
        },
        "validation_path": _append_to_path(state, "ExtractGeometry"),
    }
```

**Key Decision:** Store `rhino_model` in state to avoid re-parsing in ValidateGeometry node.

---

### 4.2. ValidateNomenclature Adapter (~70 LOC)

**Purpose:** Call NomenclatureValidator (US-002) with layers from ExtractGeometry

**Implementation:**
```python
def node_validate_nomenclature(state: ValidationState) -> Dict[str, Any]:
    """
    T-1803 ADAPTER: Calls NomenclatureValidator (US-002) via wrapper.
    
    Extracts layers from geometry_metadata → validates → updates state.
    """
    from src.agent.services.nomenclature_validator import NomenclatureValidator
    
    geometry_metadata = state.get("geometry_metadata", {})
    layers = geometry_metadata.get("layers", [])  # List[LayerInfo]
    
    # Call US-002 validator (UNCHANGED code)
    validator = NomenclatureValidator()
    errors = validator.validate_nomenclature(layers)
    
    return {
        "nomenclature_valid": len(errors) == 0,
        "nomenclature_errors": errors,
        "validation_path": _append_to_path(state, "ValidateNomenclature"),
    }
```

**Zero Regression:** `NomenclatureValidator` code 100% unchanged (15 tests still PASS).

---

### 4.3. ValidateGeometry Adapter (~70 LOC)

**Purpose:** Call GeometryValidator (US-002) with rhino_model from ExtractGeometry

**Implementation:**
```python
def node_validate_geometry(state: ValidationState) -> Dict[str, Any]:
    """
    T-1803 ADAPTER: Calls GeometryValidator (US-002) with rhino_model.
    
    Validates geometry integrity (null check, IsValid, bbox, volume).
    """
    from src.agent.services.geometry_validator import GeometryValidator
    
    geometry_metadata = state.get("geometry_metadata", {})
    rhino_model = geometry_metadata.get("rhino_model")
    
    # Call US-002 validator (UNCHANGED code)
    validator = GeometryValidator()
    errors = validator.validate_geometry(rhino_model)
    
    return {
        "geometry_valid": len(errors) == 0,
        "validation_path": _append_to_path(state, "ValidateGeometry"),
    }
```

**Key Decision:** Reuse `rhino_model` from state (no re-parsing) for performance.

---

### 4.4. EnrichMetadata Adapter (~80 LOC)

**Purpose:** Extract Material from UserStringCollection, merge into semantic_data

**Implementation:**
```python
def node_enrich_metadata(state: ValidationState) -> Dict[str, Any]:
    """
    T-1803 ADAPTER: Parses UserStringCollection to extract Material.
    
    Merges Material into semantic_data (preserves LLM classification from ClassifyTipologia).
    """
    geometry_metadata = state.get("geometry_metadata", {})
    user_strings = geometry_metadata.get("user_strings")  # From RhinoParserService
    semantic_data = state.get("semantic_data", {})
    
    material = "Unknown"
    
    # user_strings can be dict (from RhinoParserService) or UserStringCollection object
    if user_strings:
        if isinstance(user_strings, dict):
            # Dict format: {document: {}, layers: {}, objects: {}}
            document_strings = user_strings.get("document", {})
            if "Material" in document_strings:
                material = document_strings["Material"]
            
            # Fallback to first object's user strings
            if material == "Unknown":
                objects_strings = user_strings.get("objects", {})
                for obj_id, obj_strings in objects_strings.items():
                    if "Material" in obj_strings:
                        material = obj_strings["Material"]
                        break
    
    # Merge into semantic_data (preserve tipologia, confidence, reasoning from LLM)
    updated_semantic_data = {**semantic_data, "material": material}
    
    return {
        "semantic_data": updated_semantic_data,
        "validation_path": _append_to_path(state, "EnrichMetadata"),
    }
```

**Bug Fix (Day 2):** Added dict support for user_strings (RhinoParserService returns `user_strings.model_dump()`).

---

## 5. Testing Strategy

### 5.1. Integration Tests (test_stategraph_validators.py, 5 tests)

**Purpose:** Verify Adapter Pattern works with real US-002 validators in StateGraph context.

**Tests:**
1. **INT-01:** Nomenclature valid → ExtractGeometry executed ✅
2. **INT-02:** Nomenclature fail → downstream nodes skipped (fail-fast) ✅
3. **INT-03:** Geometry valid → EnrichMetadata executed ✅
4. **INT-04:** Geometry fail → EnrichMetadata skipped (fail-fast) ✅
5. **INT-05:** Full happy path with real validators ✅

**Mocking Strategy:**
- Mock Supabase Storage download (return mock .3dm bytes)
- Mock rhino3dm.File3dm.Read() with valid/invalid layer names + geometry
- **Preserve real validators** (NomenclatureValidator, GeometryValidator - NOT mocked)

**Result:** 5/5 tests PASS

---

### 5.2. Zero Regression Verification (US-002 tests, 26 tests)

**Purpose:** Confirm validators remain 100% unchanged after T-1803 refactoring.

**Tests:**
- test_nomenclature_validator.py: 9/9 tests PASS ✅
- test_geometry_validator.py: 9/9 tests PASS ✅
- test_user_string_extractor.py: 8/8 tests PASS ✅

**Total:** 26/26 tests PASS (zero regression confirmed)

---

### 5.3. T-1801 Regression Prevention (test_stategraph.py, 11 tests)

**Problem:** Graph reordering (ExtractGeometry first) broke T-1801 tests expecting old flow.

**Solution:** Added `mock_supabase_and_rhino3dm` autouse fixture to test_stategraph.py:
- Mocks Supabase Storage download
- Mocks rhino3dm.File3dm.Read() with valid nomenclature + geometry
- Updated expected validation_path (ExtractGeometry now first node)

**Result:** 11/11 T-1801 tests PASS (no regression)

---

## 6. Metrics

**Implementation:**
- Lines of Code: ~900 LOC total
  - src/agent/graph/nodes.py: 4 adapters refactored (~400 LOC)
  - src/agent/graph/graph.py: Graph reordering + 3rd conditional edge (~50 LOC)
  - tests/agent/unit/test_stategraph_validators.py: 5 integration tests (~500 LOC)
  - tests/agent/unit/test_stategraph.py: Supabase/rhino3dm mocks (~70 LOC added)

**Test Coverage:**
- **74/74 tests PASS** (100% passing rate for T-1803 scope)
  - 5/5 integration (T-1803 new tests) ✅
  - 26/26 US-002 zero regression ✅
  - 11/11 T-1801 StateGraph ✅
  - 32/32 T-1802 LLM + Circuit Breaker ✅

**Duration:** 2.5 días (20 horas)
- Day 1: 4 Adapters (8h) ✅
- Day 2: Testing + Bug Fixes (8h) ✅
- Day 3: Documentation (4h) ✅

**Commits:**
1. `91c843e` - docs(agent): T-1803 Planning registered in prompts.md (#252)
2. `15c412a` - feat(agent): T-1803 Day 1 - Adapter Pattern for 4 StateGraph Nodes
3. `79efe93` - test(agent): T-1803 Day 2 - Integration Tests + Adapter Fixes
4. `[PENDING]` - docs(agent): T-1803 Day 3 - TechnicalSpec + systemPatterns Guide

---

## 7. Benefits

**Achieved:**
1. **Zero Regression:** 26 US-002 tests continue to PASS (validators 100% unchanged)
2. **Reusability:** Validators usable independently (CLI tools, standalone scripts, future graphs)
3. **Testability:** Clear separation → Validators isolated (unit tests), Adapters integrated (StateGraph tests)
4. **Maintainability:** Changes to validators don't break StateGraph (loose coupling)
5. **Fail-Fast:** Invalid nomenclature/geometry skip downstream nodes (performance optimization)

**Future-Proofing:**
- Adding new validators → create adapter wrapper (no graph changes)
- Graph reordering → update conditional edges (validators unaffected)
- Validator enhancements → US-002 tests validate, adapters unchanged

---

## 8. Lessons Learned

**Design Decisions:**
1. **Graph Entry Point:** ExtractGeometry must be FIRST node (ValidateNomenclature needs layers from .3dm file)
2. **State Reuse:** Store rhino_model in state to avoid re-parsing (performance optimization)
3. **UserStrings Format:** RhinoParserService returns dict (`user_strings.model_dump()`), not Pydantic object

**Testing Insights:**
1. **Mock Fixtures Must Match Real APIs:** UserStringCollection mock initially didn't support dict access (INT-03/INT-05 failed)
2. **Graph Reordering Has Cascading Effects:** T-1801 tests broke when ExtractGeometry became first node (fixed with autouse fixture)
3. **Integration Tests Reveal Flow Issues:** Unit tests alone didn't catch dependency ordering problem (ValidateNomenclature → ExtractGeometry)

**Adapter Pattern Validation:**
- Successfully isolated US-002 validators (zero regression)
- Clean separation of concerns (validators = business logic, adapters = state transformation)
- Easy to test (validators + adapters independently verifiable)

---

## 9. References

**Related Documentation:**
- [T-1801 TechnicalSpec](./T-1801-SETUP-TechnicalSpec.md) - StateGraph setup + stub nodes
- [T-1802 TechnicalSpec](./T-1802-LLM-TechnicalSpec.md) - LLM Classification + Circuit Breaker
- [Adapter Pattern Guide](../../memory-bank/systemPatterns.md#adapter-pattern) - Reusable pattern for future validators
- [US-002 Validation Services](../US-002/README.md) - NomenclatureValidator, GeometryValidator specs

**Code Files:**
- `src/agent/graph/nodes.py` - 4 adapter implementations
- `src/agent/graph/graph.py` - StateGraph definition with 3 conditional edges
- `tests/agent/unit/test_stategraph_validators.py` - 5 integration tests
- `src/agent/services/nomenclature_validator.py` - US-002 validator (UNCHANGED)
- `src/agent/services/geometry_validator.py` - US-002 validator (UNCHANGED)
- `src/agent/services/user_string_extractor.py` - US-002 extractor (UNCHANGED)

---

**Status:** ✅ COMPLETED  
**Next Ticket:** T-1804 (GenerateReport node - PDF report generation)
