# Technical Specification: T-1503-AGENT

**Version:** 1.0  
**Status:** ENRICHED (Pre-TDD)  
**Date:** 2026-03-07  
**Ticket:** T-1503-AGENT — Rhino Parser + GLB Generator with Material Type Extraction

---

## 1. Ticket Summary

- **Tipo:** AGENT
- **Alcance:** Update geometry processing pipeline to extract and validate `material_type` from Rhino UserStrings, use standardized storage paths, and fix race condition in temporary file naming
- **Story Points:** 5
- **Dependencias:**
  - ✅ **T-1501-DB** (material_type column exists in blocks table)
  - ✅ **T-1502-INFRA** (generate_glb_storage_path function available)
  - 🔜 **T-1504-BACK** (blocked until agent integration complete)

---

## 2. Problem Statement

### Current State (Before T-1503)
The geometry processing pipeline (`src/agent/tasks/geometry_processing.py`) currently:
- ❌ Does NOT extract `material_type` from Rhino UserStrings
- ❌ Uses hardcoded storage paths: `f"{LOW_POLY_PREFIX}{block_id}.glb"` (e.g., `low-poly/{uuid}.glb`)
- ❌ Creates temporary files with only block_id: `f"{block_id}.3dm"`, `f"{block_id}.glb"` → **race condition risk** if same block processed concurrently
- ❌ Updates database with only `low_poly_url` and `bbox` → `material_type` remains NULL

### Target State (After T-1503)
The updated pipeline will:
- ✅ Extract `material_type` from document/layer/object UserStrings (key: `"Material"`)
- ✅ Validate extracted value against `MaterialType` enum (`"Stone"`, `"Ceramic"`)
- ✅ Default to `"Stone"` if not found (architectural elements assumption)
- ✅ Use standardized storage paths: `models/low-poly/{uuid}_{ISO8601}.glb` (via T-1502 function)
- ✅ Create unique temporary files: `{block_id}-{original_filename}` to prevent collisions
- ✅ Update database with `material_type` alongside `low_poly_url` and `bbox`

---

## 3. Data Structures & Contracts

### Backend Schema (Pydantic)

**NEW Enum in `src/backend/schemas.py`:**
```python
# Add to existing schemas.py (after BlockStatus enum, before BoundingBox class)
class MaterialType(str, Enum):
    """
    Material types for architectural elements.
    
    Synchronized with PostgreSQL CHECK constraint (T-1501-DB):
    CHECK (material_type IN ('Stone', 'Ceramic'))
    
    Valid values:
        - Stone: Natural stone (99% of Sagrada Familia elements)
        - Ceramic: Ceramic materials (decorative elements)
    """
    STONE = "Stone"
    CERAMIC = "Ceramic"
```

**NO changes needed to existing schemas** — `material_type` already exists in database (T-1501-DB), this enum will be used by T-1504-BACK for API responses.

### Agent Internal Models

**NEW Model in `src/agent/models.py`:**
```python
# Add after FileProcessingResult class
class MaterialExtractionResult(BaseModel):
    """
    Result of material type extraction from Rhino UserStrings.
    
    Attributes:
        material_type: Validated MaterialType enum value
        source: Where the value was found (document/layer/object/default)
        raw_value: Original string before validation (for debugging)
    """
    material_type: str = Field(..., description="Validated MaterialType enum value")
    source: str = Field(..., description="Extraction source: document/layer/object/default")
    raw_value: Optional[str] = Field(None, description="Original UserString value")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "material_type": "Stone",
                "source": "document",
                "raw_value": "Stone"
            }
        }
    )
```

### Database Changes (SQL)

**NO migrations needed** — schema already updated by T-1501-DB:
```sql
-- Column already exists (T-1501-DB migration):
-- ALTER TABLE blocks ADD COLUMN material_type TEXT CHECK (material_type IN ('Stone', 'Ceramic'));

-- Only UPDATE operation needed (in _update_block_with_processing_results):
UPDATE blocks 
SET low_poly_url = %s, 
    bbox = %s,
    material_type = %s  -- NEW: Add this field
WHERE id = %s;
```

---

## 4. Implementation Design

### 4.1 Material Type Extraction Logic

**NEW Function in `src/agent/tasks/geometry_processing.py`:**
```python
def _extract_material_type(rhino_file: rhino3dm.File3dm, block_id: str, iso_code: str) -> str:
    """
    Extract and validate material_type from Rhino UserStrings.
    
    Extraction Priority (first found wins):
        1. Document-level UserString with key "Material"
        2. Layer-level UserString with key "Material" (any layer)
        3. Object-level UserString with key "Material" (any object)
        4. Default to "Stone" if not found
    
    Validation:
        - Value MUST be in MaterialType enum: ["Stone", "Ceramic"]
        - Case-insensitive matching (e.g., "stone" → "Stone")
        - Whitespace trimming
        - Invalid values → log WARNING + use default "Stone"
    
    Args:
        rhino_file: Parsed rhino3dm.File3dm object
        block_id: UUID of the block (for logging)
        iso_code: ISO code of the block (for logging)
    
    Returns:
        str: Validated MaterialType enum value ("Stone" or "Ceramic")
    
    Example:
        material_type = _extract_material_type(rhino_file, block_id, "SAGR-Z1-001")
        # Returns: "Stone"
    """
    # Implementation will use UserStringExtractor service
    # See pseudocode in section 4.2
    pass
```

### 4.2 Pseudocode for Material Extraction
```python
# Step 1: Extract all UserStrings using existing service
from src.agent.services.user_string_extractor import UserStringExtractor
extractor = UserStringExtractor()
user_strings = extractor.extract(rhino_file)

# Step 2: Search for "Material" key (case-insensitive)
MATERIAL_KEY = "Material"
VALID_MATERIALS = ["Stone", "Ceramic"]
DEFAULT_MATERIAL = "Stone"

raw_value = None
source = "default"

# Priority 1: Document-level
if MATERIAL_KEY in user_strings.document:
    raw_value = user_strings.document[MATERIAL_KEY]
    source = "document"

# Priority 2: Layer-level (any layer)
if raw_value is None:
    for layer_name, layer_strings in user_strings.layers.items():
        if MATERIAL_KEY in layer_strings:
            raw_value = layer_strings[MATERIAL_KEY]
            source = f"layer:{layer_name}"
            break

# Priority 3: Object-level (any object)
if raw_value is None:
    for obj_uuid, obj_strings in user_strings.objects.items():
        if MATERIAL_KEY in obj_strings:
            raw_value = obj_strings[MATERIAL_KEY]
            source = f"object:{obj_uuid}"
            break

# Step 3: Validate and normalize
if raw_value:
    normalized = raw_value.strip().capitalize()  # "stone" → "Stone", " Ceramic " → "Ceramic"
    if normalized in VALID_MATERIALS:
        material_type = normalized
        logger.info("extract_material_type.found", block_id=block_id, 
                    material_type=material_type, source=source, raw_value=raw_value)
    else:
        material_type = DEFAULT_MATERIAL
        logger.warning("extract_material_type.invalid_value", block_id=block_id,
                       raw_value=raw_value, source=source, 
                       message=f"Invalid material '{raw_value}', defaulting to '{DEFAULT_MATERIAL}'")
else:
    material_type = DEFAULT_MATERIAL
    logger.info("extract_material_type.not_found", block_id=block_id,
                material_type=material_type, message="Material UserString not found, using default")

return material_type
```

### 4.3 Storage Path Integration

**UPDATE in `_export_and_upload_glb` function:**
```python
# BEFORE (Current - T-0502 implementation):
glb_key = f"{LOW_POLY_PREFIX}{block_id}.glb"  # Produces: "low-poly/{uuid}.glb"

# AFTER (T-1503 with T-1502 integration):
from src.backend.utils.storage import generate_glb_storage_path
from datetime import datetime, timezone

glb_key = generate_glb_storage_path(
    block_id=UUID(block_id),  # Convert string to UUID object
    timestamp=datetime.now(timezone.utc)  # Explicit UTC timestamp
)
# Produces: "models/low-poly/{uuid}_2026-03-07T15:30:45Z.glb"
```

**Import Statement to Add:**
```python
# Add to imports section at top of geometry_processing.py
from uuid import UUID
from datetime import timezone
```

### 4.4 Race Condition Fix

**UPDATE in `generate_low_poly_glb` task (temp file naming):**
```python
# BEFORE (Current - race condition vulnerable):
temp_3dm_path = os.path.join(TEMP_DIR, f"{block_id}.3dm")

# AFTER (T-1503 - unique filename):
original_filename = url_original.split('/')[-1]  # Extract "test-file.3dm" from URL
temp_3dm_path = os.path.join(TEMP_DIR, f"{block_id}-{original_filename}")
# Produces: "/tmp/sf-pm-agent/{uuid}-test-file.3dm"
```

**UPDATE in `_export_and_upload_glb` (temp GLB naming):**
```python
# BEFORE (Current):
temp_glb_path = os.path.join(TEMP_DIR, f"{block_id}.glb")
raw_glb_path = os.path.join(TEMP_DIR, f"{block_id}-raw.glb")

# AFTER (T-1503 - unique filenames):
timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
temp_glb_path = os.path.join(TEMP_DIR, f"{block_id}-{timestamp_str}.glb")
raw_glb_path = os.path.join(TEMP_DIR, f"{block_id}-{timestamp_str}-raw.glb")
# Produces: "/tmp/sf-pm-agent/{uuid}-20260307-153045.glb"
```

### 4.5 Database Update Integration

**UPDATE `_update_block_low_poly_url` function (rename and extend):**
```python
# BEFORE (Current - T-0502):
def _update_block_low_poly_url(block_id: str, url: str, bbox: dict) -> None:
    """Update database with low_poly_url and bbox for processed block."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blocks SET low_poly_url = %s, bbox = %s WHERE id = %s",
            (url, json.dumps(bbox), block_id)
        )
        conn.commit()

# AFTER (T-1503 - add material_type):
def _update_block_with_processing_results(
    block_id: str, 
    url: str, 
    bbox: dict,
    material_type: str  # NEW parameter
) -> None:
    """
    Update database with processing results: low_poly_url, bbox, material_type.
    
    Args:
        block_id: UUID of the block to update
        url: Public URL of the uploaded GLB file
        bbox: Bounding box: {"min": [x,y,z], "max": [x,y,z]}
        material_type: Validated MaterialType enum value ("Stone" or "Ceramic")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blocks SET low_poly_url = %s, bbox = %s, material_type = %s WHERE id = %s",
            (url, json.dumps(bbox), material_type, block_id)  # NEW: material_type parameter
        )
        conn.commit()
    
    logger.info("update_db.success", 
                block_id=block_id, 
                low_poly_url=url,
                bbox_min=bbox["min"], 
                bbox_max=bbox["max"],
                material_type=material_type)  # NEW: log material_type
```

**UPDATE main task to call new function:**
```python
# In generate_low_poly_glb task, AFTER Step 3 (parse .3dm):
# NEW: Step 3.5 - Extract material type
material_type = _extract_material_type(rhino_file, block_id, iso_code)

# ...existing Steps 4-8...

# Step 9: Update database (BEFORE - old function call)
# _update_block_low_poly_url(block_id, low_poly_url, bbox)

# Step 9: Update database (AFTER - new function call with material_type)
_update_block_with_processing_results(block_id, low_poly_url, bbox, material_type)
```

---

## 5. Test Cases Checklist

### Happy Path (Material Extraction)
- [ ] **HP-01**: Document-level UserString `"Material": "Stone"` → extracts `"Stone"`
- [ ] **HP-02**: Document-level UserString `"Material": "Ceramic"` → extracts `"Ceramic"`
- [ ] **HP-03**: Layer-level UserString (no document-level) → extracts from layer
- [ ] **HP-04**: Object-level UserString (no document/layer) → extracts from object
- [ ] **HP-05**: No UserString found → defaults to `"Stone"`

### Edge Cases (Normalization)
- [ ] **EC-01**: Lowercase `"material": "stone"` → normalizes to `"Stone"`
- [ ] **EC-02**: Whitespace `"Material": " Ceramic "` → normalizes to `"Ceramic"`
- [ ] **EC-03**: Mixed case `"Material": "STONE"` → normalizes to `"Stone"`
- [ ] **EC-04**: Multiple layers with Material UserString → uses first found (deterministic order)

### Error Handling (Invalid Values)
- [ ] **ERR-01**: Invalid value `"Material": "Wood"` → logs WARNING, defaults to `"Stone"`
- [ ] **ERR-02**: Invalid value `"Material": ""` (empty string) → defaults to `"Stone"`
- [ ] **ERR-03**: Invalid value `"Material": "concrete"` → defaults to `"Stone"`

### Storage Path Integration (T-1502)
- [ ] **PATH-01**: Generated GLB key uses format `models/low-poly/{uuid}_{ISO8601}.glb`
- [ ] **PATH-02**: No leading slash in storage key (S3 compatibility)
- [ ] **PATH-03**: Timestamp in ISO8601 format with `Z` suffix
- [ ] **PATH-04**: UUID converted to lowercase in path

### Race Condition Prevention
- [ ] **RACE-01**: Temp .3dm file includes original filename: `{uuid}-{filename}.3dm`
- [ ] **RACE-02**: Temp GLB files include timestamp: `{uuid}-{timestamp}.glb`
- [ ] **RACE-03**: Concurrent processing of same block_id → different temp files
- [ ] **RACE-04**: Temp file cleanup after upload (no orphan files)

### Database Integration
- [ ] **DB-01**: Database UPDATE includes material_type field
- [ ] **DB-02**: material_type value validated by DB CHECK constraint
- [ ] **DB-03**: Query after update shows material_type = "Stone" or "Ceramic"
- [ ] **DB-04**: Existing blocks retain NULL material_type (no retroactive update)

### Integration (End-to-End)
- [ ] **INT-01**: Full pipeline: .3dm with Material UserString → GLB upload → DB update with all 3 fields
- [ ] **INT-02**: Full pipeline: .3dm without Material UserString → default "Stone" → DB update
- [ ] **INT-03**: Celery task SUCCESS return includes material_type in result dict
- [ ] **INT-04**: Worker logs show material extraction step (info/warning levels)

---

## 6. Files to Create/Modify

### Create (NEW files)
- `docs/US-015/T-1503-AGENT-TechnicalSpec-ENRICHED.md` → This spec document

### Modify (EXISTING files)

**Agent Code:**
1. `src/agent/tasks/geometry_processing.py` (MAJOR REFACTOR ~100 lines changed)
   - Add `_extract_material_type()` function (~50 lines NEW)
   - Update `_export_and_upload_glb()` to use `generate_glb_storage_path` (~5 lines changed)
   - Rename `_update_block_low_poly_url()` → `_update_block_with_processing_results()` (~10 lines changed)
   - Update `generate_low_poly_glb()` main task (~15 lines changed)
     - Add material_type extraction step
     - Update temp file naming (race condition fix)
     - Call new DB update function with material_type parameter
   - Add imports: `from src.agent.services.user_string_extractor import UserStringExtractor`
   - Add imports: `from src.backend.utils.storage import generate_glb_storage_path`
   - Add imports: `from uuid import UUID`

2. `src/agent/models.py` (MINOR ADDITION ~20 lines NEW)
   - Add `MaterialExtractionResult` Pydantic model

**Backend Code:**
3. `src/backend/schemas.py` (MINOR ADDITION ~15 lines NEW)
   - Add `MaterialType` enum (Stone, Ceramic)

**Test Files:**
4. `tests/agent/unit/test_material_extraction.py` (NEW FILE ~200 lines)
   - Test suite for `_extract_material_type()` function
   - 20+ test cases covering HP, EC, ERR scenarios

5. `tests/agent/integration/test_low_poly_pipeline.py` (MINOR UPDATE ~20 lines)
   - Update existing integration tests to assert material_type in DB
   - Mock UserString data in fixtures

---

## 7. Reusable Components/Patterns

### Existing Services to Reuse
1. **UserStringExtractor** (`src/agent/services/user_string_extractor.py`)
   - Already implements extraction from document/layers/objects
   - Returns `UserStringCollection` model with structured data
   - Pattern: `extractor.extract(model)` → get all user strings at once

2. **generate_glb_storage_path** (`src/backend/utils/storage.py` - T-1502-INFRA)
   - Already implements standardized path format
   - Handles UUID validation, timezone conversion, ISO8601 formatting
   - Pattern: `generate_glb_storage_path(UUID(block_id), datetime.now(timezone.utc))`

3. **Structured Logging** (existing pattern in `geometry_processing.py`)
   - Use `logger.info/warning/error` with structured fields
   - Pattern: `logger.info("extract_material_type.found", block_id=block_id, material_type=material_type, source=source)`

### Design Patterns to Follow
1. **Priority Search Pattern** (document → layer → object → default)
   - First-found-wins logic
   - Clear logging of source at each level

2. **Validation with Fallback** (validate → default if invalid)
   - Protect against user input errors
   - Always log warnings when using defaults

3. **Function Decomposition** (existing pattern)
   - Single-purpose functions with clear docstrings
   - Pure functions where possible (no side effects except logging)

---

## 8. Next Steps

This spec is ready for TDD-RED phase. Use `:tdd-red` prompt with the following data:

---

**HANDOFF FOR TDD-RED PHASE:**
```
=============================================
READY FOR TDD-RED PHASE - Copy these values:
=============================================
Ticket ID:       T-1503-AGENT
Feature name:    Material Type Extraction + Storage Path Standardization
Key test cases:  
  - HP-01: Extract Material UserString "Stone" from document level
  - HP-05: Default to "Stone" when Material UserString not found
  - ERR-01: Reject invalid Material value "Wood", default to "Stone"
  - PATH-01: GLB storage path uses format models/low-poly/{uuid}_{ISO8601}.glb
  - RACE-01: Temp files include unique identifiers (block_id + filename/timestamp)
  - DB-01: Database UPDATE includes material_type field
  - INT-01: Full pipeline uploads GLB + updates DB with material_type

Files to create:
  - tests/agent/unit/test_material_extraction.py (NEW ~200 lines)

Files to modify:
  - src/agent/tasks/geometry_processing.py (~100 lines changed)
  - src/agent/models.py (~20 lines added)
  - src/backend/schemas.py (~15 lines added)
  - tests/agent/integration/test_low_poly_pipeline.py (~20 lines updated)

Dependencies verified:
  ✅ T-1501-DB: material_type column exists
  ✅ T-1502-INFRA: generate_glb_storage_path function ready
  ✅ UserStringExtractor service already implemented

Estimated TDD-RED time: 2-3 hours (4 files to create/modify, 25+ test cases)
=============================================
```

---

## 9. Testing Strategy (TDD Workflow)

### Phase 1: TDD-RED (Write Failing Tests)
1. Create `test_material_extraction.py` with 20 test cases (HP + EC + ERR)
2. Update `test_low_poly_pipeline.py` with material_type assertions
3. Run tests → Expect: **20+ FAILED** (NotImplementedError)

### Phase 2: TDD-GREEN (Implement Minimal Code)
1. Implement `_extract_material_type()` function
2. Update `_update_block_with_processing_results()` function (rename + add parameter)
3. Integrate storage path generator from T-1502
4. Fix temp file naming (race condition)
5. Run tests → Expect: **20+ PASSED, 0 FAILED**

### Phase 3: TDD-REFACTOR (Clean Code)
1. Extract constants: `MATERIAL_KEY = "Material"`, `VALID_MATERIALS = ["Stone", "Ceramic"]`
2. Improve docstrings with examples
3. Add structured logging for all code paths
4. Run tests → Expect: **20+ PASSED, 0 FAILED** (no regression)

### Phase 4: INTEGRATION (Verify Baseline)
1. Run FULL agent test suite: `pytest tests/agent/ -v`
2. Run backend baseline (no changes expected): `pytest tests/ -v`
3. Expect: **ALL TESTS PASS** (no regressions)

---

## 10. Risk Mitigation

### Risk 1: UserString Key Inconsistency
**Risk:** Different .3dm files use different keys: "Material", "material", "MaterialType"  
**Mitigation:** 
- Use case-insensitive search: `key.lower() == "material"`
- Document approved key name in ADR (if needed)
- Log warnings when non-standard keys found

### Risk 2: Invalid Material Values
**Risk:** Users input freeform text: "piedra", "concrete", "wood"  
**Mitigation:**
- Always validate against enum BEFORE database update
- Default to "Stone" for invalid values
- Log WARNING with raw value for audit trail

### Risk 3: T-1502 Import Error
**Risk:** Circular import if `geometry_processing.py` imports from `src/backend/utils/`  
**Mitigation:**
- Test imports in isolation before TDD-RED
- If circular dependency detected, copy function to agent utils

### Risk 4: Timestamp Collision in Temp Files
**Risk:** Two tasks start processing at exact same second → temp file collision  
**Mitigation:**
- Use microsecond precision: `strftime("%Y%m%d-%H%M%S-%f")`
- Alternative: Use `uuid.uuid4()` suffix for absolute uniqueness

---

## 11. Acceptance Criteria Validation

**From backlog (US-015 → T-1503-AGENT DoD):**

| DoD Criterion | Implementation Plan | Verification Method |
|---------------|---------------------|---------------------|
| ✅ Material type extracted from UserString | `_extract_material_type()` function with priority search | Unit tests HP-01 to HP-05 |
| ✅ Validated against enum | Normalize + check in `VALID_MATERIALS` list | Unit tests ERR-01 to ERR-03 |
| ✅ Race condition fixed | Temp files use `{block_id}-{filename/timestamp}` | Unit tests RACE-01 to RACE-04 |
| ✅ 3-5 backend tests updated (UserString mocks) | Update `test_low_poly_pipeline.py` with material fixtures | Integration tests INT-01 to INT-04 |

---

**Document END**  
**Next Action:** Proceed to TDD-RED phase (create test files with `:tdd-red` prompt)
