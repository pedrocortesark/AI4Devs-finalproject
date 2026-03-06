# JSON CONTRACTS: Backend ↔ Frontend API

**Fecha:** 2026-03-05  
**Epic:** US-015 - Refactorización E2E del Flujo de Ingesta 3D  
**Versión:** 1.0.0  
**Status:** 🔒 **CANONICAL** — This document is the source of truth  

---

## 📋 Executive Summary

Este documento define los **contratos JSON obligatorios** entre Backend (FastAPI + Pydantic) y Frontend (React + TypeScript). **Todo código de producción DEBE cumplir estos contratos** antes de ser mergeado a `main`.

### 🎯 Objetivos del Contrato

1. **Type Safety End-to-End**: Pydantic valida en backend, Zod valida en frontend
2. **Zero Runtime Surprises**: Rechazar datos inválidos antes de causar crashes
3. **Self-Documenting API**: OpenAPI auto-generado desde Pydantic schemas
4. **TDD Foundation**: Tests de contrato garantizan alineación backend-frontend

### 🚨 Reglas Inquebrantables

| Regla | Descripción | Enforcement |
|-------|-------------|-------------|
| **R1: Absolute URLs** | `low_poly_url` SIEMPRE `https://...` (nunca relativa, nunca null) | Pydantic `HttpUrl` + Zod `.url()` |
| **R2: Required Geometry** | `bbox` SIEMPRE presente (elementos sin geometría no se devuelven) | Pydantic required field + Zod no `.nullable()` |
| **R3: Enum Sync** | `ElementStatus` y `MaterialType` enums IGUALES en Python y TypeScript | Unit tests cruzan valores |
| **R4: UUID Format** | UUIDs como `string` en JSON (no objetos) | Pydantic `UUID` serializa a `str` |
| **R5: ISO Timestamps** | Datetimes en ISO 8601 con timezone (`YYYY-MM-DDTHH:MM:SSZ`) | Pydantic `datetime` + `.isoformat()` |
| **R6: BBox Structure** | `{"min": [x,y,z], "max": [x,y,z]}` exacto (3 floats) | Validators en ambos lados |

### 📝 Nota sobre `iso_code`

El campo `iso_code` se extrae del **Rhino UserString** con la clave `"Codi"` durante el procesamiento del archivo `.3dm`:

```python
# Durante geometría processing (src/agent/tasks/geometry_processing.py)
user_strings = rhino_object.Attributes.GetUserStrings()
iso_code = user_strings.Get("Codi", "UNKNOWN")  # Default si no existe

# Se guarda en la base de datos
cursor.execute(
    "INSERT INTO blocks (id, iso_code, ...) VALUES (%s, %s, ...)",
    (block_id, iso_code, ...)
)
```

**Formato esperado:** Texto alfanumérico legible para humanos (ej: `"SF-C12-D-001"`, `"EL-PIEDRA-042"`).  
**Propósito:** Identificador único arquitectónico definido por el equipo de diseño de la Sagrada Família.

---

## 🔗 Contract 1: Element (Dashboard 3D)

**Endpoint:** `GET /api/elements`  
**User Story:** US-005 (Dashboard 3D Interactivo)  
**Purpose:** Listar elementos arquitectónicos procesados para renderizar en canvas Three.js

**⚠️ IMPORTANTE:** Este endpoint solo devuelve elementos completamente procesados (filtro: `WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL`)

### Schema Canónico

```typescript
// ========================================
// TypeScript Interface (Frontend)
// File: src/frontend/src/types/elements.ts
// ========================================

export interface BoundingBox {
  min: [number, number, number];  // ✅ Tuple exacto (no number[])
  max: [number, number, number];
}

export enum ElementStatus {
  Uploaded = "uploaded",
  Processing = "processing",
  Validated = "validated",
  Rejected = "rejected",
  ErrorProcessing = "error_processing",  // ✅ Snake_case como en BD
  InFabrication = "in_fabrication",
  Completed = "completed",
  Archived = "archived",
}

export enum MaterialType {
  Stone = "Stone",          // ✅ Architectural materials
  Ceramic = "Ceramic",
}

export interface Element {
  id: string;                      // UUID as string (not UUID object)
  iso_code: string;                // Extracted from Rhino UserString key "Codi" (e.g., "SF-C12-D-001")
  status: ElementStatus;           // Enum value
  material_type: MaterialType;     // ✅ Enum with 2 values (not free string)
  low_poly_url: string;            // ✅ REQUIRED - absolute HTTPS URL (elements without geometry not returned)
  bbox: BoundingBox;               // ✅ REQUIRED - geometry processed
}

export interface ElementsListResponse {
  elements: Element[];              // ✅ Renombrado de parts → elements
  count: number;
  filters_applied: Record<string, string | null>;
}
```

```python
# ========================================
# Pydantic Schema (Backend)
# File: src/backend/schemas.py
# ========================================

from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import List
from uuid import UUID
from enum import Enum

class ElementStatus(str, Enum):
    """Synchronized with frontend ElementStatus enum."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR_PROCESSING = "error_processing"
    IN_FABRICATION = "in_fabrication"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class MaterialType(str, Enum):
    """Architectural material types."""
    STONE = "Stone"        # Stone elements
    CERAMIC = "Ceramic"    # Ceramic elements

class BoundingBox(BaseModel):
    """3D bounding box for spatial layout."""
    min: List[float] = Field(..., min_length=3, max_length=3)
    max: List[float] = Field(..., min_length=3, max_length=3)

    @field_validator('min', 'max')
    @classmethod
    def validate_coordinates(cls, v):
        if len(v) != 3:
            raise ValueError('Must contain exactly 3 coordinates [x, y, z]')
        return v

class Element(BaseModel):
    """Architectural element for 3D canvas rendering (only processed geometry)."""
    id: UUID
    iso_code: str = Field(..., min_length=1, max_length=50, description="From Rhino UserString 'Codi'")
    status: ElementStatus
    material_type: MaterialType  # ✅ Enum enforced
    low_poly_url: HttpUrl  # ✅ REQUIRED - always absolute HTTPS URL
    bbox: BoundingBox      # ✅ REQUIRED - geometry always processed

    class Config:
        use_enum_values = True  # Serialize enum as string value

class ElementsListResponse(BaseModel):
    elements: List[Element]  # ✅ Renombrado de parts → elements
    count: int = Field(..., ge=0)
    filters_applied: dict
```

### Zod Validation (Frontend Runtime)

```typescript
// ========================================
// Zod Schema for Runtime Validation
// File: src/frontend/src/schemas/elements.schema.ts
// ========================================

import { z } from 'zod';

export const BoundingBoxSchema = z.object({
  min: z.tuple([z.number(), z.number(), z.number()]),  // ✅ Exact tuple
  max: z.tuple([z.number(), z.number(), z.number()]),
});

export const ElementStatusSchema = z.enum([
  "uploaded",
  "processing",
  "validated",
  "rejected",
  "error_processing",
  "in_fabrication",
  "completed",
  "archived",
]);

export const MaterialTypeSchema = z.enum(["Stone", "Ceramic"]);

export const ElementSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string().min(1).max(50),  // From Rhino UserString "Codi"
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,  // ✅ Enum enforced
  low_poly_url: z.string().url()  // ✅ REQUIRED - no nullable
    .refine(
      (url) => url.startsWith('https://'),
      { message: "low_poly_url must be HTTPS absolute URL" }
    ),
  bbox: BoundingBoxSchema,  // ✅ REQUIRED - no nullable
});

export const ElementsListResponseSchema = z.object({
  elements: z.array(ElementSchema),  // ✅ Renombrado de parts → elements
  count: z.number().int().nonnegative(),
  filters_applied: z.record(z.string(), z.string().nullable()),
});

// ========================================
// Usage in API Service
// ========================================

export async function fetchElementsList(params: ElementsQueryParams): Promise<ElementsListResponse> {
  const response = await fetch('/api/elements?' + new URLSearchParams(params));
  const data = await response.json();
  
  // ✅ Runtime validation with Zod
  const validated = ElementsListResponseSchema.parse(data);
  return validated;
}
```

### Payload Examples

#### ✅ Valid Payload

```json
{
  "elements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "iso_code": "SF-C12-D-001",
      "status": "validated",
      "material_type": "Stone",
      "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/low-poly/550e8400.glb",
      "bbox": {
        "min": [-2.5, 0.0, -2.5],
        "max": [2.5, 5.0, 2.5]
      }
    },
    {
      "id": "987fcdeb-51a2-43e7-9876-543210fedcba",
      "iso_code": "SF-C12-D-002",
      "status": "validated",
      "material_type": "Ceramic",
      "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/low-poly/987fcdeb.glb",
      "bbox": {
        "min": [-1.0, 0.0, -1.0],
        "max": [1.0, 3.0, 1.0]
      }
    }
  ],
  "count": 2,
  "filters_applied": {
    "status": "validated",
    "material_type": null
  }
}
```

#### ❌ Invalid Payload 1: Relative URL

```json
{
  "elements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "iso_code": "SF-C12-D-001",
      "status": "validated",
      "material_type": "Stone",
      "low_poly_url": "models/low-poly/550e8400.glb",  // ❌ Relative URL
      "bbox": {"min": [-2.5, 0, -2.5], "max": [2.5, 5, 2.5]}
    }
  ],
  "count": 1,
  "filters_applied": {}
}
```

**Error:**
- **Pydantic:** `ValidationError: Input should be a valid URL`
- **Zod:** `ZodError: low_poly_url must be HTTPS absolute URL`

#### ❌ Invalid Payload 2: Invalid MaterialType Value

```json
{
  "elements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "iso_code": "SF-C12-D-001",
      "status": "validated",
      "material_type": "capitel",  // ❌ Not in enum ["Stone", "Ceramic"]
      "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/550e8400.glb",
      "bbox": {"min": [-2.5, 0, -2.5], "max": [2.5, 5, 2.5]}
    }
  ],
  "count": 1,
  "filters_applied": {}
}
```

**Error:**
- **Pydantic:** `ValidationError: Input should be 'Stone' or 'Ceramic'`
- **Zod:** `ZodError: Invalid enum value. Expected 'Stone' | 'Ceramic', received 'capitel'`

#### ❌ Invalid Payload 3: BBox with Wrong Length

```json
{
  "elements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "iso_code": "SF-C12-D-001",
      "status": "validated",
      "material_type": "Stone",
      "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/550e8400.glb",
      "bbox": {
        "min": [-2.5, 0.0],  // ❌ Only 2 coordinates (needs 3)
        "max": [2.5, 5.0, 2.5]
      }
    }
  ],
  "count": 1,
  "filters_applied": {}
}
```

**Error:**
- **Pydantic:** `ValidationError: Must contain exactly 3 coordinates [x, y, z]`
- **Zod:** `ZodError: Expected array of length 3 at "elements[0].bbox.min"`

---

## 🔗 Contract 2: Element Detail (Modal 3D Viewer)

**Endpoint:** `GET /api/elements/{id}`  
**User Story:** US-010 (Visor 3D Web)  
**Purpose:** Detalles completos de un elemento arquitectónico para modal con viewer 3D

### Schema Canónico

```typescript
// ========================================
// TypeScript Interface (Frontend)
// File: src/frontend/src/types/elements.ts
// ========================================

export interface ValidationReport {
  is_valid: boolean;
  errors: Array<{
    category: string;
    target: string | null;
    message: string;
  }>;
  metadata: Record<string, any>;
  validated_at: string | null;  // ISO 8601 timestamp
  validated_by: string | null;
}

export interface ElementDetail {
  id: string;                       // UUID
  iso_code: string;                 // From Rhino UserString "Codi"
  status: ElementStatus;
  material_type: MaterialType;      // ✅ Enum ["Stone", "Ceramic"]
  created_at: string;               // ✅ ISO 8601: "2026-03-05T10:30:00Z"
  low_poly_url: string;             // ✅ REQUIRED - HTTPS absolute URL
  bbox: BoundingBox;                // ✅ REQUIRED - geometry processed
  validation_report: ValidationReport | null;
  glb_size_bytes: number | null;    // File size in bytes
  triangle_count: number | null;    // Triangles count
}
```

```python
# ========================================
# Pydantic Schema (Backend)
# File: src/backend/schemas.py
# ========================================

from datetime import datetime
from typing import Optional

class ValidationErrorItem(BaseModel):
    category: str
    target: Optional[str] = None
    message: str

class ValidationReport(BaseModel):
    is_valid: bool
    errors: List[ValidationErrorItem] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None

class ElementDetailResponse(BaseModel):
    """Full element details for 3D viewer modal."""
    id: UUID
    iso_code: str = Field(..., description="From Rhino UserString 'Codi'")
    status: ElementStatus
    material_type: MaterialType  # ✅ Enum enforced
    created_at: datetime  # ✅ Pydantic auto-serializes to ISO 8601
    low_poly_url: HttpUrl  # ✅ REQUIRED - always HTTPS absolute
    bbox: BoundingBox      # ✅ REQUIRED - geometry always processed
    validation_report: Optional[ValidationReport] = None
    glb_size_bytes: Optional[int] = Field(None, ge=0)
    triangle_count: Optional[int] = Field(None, ge=0)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),  # ✅ Force ISO 8601 with Z
        }
```

### Zod Validation (Frontend Runtime)

```typescript
// ========================================
// Zod Schema
// File: src/frontend/src/schemas/elements.schema.ts
// ========================================

export const ValidationErrorItemSchema = z.object({
  category: z.string(),
  target: z.string().nullable(),
  message: z.string(),
});

export const ValidationReportSchema = z.object({
  is_valid: z.boolean(),
  errors: z.array(ValidationErrorItemSchema),
  metadata: z.record(z.any()),
  validated_at: z.string().datetime().nullable(),  // ✅ ISO 8601 validation
  validated_by: z.string().nullable(),
});

export const ElementDetailSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string(),  // From Rhino UserString "Codi"
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,  // ✅ Enum enforced
  created_at: z.string().datetime(),  // ✅ Validates ISO 8601 format
  low_poly_url: z.string().url()  // ✅ REQUIRED - no nullable
    .refine(
      (url) => url.startsWith('https://'),
      { message: "low_poly_url must be HTTPS absolute URL" }
    ),
  bbox: BoundingBoxSchema,  // ✅ REQUIRED - no nullable
  validation_report: ValidationReportSchema.nullable(),
  glb_size_bytes: z.number().int().nonnegative().nullable(),
  triangle_count: z.number().int().nonnegative().nullable(),
});

// ========================================
// Usage with Error Handling
// ========================================

export async function getElementDetail(id: string): Promise<ElementDetail> {
  const response = await fetch(`/api/elements/${id}`);
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  const data = await response.json();
  
  try {
    const validated = ElementDetailSchema.parse(data);
    return validated;
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error('Contract violation:', error.errors);
      throw new Error(`Invalid API response: ${error.errors[0].message}`);
    }
    throw error;
  }
}
```

### Payload Examples

#### ✅ Valid Payload

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "iso_code": "SF-C12-D-001",
  "status": "validated",
  "material_type": "Stone",
  "created_at": "2026-03-05T10:30:00Z",
  "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/low-poly/550e8400.glb",
  "bbox": {
    "min": [-2.5, 0.0, -2.5],
    "max": [2.5, 5.0, 2.5]
  },
  "validation_report": {
    "is_valid": true,
    "errors": [],
    "metadata": {
      "total_objects": 42,
      "layer_count": 5
    },
    "validated_at": "2026-03-05T09:15:00Z",
    "validated_by": "librarian-agent-v1.0"
  },
  "glb_size_bytes": 425984,
  "triangle_count": 1024
}
```

#### ❌ Invalid Payload 1: Wrong Timestamp Format

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "iso_code": "SF-C12-D-001",
  "status": "validated",
  "material_type": "Stone",
  "created_at": "05/03/2026 10:30",  // ❌ Not ISO 8601
  "low_poly_url": "https://xyz.supabase.co/storage/v1/object/public/models/550e8400.glb",
  "bbox": {
    "min": [-2.5, 0.0, -2.5],
    "max": [2.5, 5.0, 2.5]
  },
  "validation_report": null,
  "glb_size_bytes": null,
  "triangle_count": null
}
```

**Error:**
- **Zod:** `ZodError: Invalid datetime string at "created_at"`

#### ❌ Invalid Payload 2: Negative File Size

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "iso_code": "SF-C12-D-001",
  "status": "validated",
  "material_type": "Ceramic",
  "created_at": "2026-03-05T10:30:00Z",
  "low_poly_url": "https://example.com/model.glb",
  "bbox": {
    "min": [-2.5, 0.0, -2.5],
    "max": [2.5, 5.0, 2.5]
  },
  "validation_report": null,
  "glb_size_bytes": -500,  // ❌ Negative size
  "triangle_count": 1024
}
```

**Error:**
- **Pydantic:** `ValidationError: Input should be greater than or equal to 0`
- **Zod:** `ZodError: Number must be non-negative at "glb_size_bytes"`

---

## 🧪 Contract Testing

### Backend Tests (pytest)

```python
# ========================================
# Contract Tests
# File: tests/integration/test_api_contracts.py
# ========================================

import pytest
from fastapi.testclient import TestClient
from src.backend.main import app
from src.backend.schemas import ElementsListResponse, ElementDetailResponse

client = TestClient(app)

def test_get_elements_contract_compliance():
    """Verify GET /api/elements response matches ElementsListResponse schema."""
    response = client.get("/api/elements?limit=10")
    assert response.status_code == 200
    
    # Parse with Pydantic (throws ValidationError if contract violated)
    data = ElementsListResponse(**response.json())
    
    # Schema validations
    assert isinstance(data.elements, list)
    assert data.count >= 0
    assert isinstance(data.filters_applied, dict)
    
    # Field validations
    for element in data.elements:
        assert element.id is not None  # UUID
        assert len(element.iso_code) >= 1
        assert element.status in ["uploaded", "processing", "validated", ...]
        assert element.material_type in ["Stone", "Ceramic"]  # ✅ Enum enforced
        
        # Critical: low_poly_url MUST be absolute HTTPS (never null)
        assert str(element.low_poly_url).startswith("https://"), \
            f"low_poly_url must be HTTPS: {element.low_poly_url}"
        
        # Critical: bbox MUST exist (never null)
        assert element.bbox is not None, "bbox is required for all elements"

def test_get_element_detail_contract_compliance():
    """Verify GET /api/elements/{id} response matches ElementDetailResponse schema."""
    # Setup: Create test element
    test_id = "550e8400-e29b-41d4-a716-446655440000"
    
    response = client.get(f"/api/elements/{test_id}")
    assert response.status_code == 200
    
    # Parse with Pydantic
    data = ElementDetailResponse(**response.json())
    
    # Timestamp format validation
    assert data.created_at.tzinfo is not None, "created_at must have timezone"
    assert "T" in data.created_at.isoformat(), "created_at must be ISO 8601"
    
    # Required fields validation
    assert data.low_poly_url is not None, "low_poly_url is required"
    assert data.bbox is not None, "bbox is required"
    
    # Optional fields validation
    if data.glb_size_bytes is not None:
        assert data.glb_size_bytes >= 0
    if data.triangle_count is not None:
        assert data.triangle_count >= 0

def test_reject_relative_url():
    """Ensure backend rejects relative URLs in low_poly_url."""
    from pydantic import ValidationError
    from src.backend.schemas import Element
    
    with pytest.raises(ValidationError) as exc_info:
        Element(
            id="550e8400-e29b-41d4-a716-446655440000",
            iso_code="SF-C12-D-001",
            status="validated",
            tipologia="Piedra",
            low_poly_url="models/part.glb",  # ❌ Relative
            bbox={"min": [-2.5, 0, -2.5], "max": [2.5, 5, 2.5]}
        )
    
    assert "valid URL" in str(exc_info.value)

def test_reject_invalid_material_type():
    """Ensure backend rejects material_type values outside enum."""
    from pydantic import ValidationError
    from src.backend.schemas import Element
    
    with pytest.raises(ValidationError) as exc_info:
        Element(
            id="550e8400-e29b-41d4-a716-446655440000",
            iso_code="SF-C12-D-001",
            status="validated",
            material_type="capitel",  # ❌ Not in ["Stone", "Ceramic"]
            low_poly_url="https://example.com/model.glb",
            bbox={"min": [-2.5, 0, -2.5], "max": [2.5, 5, 2.5]}
        )
    
    assert "Stone" in str(exc_info.value) or "Ceramic" in str(exc_info.value)
```

### Frontend Tests (Vitest)

```typescript
// ========================================
// Contract Tests
// File: src/frontend/src/schemas/elements.schema.test.ts
// ========================================

import { describe, it, expect } from 'vitest';
import { ElementSchema, ElementDetailSchema } from './elements.schema';
import { z } from 'zod';

describe('Element Contract', () => {
  it('should accept valid payload', () => {
    const validPayload = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Stone",
      low_poly_url: "https://xyz.supabase.co/storage/v1/object/public/models/550e8400.glb",
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      }
    };
    
    const result = ElementSchema.parse(validPayload);
    expect(result).toEqual(validPayload);
  });

  it('should reject relative URL', () => {
    const invalidPayload = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Stone",
      low_poly_url: "models/element.glb",  // ❌ Relative
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      }
    };
    
    expect(() => ElementSchema.parse(invalidPayload)).toThrow(z.ZodError);
  });

  it('should reject invalid material_type value', () => {
    const invalidMaterialType = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "capitel",  // ❌ Not in enum ["Stone", "Ceramic"]
      low_poly_url: "https://example.com/model.glb",
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      }
    };
    
    expect(() => ElementSchema.parse(invalidMaterialType)).toThrow(z.ZodError);
  });

  it('should reject null low_poly_url', () => {
    const payloadWithNull = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "processing",
      material_type: "Stone",
      low_poly_url: null,  // ❌ Required field cannot be null
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      }
    };
    
    expect(() => ElementSchema.parse(payloadWithNull)).toThrow(z.ZodError);
  });

  it('should reject null bbox', () => {
    const payloadWithNullBBox = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Ceramic",
      low_poly_url: "https://example.com/model.glb",
      bbox: null  // ❌ Required field cannot be null
    };
    
    expect(() => ElementSchema.parse(payloadWithNullBBox)).toThrow(z.ZodError);
  });

  it('should reject BBox with wrong tuple length', () => {
    const invalidBBox = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Stone",
      low_poly_url: "https://example.com/model.glb",
      bbox: {
        min: [-2.5, 0.0],  // ❌ Only 2 elements
        max: [2.5, 5.0, 2.5]
      }
    };
    
    expect(() => ElementSchema.parse(invalidBBox)).toThrow(z.ZodError);
  });
});

describe('ElementDetail Contract', () => {
  it('should accept ISO 8601 timestamps', () => {
    const validPayload = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Stone",
      created_at: "2026-03-05T10:30:00Z",  // ✅ ISO 8601
      low_poly_url: "https://example.com/model.glb",
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      },
      validation_report: null,
      glb_size_bytes: null,
      triangle_count: null
    };
    
    const result = ElementDetailSchema.parse(validPayload);
    expect(result.created_at).toBe("2026-03-05T10:30:00Z");
  });

  it('should reject non-ISO timestamps', () => {
    const invalidPayload = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      iso_code: "SF-C12-D-001",
      status: "validated",
      material_type: "Ceramic",
      created_at: "05/03/2026 10:30",  // ❌ Not ISO 8601
      low_poly_url: "https://example.com/model.glb",
      bbox: {
        min: [-2.5, 0.0, -2.5],
        max: [2.5, 5.0, 2.5]
      },
      validation_report: null,
      glb_size_bytes: null,
      triangle_count: null
    };
    
    expect(() => ElementDetailSchema.parse(invalidPayload)).toThrow(z.ZodError);
  });
});
```

---

## 📐 Type Transformation Rules

### Python → JSON (Serialization)

| Python Type | JSON Type | Example | Notes |
|-------------|-----------|---------|-------|
| `UUID` | `string` | `"550e8400-e29b-..."` | Pydantic auto-converts |
| `datetime` | `string` | `"2026-03-05T10:30:00Z"` | ISO 8601 with timezone |
| `Optional[str]` | `string \| null` | `null` or `"value"` | Never omit field |
| `List[float]` | `array` | `[-2.5, 0.0, 2.5]` | Fixed length enforced |
| `Enum` | `string` | `"validated"` | Lowercase snake_case |
| `HttpUrl` | `string` | `"https://..."` | Always absolute HTTPS |

### JSON → TypeScript (Deserialization)

| JSON Type | TypeScript Type | Zod Validator | Notes |
|-----------|----------------|---------------|-------|
| `string` (UUID) | `string` | `.uuid()` | Runtime UUID format check |
| `string` (ISO 8601) | `string` | `.datetime()` | Validates timezone |
| `null` | `null` | `.nullable()` | Never `undefined` |
| `array` | `[T, T, T]` | `.tuple([...])` | Fixed-length tuples |
| `string` (enum) | `enum` | `.enum([...])` | Type-safe enum |
| `string` (URL) | `string` | `.url()` + refine | HTTPS + absolute |

---

## ⚙️ Implementation Checklist

### Backend (T-1504-BACK)

- [ ] **schemas.py:** Añadir enum `MaterialType` con valores `["Stone", "Ceramic"]`
- [ ] **schemas.py:** Cambiar `Element.material_type` de `str` → `MaterialType` enum
- [ ] **schemas.py:** Cambiar `Element.low_poly_url` de `Optional[HttpUrl]` → `HttpUrl` (required)
- [ ] **schemas.py:** Cambiar `Element.bbox` de `Optional[BoundingBox]` → `BoundingBox` (required)
- [ ] **schemas.py:** Eliminar campos `workshop_id` y `workshop_name` de `Element` y `ElementDetailResponse`
- [ ] **elements_service.py:** Filtrar elementos con `WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL`
- [ ] **elements_service.py:** Generar URLs absolutas con `supabase.storage.get_public_url()`
- [ ] **elements_service.py:** Serializar `datetime` con `.isoformat()`
- [ ] **db/migrations:** Crear migración `DROP COLUMN workshop_id, DROP COLUMN workshop_name`
- [ ] **tests:** Añadir `test_api_contracts.py` con 6 tests mínimo (incluyendo `test_reject_invalid_material_type`)

### Frontend (T-1505-FRONT)

- [ ] **Create:** `src/schemas/elements.schema.ts` con Zod schemas (`ElementSchema`, `ElementDetailSchema`, `MaterialTypeSchema`)
- [ ] **Update:** `src/types/elements.ts` con interfaces TypeScript (`Element`, `ElementDetail`, enum `MaterialType`)
- [ ] **Update:** `upload.service.ts` para usar `ElementsListResponseSchema.parse()`
- [ ] **Update:** `upload.service.ts` para usar `ElementDetailSchema.parse()`
- [ ] **Add:** Error handling para `z.ZodError` con mensajes user-friendly
- [ ] **Refactor:** Renombrar `PartCanvasItem` → `Element` en todos los componentes (Dashboard3D, ModelLoader, etc.)
- [ ] **Remove:** Referencias a `workshop_id` y `workshop_name` en componentes
- [ ] **tests:** Añadir `elements.schema.test.ts` con 12 tests mínimo (incluyendo tests de material_type enum)
- [ ] **CI/CD:** Añadir step `npm run type-check` en GitHub Actions

---

## 🔄 Versioning Strategy

### Contract Version: 1.0.0

**Breaking Changes Policy:**
- Añadir campo requerido → Major bump (2.0.0)
- Cambiar tipo de campo → Major bump
- Remover campo → Major bump
- Hacer campo opcional → Minor bump (1.1.0)
- Añadir campo opcional → Minor bump

**Backward Compatibility:**
- Frontend SIEMPRE valida con Zod (fail fast)
- Backend usa Pydantic strict mode
- Deprecated fields marcados con `@deprecated` en JSDoc
- Migrations aplicadas ANTES de desplegar frontend

**Example Migration (Non-Breaking):**
```python
# Version 1.0.0 → 1.1.0: Add optional field
class Element(BaseModel):
    # ... existing fields
    mid_poly_url: Optional[HttpUrl] = None  # ✅ NEW optional field (minor bump)
```

```typescript
// Frontend compatible con 1.0.0 y 1.1.0
export const ElementSchema = z.object({
  // ... existing fields
  mid_poly_url: z.string().url().nullable().optional(),  // ✅ Graceful degradation
});
```

**Example Migration (Breaking - Removing Fields):**
```sql
-- Version 1.0.0 → 2.0.0: DROP workshop columns
-- This is a BREAKING change (Major version bump)
-- Migration: supabase/migrations/20260305_drop_workshop_columns.sql

BEGIN;

-- Step 1: Drop foreign key constraint first
ALTER TABLE blocks DROP CONSTRAINT IF EXISTS blocks_workshop_id_fkey;

-- Step 2: Drop columns
ALTER TABLE blocks DROP COLUMN IF EXISTS workshop_id;
ALTER TABLE blocks DROP COLUMN IF EXISTS workshop_name;

-- Step 3: Update triggers/functions if they reference these columns
-- (not applicable in current schema)

COMMIT;
```

```python
# Backend: Remove fields from schemas AFTER migration deployed
class Element(BaseModel):
    id: UUID
    iso_code: str
    status: ElementStatus
    tipologia: Tipologia
    low_poly_url: HttpUrl
    bbox: BoundingBox
    # ✅ workshop_id and workshop_name removed
```

---

## 🚨 Common Violations & Fixes

### Violation 1: Relative URL in Database

**Symptom:**
```
TypeError: Failed to construct 'URL': Invalid URL
at useGLTF (ModelLoader.tsx:42)
```

**Root Cause:**
```python
# ❌ WRONG: Backend saves relative path
low_poly_url = f"models/low-poly/{block_id}.glb"
```

**Fix:**
```python
# ✅ CORRECT: Always generate absolute URL
from src.backend.config import settings
supabase = get_supabase_client()
glb_key = f"models/low-poly/{block_id}.glb"
low_poly_url = supabase.storage.from_(BUCKET).get_public_url(glb_key)
# Result: "https://xyz.supabase.co/storage/v1/object/public/models/low-poly/abc.glb"
```

### Violation 2: Missing Required Field (low_poly_url or bbox)

**Symptom:**
```
ZodError: Required at "elements[0].low_poly_url"
TypeError: Cannot read property 'startsWith' of null
```

**Root Cause:**
```python
# ❌ WRONG: Returning elements without geometry
query = "SELECT * FROM blocks WHERE is_archived = FALSE"
# Includes elements with low_poly_url = NULL
```

**Fix:**
```python
# ✅ CORRECT: Filter only processed elements
query = """
    SELECT * FROM blocks 
    WHERE is_archived = FALSE 
      AND low_poly_url IS NOT NULL 
      AND bbox IS NOT NULL
"""
# Only returns elements with complete geometry
```

### Violation 3: Invalid MaterialType Value

**Symptom:**
```
ZodError: Invalid enum value. Expected 'Stone' | 'Ceramic', received 'capitel'
```

**Root Cause:**
```python
# ❌ WRONG: Accepting arbitrary string values
class Element(BaseModel):
    tipologia: str  # No enum enforcement
```

**Fix:**
```python
# ✅ CORRECT: Use enum to enforce valid values
class MaterialType(str, Enum):
    STONE = "Stone"
    CERAMIC = "Ceramic"

class Element(BaseModel):
    material_type: MaterialType  # ✅ Only accepts enum values

    class Config:
        use_enum_values = True  # Serialize as string
```

---

## � Breaking Changes from Original Design

Este contrato refleja un modelo simplificado basado en las siguientes decisiones de diseño:

### ✅ Cambios Aplicados

1. **PartCanvasItem → Element**: Renombrado para simplificar y reflejar mejor el dominio (elementos arquitectónicos, no "parts")

2. **MaterialType como Enum**: Cambio de `string` libre → `enum ["Stone", "Ceramic"]` para garantizar consistencia de datos

3. **Geometría Requerida**: 
   - `low_poly_url`: `Optional[HttpUrl]` → `HttpUrl` (required)
   - `bbox`: `Optional[BoundingBox]` → `BoundingBox` (required)
   - API filtrada: Solo devuelve elementos con geometría procesada completamente

4. **Workshops Eliminados**: Campos `workshop_id` y `workshop_name` removidos del modelo (requiere migración SQL `DROP COLUMN`)

5. **iso_code Source**: Definido explícitamente como extraído de Rhino UserString key `"Codi"` (no generado automáticamente por el sistema)

### 🎯 Impacto en Implementación

**Backend (T-1501-DB):**
- Crear migración SQL para DROP workshops columns
- Añadir enum MaterialType a schemas.py
- Actualizar queries con filtro `WHERE low_poly_url IS NOT NULL AND bbox IS NOT NULL`

**Frontend (T-1505-FRONT):**
- Renombrar interfaces `PartCanvasItem` → `Element` en todos los componentes
- Añadir MaterialTypeSchema a Zod validation
- Eliminar referencias a workshop_id/workshop_name en UI
- Actualizar tests para validar geometría siempre presente

**Agent (T-1503-AGENT):**
- Garantizar que geometry_processing.py siempre genera `low_poly_url` y `bbox` antes de marcar elemento como "validated"
- Extraer y guardar UserString "Codi" como `iso_code` durante procesamiento

---

## �📚 References

- [Pydantic Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [Zod Documentation](https://zod.dev/)
- [OpenAPI 3.1 Spec](https://spec.openapis.org/oas/v3.1.0)
- [ISO 8601 DateTime](https://en.wikipedia.org/wiki/ISO_8601)
- [UUID RFC 4122](https://datatracker.ietf.org/doc/html/rfc4122)

---

**Document Status:** ✅ Ready for Implementation  
**Next Step:** Review with team → Approve → Start T-1501-DB
