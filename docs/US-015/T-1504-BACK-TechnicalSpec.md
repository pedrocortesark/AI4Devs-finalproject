# Technical Specification: T-1504-BACK

## 1. Ticket Summary
- **Tipo:** BACKEND (API Layer + Service Layer + Schemas)
- **Alcance:** Refactorizar API de Parts a Elements con nomenclatura en inglés, material_type validado contra 62 materiales reales, y filtrado de elementos sin geometría procesada
- **Dependencias:** 
  - ✅ T-1501-DB (Migration aplicada: `material_type TEXT`, `workshop_id`/`workshop_name` eliminados)
  - ✅ T-1502-INFRA (Storage path conventions implementadas)
  - ✅ T-1504-AGENT (MATERIAL_COLORS dictionary con 62 materiales + RGB colores)
  - 🔜 T-1505-FRONT (Consumirá los nuevos contratos Element)

## 2. Data Structures & Contracts

### Backend Schemas (Pydantic)

**File:** `src/backend/schemas.py`

#### 2.1 Element Schema (reemplaza PartCanvasItem)

```python
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from enum import Enum

# Import material validation from agent constants
from agent.constants import VALID_MATERIALS, DEFAULT_MATERIAL

class ElementStatus(str, Enum):
    """
    Lifecycle states for elements (replaces BlockStatus for clarity).
    
    Synchronized with PostgreSQL ENUM block_status (T-021-DB).
    """
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR_PROCESSING = "error_processing"
    IN_FABRICATION = "in_fabrication"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class BoundingBox(BaseModel):
    """
    3D bounding box for spatial layout in canvas.
    
    Format matches THREE.js Box3 structure for frontend compatibility.
    """
    min: List[float] = Field(..., min_length=3, max_length=3, description="Min corner [x, y, z]")
    max: List[float] = Field(..., min_length=3, max_length=3, description="Max corner [x, y, z]")

    @field_validator('min', 'max')
    @classmethod
    def validate_coordinates(cls, v):
        if len(v) != 3:
            raise ValueError('Must contain exactly 3 coordinates [x, y, z]')
        return v


class Element(BaseModel):
    """
    Element schema optimized for 3D canvas rendering (US-005).
    
    Contract: Must match TypeScript interface Element exactly (T-1505-FRONT).
    
    Breaking Changes from PartCanvasItem:
    - Removed: workshop_id, workshop_name (workshops not used in MVP)
    - Renamed: tipologia → material_type (internationalization)
    - Changed: material_type from enum to str (validated against 62 real materials)
    
    Attributes:
        id: Element UUID
        iso_code: ISO-19650 identifier (e.g., SF-C12-D-001)
        status: Lifecycle state (ElementStatus enum)
        material_type: Stone material type (validated against 62 MATERIAL_COLORS)
        low_poly_url: Presigned CDN URL to GLB file (~1000 triangles)
        bbox: 3D bounding box for camera centering
    """
    id: UUID = Field(..., description="Element UUID")
    iso_code: str = Field(..., description="ISO-19650 identifier (e.g., SF-C12-D-001)")
    status: ElementStatus = Field(..., description="Lifecycle state")
    material_type: str = Field(
        ..., 
        description="Stone material type (one of 62 real materials: Montjuïc, Ulldecona, etc.)"
    )
    low_poly_url: Optional[str] = Field(
        None, 
        description="Presigned CDN URL for GLB file (NULL if async processing incomplete)"
    )
    bbox: Optional[BoundingBox] = Field(
        None, 
        description="3D bounding box (NULL if async processing incomplete)"
    )
    
    @field_validator('material_type')
    @classmethod
    def validate_material_type(cls, v: str) -> str:
        """
        Validate material_type against MATERIAL_COLORS dictionary (62 real materials).
        
        Args:
            v: Material type string from database
            
        Returns:
            Validated material type
            
        Raises:
            ValueError: If material not in VALID_MATERIALS list
        """
        if v not in VALID_MATERIALS:
            raise ValueError(
                f"Invalid material_type: '{v}'. Must be one of {len(VALID_MATERIALS)} "
                f"valid materials (e.g., Montjuïc, Ulldecona, Floresta). "
                f"See agent.constants.MATERIAL_COLORS for full list."
            )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "iso_code": "GLPER.B-PAE0720.0701",
                "status": "validated",
                "material_type": "Montjuïc",
                "low_poly_url": "https://d1234abcd.cloudfront.net/models/low-poly/550e8400_20260307T120000Z.glb",
                "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
            }
        }


class ElementsListResponse(BaseModel):
    """
    Response for GET /api/elements endpoint.
    
    Breaking Changes from PartsListResponse:
    - Renamed: parts → elements
    - Removed: count (redundant, use len(elements))
    
    Attributes:
        elements: Array of all elements matching filters
        filters_applied: Echo of query parameters for transparency
        meta: Metadata (total count, filtered count)
    """
    elements: List[Element] = Field(..., description="Array of canvas-ready elements")
    filters_applied: dict = Field(default_factory=dict, description="Applied filters (debugging)")
    meta: dict = Field(
        default_factory=lambda: {"total": 0, "filtered": 0},
        description="Response metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "elements": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "iso_code": "GLPER.B-PAE0720.0701",
                        "status": "validated",
                        "material_type": "Montjuïc",
                        "low_poly_url": "https://d1234abcd.cloudfront.net/models/low-poly/550e8400.glb",
                        "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
                    }
                ],
                "filters_applied": {"status": "validated", "material_type": "Montjuïc"},
                "meta": {"total": 6, "filtered": 6}
            }
        }
```

#### 2.2 ElementDetail Schema (reemplaza PartDetailResponse)

```python
class ElementDetail(BaseModel):
    """
    Detailed element info for 3D viewer modal (US-010).
    
    Contract: Must match TypeScript interface ElementDetail exactly (T-1505-FRONT).
    
    Breaking Changes from PartDetailResponse:
    - Removed: workshop_id, workshop_name, tipologia
    - Added: material_type (str validated against 62 materials)
    
    Attributes:
        id: Element UUID
        iso_code: ISO-19650 identifier
        status: Lifecycle state
        material_type: Stone material type
        created_at: Row creation timestamp (ISO 8601)
        low_poly_url: Presigned CDN URL (TTL 5min)
        bbox: 3D bounding box
        validation_report: Validation results from The Librarian
        glb_size_bytes: GLB file size (optional)
        triangle_count: Triangle count (optional)
    """
    id: UUID = Field(..., description="Element UUID")
    iso_code: str = Field(..., description="ISO-19650 identifier")
    status: ElementStatus = Field(..., description="Lifecycle state")
    material_type: str = Field(..., description="Stone material type (62 options)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    low_poly_url: Optional[str] = Field(None, description="Presigned CDN URL (TTL 5min)")
    bbox: Optional[BoundingBox] = Field(None, description="3D bounding box")
    validation_report: Optional[ValidationReport] = Field(None, description="Validation results")
    glb_size_bytes: Optional[int] = Field(None, description="GLB file size in bytes")
    triangle_count: Optional[int] = Field(None, description="Triangle count (performance)")
    
    @field_validator('material_type')
    @classmethod
    def validate_material_type(cls, v: str) -> str:
        """Validate material_type against 62 real materials."""
        if v not in VALID_MATERIALS:
            raise ValueError(f"Invalid material_type: '{v}'. Must be one of {len(VALID_MATERIALS)} valid materials.")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "iso_code": "GLPER.B-PAE0720.0701",
                "status": "validated",
                "material_type": "Montjuïc",
                "created_at": "2026-03-06T10:30:00Z",
                "low_poly_url": "https://d1234abcd.cloudfront.net/models/low-poly/550e8400.glb",
                "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]},
                "validation_report": {
                    "is_valid": True,
                    "errors": [],
                    "metadata": {"layer_count": 1, "object_count": 1}
                },
                "glb_size_bytes": 312456,
                "triangle_count": 987
            }
        }
```

#### 2.3 ElementNavigation Schema (reemplaza PartNavigationResponse)

```python
class ElementNavigationResponse(BaseModel):
    """
    Response for GET /api/elements/{id}/navigation endpoint.
    
    No breaking changes in structure, only renamed class for consistency.
    """
    prev_id: Optional[UUID] = Field(None, description="Previous element UUID (None if first)")
    next_id: Optional[UUID] = Field(None, description="Next element UUID (None if last)")
    current_index: int = Field(..., ge=1, description="1-based index of current element")
    total_count: int = Field(..., ge=0, description="Total elements in filtered set")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prev_id": None,
                "next_id": "987fcdeb-51a2-43e7-9876-543210fedcba",
                "current_index": 1,
                "total_count": 6
            }
        }
```

### Frontend Types (TypeScript)

**File:** `src/frontend/src/types/elements.ts`

```typescript
/**
 * Element types for 3D canvas rendering.
 * 
 * Contract: Must match backend Pydantic schemas exactly.
 * Breaking changes from PartCanvasItem: workshop_id/workshop_name removed, tipologia → material_type
 */

// Material type union (synced with backend MATERIAL_COLORS - 62 options)
export type MaterialType = 
  | "Montjuïc"         // DEFAULT (warm ochre)
  | "Ulldecona"        // Light cream
  | "Floresta"         // Golden sand
  | "Beix Anglès"
  | "Beix mallorca"
  // ... (full 62 types list in implementation)
  | "Pedra de colmenar"
  | "Ocean Black";

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
  id: string;                      // UUID
  iso_code: string;                // ISO-19650 identifier
  status: ElementStatus;
  material_type: MaterialType;     // One of 62 real stone types
  low_poly_url: string | null;     // CDN URL to GLB file
  bbox: BoundingBox | null;        // 3D bounding box
}

export interface ElementsListResponse {
  elements: Element[];
  filters_applied: Record<string, any>;
  meta: {
    total: number;
    filtered: number;
  };
}

export interface ElementDetail extends Element {
  created_at: string;              // ISO 8601 datetime
  validation_report: ValidationReport | null;
  glb_size_bytes: number | null;
  triangle_count: number | null;
}

export interface ElementNavigationResponse {
  prev_id: string | null;
  next_id: string | null;
  current_index: number;           // 1-based
  total_count: number;
}
```

### Database Changes (SQL)

**No new migrations required.** T-1501-DB already applied:
- `material_type TEXT` column added
- `workshop_id`, `workshop_name` columns dropped
- `bbox` JSONB column structure validated

**Application-Level Filtering:**
```sql
-- Service layer will apply this filter to return only render-ready elements
SELECT id, iso_code, status, material_type, low_poly_url, bbox
FROM blocks
WHERE is_archived = false
  AND low_poly_url IS NOT NULL      -- ✅ Must have GLB file
  AND bbox IS NOT NULL                -- ✅ Must have bounding box
  AND status = 'validated'            -- Optional filter
  AND material_type = 'Montjuïc'      -- Optional filter
ORDER BY created_at DESC;
```

## 3. API Interface

### 3.1 List Elements Endpoint

- **Endpoint:** `GET /api/elements`
- **Auth:** Service role (bypasses RLS for admin context)
- **Query Parameters:**
  - `status` (Optional[str]): Filter by lifecycle status (validated, in_fabrication, etc.)
  - `material_type` (Optional[str]): Filter by stone material (Montjuïc, Ulldecona, etc.)
  
**Request:**
```bash
GET /api/elements?status=validated&material_type=Montjuïc
```

**Response 200:**
```json
{
  "elements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "iso_code": "GLPER.B-PAE0720.0701",
      "status": "validated",
      "material_type": "Montjuïc",
      "low_poly_url": "https://d1234abcd.cloudfront.net/models/low-poly/550e8400_20260307T120000Z.glb",
      "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]}
    }
  ],
  "filters_applied": {"status": "validated", "material_type": "Montjuïc"},
  "meta": {"total": 6, "filtered": 1}
}
```

**Response 400 (Invalid Material):**
```json
{
  "detail": "Invalid material_type filter: 'InvalidMaterial'. Must be one of 62 valid materials (e.g., Montjuïc, Ulldecona, Floresta). See MATERIAL_COLORS dictionary for full list."
}
```

**Response 500 (Database Error):**
```json
{
  "detail": "Failed to fetch elements from database"
}
```

### 3.2 Get Element Detail Endpoint

- **Endpoint:** `GET /api/elements/{id}`
- **Auth:** Service role
- **Path Parameters:**
  - `id` (UUID): Element identifier

**Request:**
```bash
GET /api/elements/550e8400-e29b-41d4-a716-446655440000
```

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "iso_code": "GLPER.B-PAE0720.0701",
  "status": "validated",
  "material_type": "Montjuïc",
  "created_at": "2026-03-06T10:30:00Z",
  "low_poly_url": "https://d1234abcd.cloudfront.net/models/low-poly/550e8400.glb",
  "bbox": {"min": [-0.35, -0.70, -0.35], "max": [0.35, 0.70, 0.35]},
  "validation_report": {
    "is_valid": true,
    "errors": [],
    "metadata": {"layer_count": 1, "object_count": 1}
  },
  "glb_size_bytes": 312456,
  "triangle_count": 987
}
```

**Response 404 (Element Not Found):**
```json
{
  "detail": "Element with id '550e8400-e29b-41d4-a716-446655440000' not found"
}
```

### 3.3 Navigation Endpoint

- **Endpoint:** `GET /api/elements/{id}/navigation`
- **Auth:** Service role
- **Path Parameters:**
  - `id` (UUID): Current element identifier
- **Query Parameters:**
  - `status` (Optional[str]): Filter by status
  - `material_type` (Optional[str]): Filter by material

**Request:**
```bash
GET /api/elements/550e8400-e29b-41d4-a716-446655440000/navigation?status=validated
```

**Response 200:**
```json
{
  "prev_id": null,
  "next_id": "987fcdeb-51a2-43e7-9876-543210fedcba",
  "current_index": 1,
  "total_count": 6
}
```

**Response 404 (Element Not Found):**
```json
{
  "detail": "Element with id '550e8400-e29b-41d4-a716-446655440000' not found in filtered set"
}
```

## 4. Service Layer Architecture

### 4.1 ElementsService (replaces PartsService)

**File:** `src/backend/services/elements_service.py`

```python
"""
Business logic for elements listing operations.

Clean Architecture pattern:
- API Layer (api/elements.py): HTTP handling, validation delegation
- Service Layer (services/elements_service.py): Business logic, DB access
- Schemas (schemas.py): Pydantic models (DTOs)
"""

from typing import Optional, Dict, Any, List
from supabase import Client
from uuid import UUID

from schemas import Element, ElementsListResponse, BoundingBox, ElementStatus
from agent.constants import VALID_MATERIALS

class ElementsService:
    """Service for elements listing with render-ready filtering."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    def list_elements(
        self,
        status: Optional[str] = None,
        material_type: Optional[str] = None,
    ) -> ElementsListResponse:
        """
        List all render-ready elements with optional filtering.
        
        Render-Ready Filter (Applied Automatically):
        - low_poly_url IS NOT NULL (GLB file generated)
        - bbox IS NOT NULL (geometry metadata extracted)
        - is_archived = false (exclude deleted)
        
        Args:
            status: Filter by lifecycle status (optional)
            material_type: Filter by stone material (optional)
            
        Returns:
            ElementsListResponse with elements list and metadata
            
        Raises:
            ValueError: If material_type not in VALID_MATERIALS
            RuntimeError: If database query fails
        """
        # Validate material_type filter
        if material_type and material_type not in VALID_MATERIALS:
            raise ValueError(
                f"Invalid material_type filter: '{material_type}'. "
                f"Must be one of {len(VALID_MATERIALS)} valid materials."
            )
        
        # Build query with render-ready filter
        query = self.supabase.table("blocks").select(
            "id, iso_code, status, material_type, low_poly_url, bbox"
        ).eq("is_archived", False)
        
        # CRITICAL: Application-level filtering for render-ready elements
        query = query.not_.is_("low_poly_url", "null").not_.is_("bbox", "null")
        
        # Apply optional filters
        if status:
            query = query.eq("status", status)
        if material_type:
            query = query.eq("material_type", material_type)
        
        # Execute query
        response = query.order("created_at", desc=True).execute()
        
        # Transform to Element models
        elements = []
        for row in response.data:
            elements.append(Element(
                id=row["id"],
                iso_code=row["iso_code"],
                status=ElementStatus(row["status"]),
                material_type=row["material_type"],
                low_poly_url=self._apply_cdn_transformation(row["low_poly_url"]),
                bbox=BoundingBox(**row["bbox"]) if row["bbox"] else None
            ))
        
        return ElementsListResponse(
            elements=elements,
            filters_applied={"status": status, "material_type": material_type},
            meta={"total": len(response.data), "filtered": len(elements)}
        )
    
    def _apply_cdn_transformation(self, url: Optional[str]) -> Optional[str]:
        """Transform Supabase Storage URL to CDN URL (T-1001-INFRA pattern)."""
        # Implementation mirrors PartsService._apply_cdn_transformation
        pass
```

### 4.2 ElementDetailService (replaces PartDetailService)

**File:** `src/backend/services/element_detail_service.py`

```python
"""Business logic for element detail operations (US-010)."""

from typing import Optional
from supabase import Client
from uuid import UUID

from schemas import ElementDetail, ElementStatus, BoundingBox, ValidationReport

class ElementDetailService:
    """Service for fetching detailed element information."""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    def get_element_detail(self, element_id: UUID) -> ElementDetail:
        """
        Fetch detailed element information by ID.
        
        Args:
            element_id: Element UUID
            
        Returns:
            ElementDetail with all metadata
            
        Raises:
            ValueError: If element not found
            RuntimeError: If database query fails
        """
        response = self.supabase.table("blocks").select(
            "id, iso_code, status, material_type, created_at, low_poly_url, bbox, "
            "validation_report, glb_size_bytes, triangle_count"
        ).eq("id", str(element_id)).execute()
        
        if not response.data:
            raise ValueError(f"Element with id '{element_id}' not found")
        
        row = response.data[0]
        
        # Parse validation_report JSONB
        validation_report = None
        if row.get("validation_report"):
            validation_report = ValidationReport(**row["validation_report"])
        
        return ElementDetail(
            id=row["id"],
            iso_code=row["iso_code"],
            status=ElementStatus(row["status"]),
            material_type=row["material_type"],
            created_at=row["created_at"],
            low_poly_url=self._apply_cdn_transformation(row["low_poly_url"]),
            bbox=BoundingBox(**row["bbox"]) if row["bbox"] else None,
            validation_report=validation_report,
            glb_size_bytes=row.get("glb_size_bytes"),
            triangle_count=row.get("triangle_count")
        )
    
    def _apply_cdn_transformation(self, url: Optional[str]) -> Optional[str]:
        """Transform Supabase Storage URL to CDN URL."""
        pass
```

### 4.3 NavigationService (update for Element)

**File:** `src/backend/services/navigation_service.py`

- Rename `get_adjacent_parts` → `get_adjacent_elements`
- Update query to filter by `low_poly_url IS NOT NULL AND bbox IS NOT NULL`
- Return `ElementNavigationResponse` instead of `PartNavigationResponse`

## 5. Test Cases Checklist

### Happy Path (HP)
- [ ] **HP-01**: GET /api/elements returns all render-ready elements (6/6 expected)
- [ ] **HP-02**: GET /api/elements?status=validated filters correctly
- [ ] **HP-03**: GET /api/elements?material_type=Montjuïc filters correctly
- [ ] **HP-04**: GET /api/elements/{id} returns ElementDetail with all fields
- [ ] **HP-05**: GET /api/elements/{id}/navigation returns prev/next IDs correctly
- [ ] **HP-06**: Response schemas match TypeScript interfaces exactly (contract test)

### Edge Cases (EC)
- [ ] **EC-01**: GET /api/elements with no filters returns only elements with low_poly_url AND bbox (not nulls)
- [ ] **EC-02**: GET /api/elements with multiple filters (status + material_type) combines correctly
- [ ] **EC-03**: GET /api/elements/{id} for element without validation_report returns null gracefully
- [ ] **EC-04**: GET /api/elements/{id}/navigation for first element returns prev_id=null
- [ ] **EC-05**: GET /api/elements/{id}/navigation for last element returns next_id=null
- [ ] **EC-06**: material_type field validates against 62-item MATERIAL_COLORS dictionary
- [ ] **EC-07**: Elements with tipologia="capitel" (old field) are excluded from response (migration cleanup verification)

### Security/Errors (ERR)
- [ ] **ERR-01**: GET /api/elements?material_type=InvalidMaterial returns 400 with descriptive error
- [ ] **ERR-02**: GET /api/elements?status=invalid_status returns 400
- [ ] **ERR-03**: GET /api/elements/{invalid-uuid} returns 400 (malformed UUID)
- [ ] **ERR-04**: GET /api/elements/{non-existent-uuid} returns 404
- [ ] **ERR-05**: Pydantic validation rejects material_type="Stone" (old enum value, now invalid)
- [ ] **ERR-06**: Pydantic validation rejects material_type="" (empty string)
- [ ] **ERR-07**: Database connection failure returns 500 with generic error message

### Integration (INT)
- [ ] **INT-01**: Query performance <500ms for 6 elements (baseline: 28ms)
- [ ] **INT-02**: CDN URL transformation applied correctly (T-1001-INFRA integration)
- [ ] **INT-03**: MATERIAL_COLORS import from agent.constants succeeds in backend context
- [ ] **INT-04**: Validation errors reference current 62-material list in error messages
- [ ] **INT-05**: Redis cache integration for navigation (T-1003-BACK pattern)

## 6. Files to Create/Modify

### Create
- `src/backend/services/elements_service.py` (~200 lines, mirrors PartsService structure)
- `src/backend/services/element_detail_service.py` (~150 lines, mirrors PartDetailService structure)
- `src/backend/api/elements.py` (~120 lines, mirrors parts.py structure)
- `docs/US-015/T-1504-BACK-TechnicalSpec.md` (this file)

### Modify
- `src/backend/schemas.py`:
  - Add `Element`, `ElementsListResponse`, `ElementDetail`, `ElementNavigationResponse`
  - Add `ElementStatus` enum (rename BlockStatus for clarity)
  - Keep old schemas (`PartCanvasItem`, `PartsListResponse`) temporarily for backward compatibility
  - Add Pydantic validator for material_type field
  - Import VALID_MATERIALS from agent.constants

- `src/backend/services/navigation_service.py`:
  - Rename `get_adjacent_parts` → `get_adjacent_elements`
  - Update query filters (add `low_poly_url IS NOT NULL AND bbox IS NOT NULL`)
  - Return `ElementNavigationResponse`

- `src/backend/constants.py`:
  - Add `ERROR_MSG_INVALID_MATERIAL_TYPE` constant
  - Update `PARTS_LIST_SELECT_FIELDS` → `ELEMENTS_LIST_SELECT_FIELDS` (remove workshop_id, workshop_name, tipologia; add material_type)

- `tests/integration/test_parts_api.py`:
  - Rename to `test_elements_api.py`
  - Update 30-40 test cases to use Element schemas
  - Update fixtures to use material_type="Montjuïc" instead of tipologia="capitel"
  - Add tests for material_type validation (62 materials)
  - Update assertions to exclude workshop_id/workshop_name fields

- `tests/unit/test_parts_service.py`:
  - Rename to `test_elements_service.py`
  - Update mock responses to match Element schema
  - Add test cases for render-ready filtering (low_poly_url + bbox not null)

## 7. Reusable Components/Patterns

### From Existing Codebase
- **Clean Architecture Pattern** (T-004-BACK, T-0501-BACK):
  - API Layer: HTTP handling, validation delegation, error mapping
  - Service Layer: Business logic, DB queries, transformations
  - Constants: Centralized strings, error messages

- **CDN URL Transformation** (T-1001-INFRA):
  - `_apply_cdn_transformation()` method in service layer
  - Transforms Supabase Storage URLs to CloudFront URLs
  - Reuse exact pattern from PartsService

- **Pydantic Validation Pattern** (schemas.py):
  - `@field_validator` decorator for custom validation
  - `Config.json_schema_extra` for OpenAPI examples
  - Enum validation with descriptive error messages

- **Query Filtering Pattern** (T-0501-BACK):
  - `.eq()`, `.not_.is_()` Supabase client methods
  - `.order()`, `.execute()` chaining
  - Error handling with try/except → HTTPException

- **Redis Caching Pattern** (T-1003-BACK):
  - Cache navigation results with 5-minute TTL
  - Key format: `navigation:{element_id}:{filters_hash}`
  - Reuse NavigationService caching logic

### New Patterns to Document
- **Application-Level Filtering for Render-Ready Elements**:
  ```python
  query = query.not_.is_("low_poly_url", "null").not_.is_("bbox", "null")
  ```
  - Pattern to be added to `memory-bank/systemPatterns.md`
  - Ensures only fully processed elements are returned
  - Alternative to database CHECK constraints (preserves flexibility)

- **Cross-Module Material Validation**:
  ```python
  from agent.constants import VALID_MATERIALS
  
  @field_validator('material_type')
  @classmethod
  def validate_material_type(cls, v: str) -> str:
      if v not in VALID_MATERIALS:
          raise ValueError(f"Invalid material: {v}")
      return v
  ```
  - Single source of truth for material validation
  - Synchronizes backend API with agent extraction logic
  - Pattern to be added to `memory-bank/systemPatterns.md`

## 8. Migration Strategy & Backward Compatibility

### Deprecation Plan (Dual Endpoints)
To avoid breaking production frontend (US-005, US-010), maintain both endpoints during transition:

**Phase 1: Introduce New Endpoints (T-1504-BACK)**
- Add `/api/elements` (new)
- Add `/api/elements/{id}` (new)
- Add `/api/elements/{id}/navigation` (new)
- Keep `/api/parts` endpoints active (unchanged)
- Both endpoints return data from same `blocks` table

**Phase 2: Frontend Refactor (T-1505-FRONT)**
- Update `Dashboard3D` to consume `/api/elements`
- Update `ModelLoader` to consume `/api/elements/{id}`
- Update `PartDetailModal` navigation to consume `/api/elements/{id}/navigation`
- Remove `workshop_id` references from UI

**Phase 3: Deprecation (Future Sprint)**
- Add deprecation warnings to `/api/parts` endpoints (HTTP header `Deprecated: true`)
- Update OpenAPI docs with migration guide
- Schedule removal for Sprint 8

### Database Backward Compatibility
- `material_type` column already exists (T-1501-DB applied)
- Old `tipologia` column removed safe migration
- No foreign key constraints to `workshops` table (verified in T-1501-DB audit)

## 9. OpenAPI Documentation Updates

### FastAPI Docstrings (Auto-Generated OpenAPI)
- Add detailed docstrings to all `/api/elements` endpoints
- Include examples with real material types (Montjuïc, Ulldecona, Floresta)
- Document breaking changes in migration guide section
- Add deprecation notices to `/api/parts` endpoints

### Breaking Changes Documentation

**For Frontend Consumers:**

```markdown
# API v2 Migration Guide: Parts → Elements

## Breaking Changes

### 1. Endpoint Renaming
- ❌ `GET /api/parts` → ✅ `GET /api/elements`
- ❌ `GET /api/parts/{id}` → ✅ `GET /api/elements/{id}`
- ❌ `GET /api/parts/{id}/navigation` → ✅ `GET /api/elements/{id}/navigation`

### 2. Schema Changes

**PartCanvasItem → Element**
- ❌ Removed: `workshop_id`, `workshop_name`
- ❌ Removed: `tipologia` (string)
- ✅ Added: `material_type` (string, validated against 62 real materials)

**Example v1 (deprecated):**
```json
{
  "id": "...",
  "tipologia": "capitel",
  "workshop_id": "...",
  "workshop_name": "Taller Granollers"
}
```

**Example v2 (current):**
```json
{
  "id": "...",
  "material_type": "Montjuïc"
}
```

### 3. Filtering Changes
- ❌ `?tipologia=capitel` → ✅ `?material_type=Montjuïc`
- ❌ `?workshop_id=...` → ✅ (removed, workshops not in MVP)

### 4. Material Type Validation
- Old: Free string (`"Piedra"`, `"Stone"`, custom values)
- New: One of 62 real stone types from Sagrada Família (`"Montjuïc"`, `"Ulldecona"`, etc.)
- Invalid materials return 400 error with list of valid options

### 5. Render-Ready Filtering
Elements are now automatically filtered to return ONLY those with:
- `low_poly_url IS NOT NULL` (GLB file generated)
- `bbox IS NOT NULL` (geometry metadata extracted)

Elements in "processing" or "uploaded" states are **excluded** from response.
```

## 10. Performance Targets

Based on T-0503-DB performance validation:

- **Query Latency:** <500ms for 1000 elements (baseline: 28ms for 6 elements)
- **Response Size:** <200KB gzipped (current: ~15KB for 6 elements)
- **Database Index:** Use existing `idx_blocks_canvas_query` (covers `status`, `material_type`, `is_archived`)
- **CDN Cache:** 5-minute TTL on presigned URLs (T-1001-INFRA)
- **Redis Cache:** 5-minute TTL on navigation results (T-1003-BACK)

## 11. Security Considerations

### RLS Bypass (Service Role)
- Backend uses service role key (bypasses Row Level Security)
- Safe for admin context (internal API)
- Future: Add user authentication + RLS policies for multi-tenancy

### Input Validation
- `material_type` validated against whitelist (62 materials)
- `status` validated against ElementStatus enum
- UUID format validation for `element_id` path parameter

### SQL Injection Prevention
- Supabase client sanitizes all query parameters
- No raw SQL strings in service layer

### Error Message Sanitization
- Do NOT expose database column names in error messages
- Use generic "Failed to fetch elements" for DB errors
- Expose validation errors only for client-side issues (400 errors)

## 12. Next Steps

This specification is **READY FOR TDD-RED PHASE**. Use the following command:

```bash
:tdd-red T-1504-BACK Element API
```

=============================================
READY FOR TDD-RED PHASE - Copy these values:
=============================================
Ticket ID:       T-1504-BACK
Feature name:    Element API Integration with 62 Material Types
Key test cases:  
  - HP-01: GET /api/elements returns all render-ready elements (6/6)
  - HP-06: Response schemas match TypeScript interfaces exactly
  - EC-01: Only elements with low_poly_url AND bbox returned
  - EC-06: material_type validates against 62-item MATERIAL_COLORS
  - ERR-01: Invalid material_type returns 400 with descriptive error
  - ERR-05: material_type="Stone" rejected (old enum value)
  - INT-03: MATERIAL_COLORS import from agent.constants succeeds

Files to create:
  - src/backend/services/elements_service.py
  - src/backend/services/element_detail_service.py
  - src/backend/api/elements.py
  - tests/integration/test_elements_api.py
  - tests/unit/test_elements_service.py

Files to modify:
  - src/backend/schemas.py (add Element, ElementsListResponse, ElementDetail schemas)
  - src/backend/services/navigation_service.py (rename methods, update filters)
  - src/backend/constants.py (add ELEMENTS_LIST_SELECT_FIELDS, ERROR_MSG_INVALID_MATERIAL_TYPE)
  - tests/integration/test_parts_api.py → rename + update 30-40 test cases
  - tests/unit/test_parts_service.py → rename + update fixtures
=============================================

## 13. Definition of Done (DoD) Checklist

**Code Implementation:**
- [ ] All schemas (Element, ElementsListResponse, ElementDetail, ElementNavigationResponse) implemented in schemas.py
- [ ] ElementsService implemented with render-ready filtering (low_poly_url + bbox not null)
- [ ] ElementDetailService implemented
- [ ] API endpoints (/api/elements, /api/elements/{id}, /api/elements/{id}/navigation) implemented
- [ ] Navigation service updated (rename methods, add filters)
- [ ] Constants updated (ELEMENTS_LIST_SELECT_FIELDS, error messages)

**Testing:**
- [ ] 30-40 backend tests updated from PartCanvasItem to Element
- [ ] 6 test suites PASSING (HP, EC, ERR, INT)
- [ ] Backend baseline maintained: 119/119 tests PASS (zero regression)
- [ ] Material validation tested with all 62 MATERIAL_COLORS entries
- [ ] Contract alignment verified: Pydantic schemas match TypeScript interfaces field-by-field

**Documentation:**
- [ ] OpenAPI docstrings added to all endpoints
- [ ] Migration guide created (Parts → Elements)
- [ ] Deprecation notices added to old /api/parts endpoints
- [ ] memory-bank/systemPatterns.md updated with new patterns
- [ ] memory-bank/activeContext.md updated (T-1504-BACK marked DONE)

**Integration:**
- [ ] MATERIAL_COLORS imported successfully from agent.constants
- [ ] CDN URL transformation working (T-1001-INFRA integration)
- [ ] Redis caching working for navigation (T-1003-BACK pattern)
- [ ] Query performance <500ms validated

**Production-Ready:**
- [ ] Zero debug artifacts (print statements, commented code)
- [ ] Google Style docstrings on all public methods
- [ ] Type hints complete (Python 3.11+)
- [ ] Error messages user-friendly (no technical jargon)
- [ ] Backward compatibility maintained (old /api/parts endpoints still working)
