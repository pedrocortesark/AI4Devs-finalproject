# Technical Specification: T-1505-FRONT

## 1. Ticket Summary
- **Tipo:** FRONT
- **Epic:** US-015 - Element Model Refactoring
- **Alcance:** Frontend integration of Element API contract with Zod validation, TypeScript type refactoring (Part → Element), component updates (Dashboard3D, ModelLoader, PartDetailModal), MATERIAL_COLORS integration (62 materials), Three.js mock fixes, canvas positioning with bbox.center, material color rendering
- **Dependencias:** 
  - ✅ T-1504-BACK (Element API endpoints implemented, 10/11 unit tests PASSED, 13/25 integration tests PASSED)
  - ✅ T-1504-AGENT (MATERIAL_COLORS dictionary with 62 materials in src/agent/constants.py)
  - ✅ T-1502-INFRA (generate_glb_storage_path function)
  - ✅ T-1501-DB (material_type column migrated, workshop columns removed)

---

## 2. Data Structures & Contracts

### Backend Schemas (Already Implemented via T-1504-BACK)

**NOTA:** Estas schemas YA ESTÁN IMPLEMENTADAS en `src/backend/schemas.py`. NO las modifiques. Este ticket solo debe alinear el frontend con estos contratos.

```python
# src/backend/schemas.py (REFERENCE ONLY - DO NOT MODIFY)

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from uuid import UUID

class ElementStatus(str, Enum):
    """Lifecycle states for elements"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ERROR_PROCESSING = "error_processing"
    IN_FABRICATION = "in_fabrication"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class BoundingBox(BaseModel):
    """3D bounding box for spatial layout"""
    min: List[float] = Field(..., min_length=3, max_length=3)
    max: List[float] = Field(..., min_length=3, max_length=3)

class Element(BaseModel):
    """
    Element schema for 3D canvas rendering.
    Breaking changes from PartCanvasItem:
    - Removed: workshop_id, workshop_name
    - Renamed: tipologia → material_type
    - Changed: material_type from enum to str (validated against 62 real materials)
    """
    id: UUID
    iso_code: str
    status: ElementStatus
    material_type: str  # Validated against 62 MATERIAL_COLORS materials
    low_poly_url: Optional[str]  # Nullable (async processing)
    bbox: Optional[BoundingBox]  # Nullable (async processing)

class ElementsListResponse(BaseModel):
    """Response for GET /api/elements"""
    elements: List[Element]
    filters_applied: dict
    meta: dict  # { total: int, filtered: int }

class ElementDetail(BaseModel):
    """Detailed element info for 3D viewer modal"""
    id: UUID
    iso_code: str
    status: ElementStatus
    material_type: str
    created_at: str  # ISO 8601
    low_poly_url: Optional[str]
    bbox: Optional[BoundingBox]
    validation_report: Optional[ValidationReport]
    glb_size_bytes: Optional[int]
    triangle_count: Optional[int]

class ElementNavigationResponse(BaseModel):
    """Response for GET /api/elements/{id}/navigation"""
    prev_id: Optional[UUID]
    next_id: Optional[UUID]
    current_index: int  # 1-based
    total_count: int
```

### Frontend Types (TO IMPLEMENT)

#### A) Core Element Types (`src/frontend/src/types/elements.ts`)

```typescript
/**
 * T-1505-FRONT: Element Model Types
 * 
 * CRITICAL CONTRACT RULES:
 * 1. Must match backend Pydantic schemas EXACTLY (field names, types, nullability)
 * 2. Python UUID → TypeScript string
 * 3. Python Optional[X] → TypeScript X | null
 * 4. Python List[float] → TypeScript number[]
 * 5. Python Enum → TypeScript enum (same string values)
 * 
 * BREAKING CHANGES from parts.ts:
 * - Removed: workshop_id, workshop_name
 * - Renamed: PartCanvasItem → Element, PartsListResponse → ElementsListResponse
 * - Renamed: tipologia → material_type (now validated string against 62 materials)
 * 
 * @see src/backend/schemas.py - Element, ElementDetail, ElementsListResponse
 * @see src/agent/constants.py - MATERIAL_COLORS (62 materials with RGB tuples)
 */

import type { ValidationReport } from './validation';
import type { MATERIAL_COLORS } from '../constants/materials';

// ===== Element Status =====

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

// ===== Material Type =====

/**
 * Material type - union type derived from MATERIAL_COLORS dictionary
 * 62 real stone types from Sagrada Família (Montjuïc, Ulldecona, Floresta, etc.)
 */
export type MaterialType = keyof typeof MATERIAL_COLORS;

// ===== Bounding Box =====

export interface BoundingBox {
  min: [number, number, number];  // [x, y, z] - exactly 3 elements
  max: [number, number, number];  // [x, y, z] - exactly 3 elements
}

/**
 * Helper to compute bbox center (for canvas positioning in T-1505)
 */
export function computeBBoxCenter(bbox: BoundingBox): [number, number, number] {
  return [
    (bbox.min[0] + bbox.max[0]) / 2,
    (bbox.min[1] + bbox.max[1]) / 2,
    (bbox.min[2] + bbox.max[2]) / 2,
  ];
}

// ===== Element (Canvas Item) =====

/**
 * Minimal element info optimized for 3D canvas rendering
 * Used by GET /api/elements endpoint
 */
export interface Element {
  id: string;                      // UUID string
  iso_code: string;                // ISO-19650 identifier (e.g., GLPER.B-PAE0720.0701)
  status: ElementStatus;           // Lifecycle state
  material_type: MaterialType;     // One of 62 real materials (validated string)
  low_poly_url: string | null;     // Presigned CDN URL to GLB, or null if not processed yet
  bbox: BoundingBox | null;        // 3D bounding box, or null if not extracted yet
}

/**
 * Response from GET /api/elements
 */
export interface ElementsListResponse {
  elements: Element[];
  filters_applied: Record<string, string | null>;
  meta: {
    total: number;
    filtered: number;
  };
}

/**
 * Query parameters for GET /api/elements (all optional)
 */
export interface ElementsQueryParams {
  status?: ElementStatus;
  material_type?: MaterialType;
}

// ===== Element Detail (Modal) =====

/**
 * Detailed element info for 3D viewer modal
 * Used by GET /api/elements/{id} endpoint
 */
export interface ElementDetail {
  /** Element UUID */
  id: string;
  
  /** ISO-19650 identifier */
  iso_code: string;
  
  /** Lifecycle state */
  status: ElementStatus;
  
  /** Material type (one of 62 real materials) */
  material_type: MaterialType;
  
  /** Creation timestamp (ISO 8601 datetime) */
  created_at: string;
  
  /** Presigned CDN URL for GLB file (TTL 5min), null if not generated yet */
  low_poly_url: string | null;
  
  /** 3D bounding box for camera positioning */
  bbox: BoundingBox | null;
  
  /** Validation results from The Librarian agent */
  validation_report: ValidationReport | null;
  
  /** GLB file size in bytes */
  glb_size_bytes: number | null;
  
  /** Triangle count (for performance monitoring) */
  triangle_count: number | null;
}

// ===== Element Navigation =====

/**
 * Response from GET /api/elements/{id}/navigation
 * Used for Prev/Next buttons in modal
 */
export interface ElementNavigationResponse {
  prev_id: string | null;
  next_id: string | null;
  current_index: number;  // 1-based position
  total_count: number;
}
```

#### B) Material Colors Constants (`src/frontend/src/constants/materials.ts`)

```typescript
/**
 * T-1505-FRONT: Material Colors Dictionary
 * 
 * Synchronized with backend src/agent/constants.py MATERIAL_COLORS
 * 62 real stone types from Sagrada Família with RGB color tuples
 * 
 * Usage:
 * - Frontend canvas rendering: Apply material color to Three.js mesh
 * - Validation: TypeScript MaterialType = keyof typeof MATERIAL_COLORS
 * 
 * @see src/agent/constants.py - MATERIAL_COLORS (source of truth)
 */

export const MATERIAL_COLORS = {
  // Warm tones (ochres, creams, beiges)
  "Montjuïc": [230, 180, 100] as const,               // Warm ochre (DEFAULT)
  "Ulldecona": [240, 220, 180] as const,              // Light cream
  "Floresta": [225, 200, 130] as const,               // Golden sand
  "Beix Anglès": [210, 195, 170] as const,            // Beige
  "Beix mallorca": [215, 190, 150] as const,          // Golden beige
  "Crema marfil": [235, 225, 200] as const,           // Ivory cream
  "Itaunas": [225, 210, 160] as const,                // Yellow beige
  "Jodhpur beix": [220, 200, 170] as const,           // Sand beige
  "Pedra de vilafranca": [230, 210, 170] as const,    // Light yellow
  "Pedra de figueres": [230, 215, 185] as const,      // Light beige
  "Pedra de calafell": [225, 215, 190] as const,      // Light cream
  "Udelfangen": [230, 220, 200] as const,             // Fine light beige
  "Stanton Moor": [220, 190, 170] as const,           // Light reddish beige
  
  // Browns and reds
  "Granit moreno ingemarga": [145, 95, 60] as const,  // Brown
  "Granit boveda moreno": [110, 80, 60] as const,     // Dark brown
  "Granit moreno torible": [130, 90, 70] as const,    // Dark reddish brown
  "Granit Torrat": [150, 110, 80] as const,           // Toasted brown
  "Roig st. jaume": [160, 70, 70] as const,           // Dark red
  "Rosso levanto": [170, 100, 90] as const,           // Veined red
  "Calcària griotte": [150, 70, 70] as const,         // Red black
  "Sorrenca de st. vicenç (rocafort)": [200, 150, 130] as const,  // Sandy red
  "Zarcilla": [170, 130, 110] as const,               // Reddish brown
  "Pulpis": [180, 160, 140] as const,                 // Light brown
  "Pedra de mistretta": [190, 160, 120] as const,     // Golden brown
  
  // Grays (light to dark)
  "Pedra del garraf": [220, 220, 220] as const,       // White gray
  "Blanc cardenal": [230, 230, 235] as const,         // Light grayish white
  "Calcària de st. vicens": [210, 210, 215] as const, // Grayish white
  "Granit gris quintana": [170, 170, 170] as const,   // Light gray
  "Granit de vilachà": [160, 160, 170] as const,      // Granite gray
  "Montserrat": [170, 160, 170] as const,             // Pinkish gray
  "Granit zamora": [180, 165, 175] as const,          // Pink gray
  "Pedra de les masies de roda": [205, 190, 195] as const,  // Light pinkish gray
  "Postaer Alte Poste": [210, 205, 190] as const,     // Cream gray
  "Leïstadter": [200, 200, 170] as const,             // Yellowish gray
  "Granit gudiña": [90, 90, 95] as const,             // Dark gray
  "Granit merufe": [100, 100, 110] as const,          // Veined dark gray
  "Granit del tarn": [180, 180, 190] as const,        // Silvery gray
  
  // Greenish grays
  "Cantàbria": [120, 150, 140] as const,              // Greenish gray
  "Escòcia": [140, 160, 150] as const,                // Greenish gray
  "Llisós": [180, 190, 180] as const,                 // Light greenish gray
  "Granit orrius o ull de serp": [130, 150, 130] as const,  // Green gray
  
  // Bluish tones
  "Blavozy": [160, 170, 190] as const,                // Bluish gray
  "Pedra del figueró": [140, 150, 175] as const,      // Blue gray
  "Granit blau bahia": [60, 80, 130] as const,        // Dark blue
  "Granit de fraguas": [100, 110, 130] as const,      // Dark bluish gray
  "Ocean Black": [50, 60, 70] as const,               // Bluish black
  
  // Blacks and dark tones
  "Basalt de castellfollit": [70, 70, 75] as const,   // Grayish black
  "Basalt italià": [50, 50, 55] as const,             // Intense black
  "Granit negre zimbawe": [40, 40, 45] as const,      // Graphite black
  "Volcanica": [80, 80, 90] as const,                 // Textured dark gray
  
  // Whites and very light tones
  "Blanc macael": [250, 250, 250] as const,           // Pure white
  "Granit blanco cristal": [240, 240, 240] as const,  // Crystal white
  "Alabastre": [245, 240, 235] as const,              // Translucent white
  "Pedra de colmenar": [235, 230, 215] as const,      // Cream white
  "Marbre de tassos": [240, 235, 230] as const,       // Veined white
  "Marbre de carrara": [245, 245, 245] as const,      // Carrara white
  "Himàlaia": [240, 235, 225] as const,               // Veined crystal white
  
  // Pinks
  "Jodhpur Pink": [230, 200, 200] as const,           // Light pink
  
  // Special tones
  "Pòrfir": [150, 100, 150] as const,                 // Purple
  "Ònix": [180, 220, 200] as const,                   // Translucent green
  
  // Travertines
  "Travertí romà": [220, 200, 170] as const,          // Travertine beige
  "Travertí de terol": [210, 180, 150] as const,      // Reddish beige
  "Travertí de granada": [200, 170, 140] as const,    // Dark beige
} as const;

/**
 * Default material when not specified
 */
export const DEFAULT_MATERIAL = "Montjuïc" as const;

/**
 * Helper: Get RGB color array for a material (normalized 0-1 for Three.js)
 */
export function getMaterialColor(material: keyof typeof MATERIAL_COLORS): [number, number, number] {
  const rgb = MATERIAL_COLORS[material] || MATERIAL_COLORS[DEFAULT_MATERIAL];
  return [rgb[0] / 255, rgb[1] / 255, rgb[2] / 255];
}

/**
 * Helper: Get RGB color as hex string for CSS
 */
export function getMaterialColorHex(material: keyof typeof MATERIAL_COLORS): string {
  const rgb = MATERIAL_COLORS[material] || MATERIAL_COLORS[DEFAULT_MATERIAL];
  return `#${rgb.map(c => c.toString(16).padStart(2, '0')).join('')}`;
}
```

#### C) Zod Validation Schema (`src/schemas/elements.schema.ts` - NEW FILE)

```typescript
/**
 * T-1505-FRONT: Zod Validation Schemas for Element API
 * 
 * Purpose: Runtime validation of API responses (fail-fast on contract mismatch)
 * Pattern: Zod schemas mirror Pydantic schemas EXACTLY
 * 
 * Usage:
 * - Service layer: Parse API responses with schema.parse()
 * - Type inference: z.infer<typeof ElementSchema> → Element type
 * - Error handling: ZodError → user-friendly validation errors
 */

import { z } from 'zod';
import { MATERIAL_COLORS } from '../constants/materials';

// ===== Enums =====

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

// Material type: must be one of 62 valid materials from MATERIAL_COLORS
export const MaterialTypeSchema = z.enum(
  Object.keys(MATERIAL_COLORS) as [string, ...string[]]
);

// ===== Bounding Box =====

export const BoundingBoxSchema = z.object({
  min: z.tuple([z.number(), z.number(), z.number()]),  // Exactly 3 numbers
  max: z.tuple([z.number(), z.number(), z.number()]),  // Exactly 3 numbers
});

// ===== Element (Canvas Item) =====

export const ElementSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string().min(1),
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,
  low_poly_url: z.string().url().nullable(),
  bbox: BoundingBoxSchema.nullable(),
});

// ===== Elements List Response =====

export const ElementsListResponseSchema = z.object({
  elements: z.array(ElementSchema),
  filters_applied: z.record(z.string(), z.union([z.string(), z.null()])),
  meta: z.object({
    total: z.number().int().nonnegative(),
    filtered: z.number().int().nonnegative(),
  }),
});

// ===== Element Detail =====

export const ValidationReportSchema = z.object({
  is_valid: z.boolean(),
  errors: z.array(z.object({
    category: z.string(),
    target: z.string().optional(),
    message: z.string(),
  })),
  metadata: z.record(z.string(), z.any()),
  validated_at: z.string().datetime().nullable(),
  validated_by: z.string().nullable(),
});

export const ElementDetailSchema = z.object({
  id: z.string().uuid(),
  iso_code: z.string().min(1),
  status: ElementStatusSchema,
  material_type: MaterialTypeSchema,
  created_at: z.string().datetime(),
  low_poly_url: z.string().url().nullable(),
  bbox: BoundingBoxSchema.nullable(),
  validation_report: ValidationReportSchema.nullable(),
  glb_size_bytes: z.number().int().positive().nullable(),
  triangle_count: z.number().int().positive().nullable(),
});

// ===== Element Navigation =====

export const ElementNavigationResponseSchema = z.object({
  prev_id: z.string().uuid().nullable(),
  next_id: z.string().uuid().nullable(),
  current_index: z.number().int().min(1),
  total_count: z.number().int().nonnegative(),
});

// ===== Type Inference =====

export type Element = z.infer<typeof ElementSchema>;
export type ElementsListResponse = z.infer<typeof ElementsListResponseSchema>;
export type ElementDetail = z.infer<typeof ElementDetailSchema>;
export type ElementNavigationResponse = z.infer<typeof ElementNavigationResponseSchema>;
```

---

## 3. API Service Layer Updates

### elements.service.ts (NEW FILE)

```typescript
/**
 * T-1505-FRONT: Element API Service
 * 
 * Purpose: Service layer for Element API endpoints with Zod validation
 * Pattern: 
 * - All API calls isolated here (not in components)
 * - Zod schema validation on responses (fail-fast on contract mismatch)
 * - Error handling with typed exceptions
 * 
 * Endpoints:
 * - GET /api/elements → fetch all elements matching filters
 * - GET /api/elements/{id} → fetch element detail
 * - GET /api/elements/{id}/navigation → fetch prev/next IDs
 */

import { 
  ElementsListResponseSchema, 
  ElementDetailSchema, 
  ElementNavigationResponseSchema,
  type ElementsListResponse,
  type ElementDetail,
  type ElementNavigationResponse,
  type ElementsQueryParams,
} from '../schemas/elements.schema';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Error thrown when Element API call fails
 */
export class ElementApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: unknown
  ) {
    super(message);
    this.name = 'ElementApiError';
  }
}

/**
 * Fetch elements list with optional filters
 * 
 * @param params - Query parameters (status, material_type)
 * @returns Validated ElementsListResponse
 * @throws ElementApiError if request fails or validation fails
 */
export async function fetchElements(
  params?: ElementsQueryParams
): Promise<ElementsListResponse> {
  try {
    const queryString = params 
      ? '?' + new URLSearchParams(params as Record<string, string>).toString()
      : '';
    
    const response = await fetch(`${API_BASE_URL}/api/elements${queryString}`);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new ElementApiError(
        `Failed to fetch elements: ${errorText}`,
        response.status
      );
    }
    
    const data = await response.json();
    
    // Zod validation (throws ZodError if mismatch)
    return ElementsListResponseSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      'Failed to fetch elements',
      undefined,
      error
    );
  }
}

/**
 * Fetch element detail by ID
 * 
 * @param id - Element UUID
 * @returns Validated ElementDetail
 * @throws ElementApiError if element not found or validation fails
 */
export async function fetchElementDetail(id: string): Promise<ElementDetail> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/elements/${id}`);
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new ElementApiError('Element not found', 404);
      }
      const errorText = await response.text();
      throw new ElementApiError(
        `Failed to fetch element detail: ${errorText}`,
        response.status
      );
    }
    
    const data = await response.json();
    
    // Zod validation
    return ElementDetailSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      'Failed to fetch element detail',
      undefined,
      error
    );
  }
}

/**
 * Fetch element navigation (prev/next IDs)
 * 
 * @param id - Current element UUID
 * @returns Validated ElementNavigationResponse
 * @throws ElementApiError if request fails or validation fails
 */
export async function fetchElementNavigation(
  id: string
): Promise<ElementNavigationResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/elements/${id}/navigation`);
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new ElementApiError(
        `Failed to fetch element navigation: ${errorText}`,
        response.status
      );
    }
    
    const data = await response.json();
    
    // Zod validation
    return ElementNavigationResponseSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      'Failed to fetch element navigation',
      undefined,
      error
    );
  }
}
```

---

## 4. Component Updates

### 4.1 Dashboard3D Integration

**Component:** `src/frontend/src/components/Dashboard/Dashboard3D.tsx`

**Changes:**
- Replace `usePartsStore` → `useElementsStore` (NEW store)
- Update imports: `import type { Element } from '@/types/elements'`
- Update props/state types: `Element` instead of `PartCanvasItem`

**Current Code Location:**
Line 13: `import { usePartsStore } from '@/stores/parts.store';`

**Refactor:**
```typescript
// OLD
import { usePartsStore } from '@/stores/parts.store';
const { parts, isLoading, error, selectedId, clearSelection } = usePartsStore();

// NEW
import { useElementsStore } from '@/stores/elements.store';
const { elements, isLoading, error, selectedId, clearSelection } = useElementsStore();
```

### 4.2 ModelLoader Component

**Component:** `src/frontend/src/components/Dashboard/ModelLoader.tsx`

**Critical Change 1: Canvas Positioning**
Current implementation likely positions at origin `[0, 0, 0]`. Fix by computing center from `bbox`:

```typescript
// src/frontend/src/components/Dashboard/ModelLoader.tsx

import { computeBBoxCenter } from '@/types/elements';

function ModelLoader({ elementId }: { elementId: string }) {
  const { data: element } = useQuery({
    queryKey: ['element', elementId],
    queryFn: () => fetchElementDetail(elementId),
  });

  // Compute position from bbox.center (not hardcoded [0,0,0])
  const position = element?.bbox 
    ? computeBBoxCenter(element.bbox)
    : [0, 0, 0];

  // Apply material color
  const materialColor = element?.material_type
    ? getMaterialColor(element.material_type)
    : getMaterialColor('Montjuïc');

  return (
    <mesh position={position}>
      <primitive object={glbModel.scene} />
      <meshStandardMaterial color={materialColor} />
    </mesh>
  );
}
```

**Critical Change 2: Material Coloring**
Apply RGB color from MATERIAL_COLORS to Three.js mesh material:

```typescript
import { getMaterialColor } from '@/constants/materials';

// Inside component render
<meshStandardMaterial 
  color={new THREE.Color(...getMaterialColor(element.material_type))}
/>
```

### 4.3 PartDetailModal Component

**Component:** `src/frontend/src/components/Dashboard/PartDetailModal.tsx`

**Changes:**
- Update type imports: `ElementDetail` instead of `PartDetail`
- Remove UI references to `workshop_id`, `workshop_name`
- Update label: "Tipología" → "Material Type"
- Display material with color chip using MATERIAL_COLORS

**Before:**
```tsx
<div>
  <label>Tipología:</label>
  <span>{part.tipologia}</span>
</div>
<div>
  <label>Workshop:</label>
  <span>{part.workshop_name || 'Unassigned'}</span>
</div>
```

**After:**
```tsx
<div>
  <label>Material Type:</label>
  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    <div 
      style={{
        width: 20,
        height: 20,
        backgroundColor: getMaterialColorHex(element.material_type),
        border: '1px solid #ccc',
        borderRadius: 4,
      }}
    />
    <span>{element.material_type}</span>
  </div>
</div>
```

### 4.4 PartMetadataPanel Component

**Component:** `src/frontend/src/components/Dashboard/PartMetadataPanel.tsx`

**Changes:**
- Update types: `ElementDetail` instead of `PartDetail`
- Remove "Workshop" section entirely
- Update "Info" section: "Material Type" display with color chip
- Update "Geometry" section: No changes (bbox, glb_size_bytes stay)

### 4.5 Zustand Store Refactoring

**NEW FILE:** `src/frontend/src/stores/elements.store.ts`

```typescript
/**
 * T-1505-FRONT: Elements Store (replaces parts.store.ts)
 * 
 * Breaking changes:
 * - Renamed: parts → elements
 * - Uses Element type (not PartCanvasItem)
 * - Uses fetchElements service (not fetchParts)
 * - Filters updated: tipologia → material_type
 */

import { create } from 'zustand';
import { fetchElements } from '@/services/elements.service';
import type { Element, ElementStatus, MaterialType } from '@/types/elements';

interface ElementsFilters {
  status?: ElementStatus;
  material_type?: MaterialType;
}

interface ElementsStore {
  elements: Element[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  filters: ElementsFilters;
  
  // Actions
  loadElements: () => Promise<void>;
  selectElement: (id: string) => void;
  clearSelection: () => void;
  setFilters: (filters: ElementsFilters) => void;
}

export const useElementsStore = create<ElementsStore>((set, get) => ({
  elements: [],
  isLoading: false,
  error: null,
  selectedId: null,
  filters: {},

  loadElements: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetchElements(get().filters);
      set({ elements: response.elements, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to load elements',
        isLoading: false 
      });
    }
  },

  selectElement: (id: string) => set({ selectedId: id }),
  clearSelection: () => set({ selectedId: null }),
  setFilters: (filters: ElementsFilters) => {
    set({ filters });
    get().loadElements();
  },
}));
```

---

## 5. Test Cases Checklist

### **Happy Path (11 tests)**

#### Zod Validation
- [ ] HP-ZOD-01: ElementSchema validates valid Element object from API
- [ ] HP-ZOD-02: ElementsListResponseSchema validates full list response with meta
- [ ] HP-ZOD-03: ElementDetailSchema validates detail response with all fields
- [ ] HP-ZOD-04: MaterialTypeSchema validates "Montjuïc" (default material)
- [ ] HP-ZOD-05: MaterialTypeSchema validates all 62 materials from MATERIAL_COLORS

#### Service Layer
- [ ] HP-SVC-01: fetchElements() returns validated ElementsListResponse
- [ ] HP-SVC-02: fetchElementDetail(id) returns validated ElementDetail with bbox
- [ ] HP-SVC-03: fetchElementNavigation(id) returns prev/next IDs correctly

#### Component Integration
- [ ] HP-CMP-01: Dashboard3D renders elements grid with material colors
- [ ] HP-CMP-02: ModelLoader positions mesh at bbox.center (not origin)
- [ ] HP-CMP-03: PartDetailModal displays material type with color chip

---

### **Edge Cases (10 tests)**

#### Type Safety
- [ ] EC-TYPE-01: TypeScript compiler rejects workshop_id access on Element type
- [ ] EC-TYPE-02: TypeScript compiler rejects tipologia access on Element type
- [ ] EC-TYPE-03: MaterialType union enforces only 62 valid materials

#### Nullable Fields
- [ ] EC-NULL-01: Element with low_poly_url=null renders BBoxProxy fallback
- [ ] EC-NULL-02: Element with bbox=null shows "Geometry not processed" message
- [ ] EC-NULL-03: ElementDetail with validation_report=null shows "Not validated yet"

#### Material Colors
- [ ] EC-COLOR-01: getMaterialColor("Montjuïc") returns [230/255, 180/255, 100/255]
- [ ] EC-COLOR-02: getMaterialColorHex("Montjuïc") returns "#e6b464"
- [ ] EC-COLOR-03: Fallback to DEFAULT_MATERIAL when material not in dict (defensive)
- [ ] EC-COLOR-04: All 62 materials render with distinct colors in canvas

---

### **Error Handling (10 tests)**

#### Zod Validation Errors
- [ ] ERR-ZOD-01: ElementSchema.parse() throws ZodError if material_type=null
- [ ] ERR-ZOD-02: ElementSchema.parse() throws ZodError if material_type="InvalidMaterial"
- [ ] ERR-ZOD-03: BoundingBoxSchema.parse() throws ZodError if min has 2 elements (not 3)
- [ ] ERR-ZOD-04: ElementStatusSchema.parse() throws ZodError if status="unknown"

#### Service Layer Errors
- [ ] ERR-SVC-01: fetchElements() throws ElementApiError on 500 response
- [ ] ERR-SVC-02: fetchElementDetail('invalid-uuid') throws ElementApiError 404
- [ ] ERR-SVC-03: fetchElementNavigation(id) handles network timeout gracefully

#### Component Errors
- [ ] ERR-CMP-01: Dashboard3D shows error banner when fetchElements() fails
- [ ] ERR-CMP-02: ModelLoader shows ErrorFallback when GLB fetch fails
- [ ] ERR-CMP-03: PartDetailModal shows error message when fetchElementDetail() fails

---

### **Integration Tests (6 tests)**

#### E2E Element Flow
- [ ] INT-E2E-01: Upload .3dm → Processing → Validated → Element appears in canvas with correct material color
- [ ] INT-E2E-02: Click element in canvas → Modal opens with ElementDetail → Material type displayed with color chip
- [ ] INT-E2E-03: Navigate with Prev/Next buttons → URL updates → Modal fetches new ElementDetail

#### Three.js Mocks
- [ ] INT-MOCK-01: ModelLoader.test.tsx mocks return valid Three.Object3D (fix existing test failures)
- [ ] INT-MOCK-02: Canvas3D.test.tsx renders without WebGL errors (vi.mock R3F)
- [ ] INT-MOCK-03: PartMesh.test.tsx applies material color correctly to mesh

---

## 6. Files to Create/Modify

### **Create (6 files)**

1. **`src/frontend/src/types/elements.ts`** (350 lines)
   - Element, ElementDetail, ElementsListResponse, ElementNavigationResponse types
   - MaterialType union type (62 materials)
   - computeBBoxCenter() helper

2. **`src/frontend/src/constants/materials.ts`** (150 lines)
   - MATERIAL_COLORS dictionary (62 materials with RGB tuples)
   - getMaterialColor() helper (returns 0-1 normalized RGB)
   - getMaterialColorHex() helper (returns CSS hex string)

3. **`src/frontend/src/schemas/elements.schema.ts`** (200 lines)
   - Zod schemas: ElementSchema, ElementsListResponseSchema, ElementDetailSchema
   - MaterialTypeSchema (z.enum with 62 materials)
   - Type inference exports

4. **`src/frontend/src/services/elements.service.ts`** (150 lines)
   - fetchElements(), fetchElementDetail(), fetchElementNavigation()
   - ElementApiError class
   - Zod validation integration

5. **`src/frontend/src/stores/elements.store.ts`** (100 lines)
   - ElementsStore with loadElements(), selectElement(), setFilters()
   - Replaces parts.store.ts

6. **`tests/frontend/unit/elements.schema.test.ts`** (300 lines)
   - 37 test cases (HP, EC, ERR, INT)

---

### **Modify (10 files)**

1. **`src/frontend/src/components/Dashboard/Dashboard3D.tsx`** (+20 lines)
   - Replace `usePartsStore` → `useElementsStore`
   - Update types: `Element` instead of `PartCanvasItem`

2. **`src/frontend/src/components/Dashboard/Canvas3D.tsx`** (+15 lines)
   - Update prop types: `Element[]` instead of `PartCanvasItem[]`

3. **`src/frontend/src/components/Dashboard/PartMesh.tsx`** (+30 lines)
   - Import getMaterialColor()
   - Apply material color to `<meshStandardMaterial color={...} />`

4. **`src/frontend/src/components/Dashboard/ModelLoader.tsx`** (+40 lines)
   - Import computeBBoxCenter()
   - Position mesh at bbox.center (not hardcoded [0,0,0])
   - Apply material color to mesh

5. **`src/frontend/src/components/Dashboard/PartDetailModal.tsx`** (+50 lines, -30 lines)
   - Update types: `ElementDetail` instead of `PartDetail`
   - Remove workshop section
   - Add material color chip to Material Type display

6. **`src/frontend/src/components/Dashboard/PartMetadataPanel.tsx`** (+20 lines, -25 lines)
   - Update types: `ElementDetail`
   - Remove Workshop section
   - Update "Info" section with material color chip

7. **`src/frontend/src/components/Dashboard/FiltersSidebar.tsx`** (+25 lines)
   - Replace "Tipología" filter → "Material Type" filter
   - Use MaterialType union (62 options in dropdown)

8. **`src/frontend/src/components/Dashboard/ModelLoader.test.tsx`** (+80 lines)
   - Fix Three.js mocks to return valid Object3D
   - Add test for bbox.center positioning
   - Add test for material color application

9. **`src/frontend/vitest.config.ts`** (no changes needed, but verify zod is installed)
   - Check `package.json` has `"zod": "^3.22.0"`

10. **`README.md` in `docs/US-015/`** (+100 lines)
    - Document Element model migration
    - Breaking changes list
    - Migration guide for future developers

---

## 7. Reusable Components/Patterns

### From US-010 (3D Viewer)
- **PartViewerCanvas** → Can be reused with Element type (no changes needed)
- **ViewerErrorBoundary** → Generic error boundary (works with Element)
- **BBoxProxy** → Already uses BoundingBox type (compatible)

### From US-005 (Dashboard 3D)
- **EmptyState** → Generic component (no type coupling)
- **LoadingOverlay** → Generic component (no type coupling)
- **CameraController** → Generic Three.js component (no type coupling)

### New Pattern: Material Color Rendering
- **getMaterialColor()** in `materials.ts` → Reusable for all 3D rendering contexts
- Pattern can extend to:
  - Legend/color picker for filters
  - Material statistics panel
  - Export to PDF with color-coded elements

---

## 8. Migration Strategy (Deprecation Plan)

### Phase 1: Dual API Support (T-1505-FRONT - Current Ticket)
- ✅ Backend: `/api/elements` endpoints implemented (T-1504-BACK)
- ✅ Frontend: Create NEW `elements.store.ts` (do NOT modify `parts.store.ts` yet)
- Component updates: Use `useElementsStore` in Dashboard3D (isolated change)
- Old route `/api/parts` still works (backend compatibility)

### Phase 2: Deprecation Warnings (Post-T-1505)
- Add console.warn() to `parts.store.ts`: *"DEPRECATED: Use useElementsStore instead"*
- Add UI banner in Dashboard3D if using old store
- Update all docs to reference Element model

### Phase 3: Remove Parts API (Future US)
- Delete `src/frontend/src/stores/parts.store.ts`
- Delete `src/backend/api/parts.py`
- Remove `PartCanvasItem`, `PartsListResponse` from schemas
- Database migration: Add deprecation notice to `blocks` table comments

---

## 9. Performance Considerations

### Material Colors Performance
- **62 materials × 6 elements = 372 color lookups per frame (NEGLIGIBLE)**
- Optimization: Memoize getMaterialColor() results with useMemo()
- Benchmark target: <1ms for all color computations per render

### Zod Validation Overhead
- **Risk:** Parsing 500 elements × ElementSchema = ~50ms overhead
- **Mitigation:** Validate only once in service layer, not in components
- **Alternative:** Use Zod `safeParse()` for graceful degradation (log errors, render anyway)

### Three.js Material Updates
- **Current:** One MeshStandardMaterial per element (6 materials × 378 bytes = 2.2KB)
- **Optimization (Future):** Material pooling by color (reduce to ~20 unique materials)

---

## 10. Acceptance Criteria Mapping

From `docs/09-mvp-backlog.md` T-1505-FRONT DoD:

✅ **"Element schemas integrated"**
→ Zod schemas created in `elements.schema.ts` (HP-ZOD-01 to HP-ZOD-05)

✅ **"60-80 frontend tests updated"**
→ 37 new tests defined (11 HP + 10 EC + 10 ERR + 6 INT)
→ Plus ~30 existing tests updated (ModelLoader, Dashboard3D, PartDetailModal)

✅ **"ModelLoader mocks fixed (3 exceptions resolved)"**
→ INT-MOCK-01: Fix Three.Object3D mock return value
→ INT-MOCK-02: Fix Canvas3D WebGL mock
→ INT-MOCK-03: Fix PartMesh material mock

✅ **"Canvas positioning + material coloring working"**
→ HP-CMP-02: ModelLoader positions at bbox.center
→ HP-CMP-03: Material color applied to mesh
→ EC-COLOR-04: All 62 materials render distinct colors

✅ **"Frontend target 365+/407 (90%+)"**
→ Current baseline: 407 tests
→ After T-1505: 407 - 30 (deprecated parts tests) + 67 (new element tests) = **444 tests**
→ Target: 444 × 0.90 = 400 PASS (**achievable**)

---

## 11. Next Steps — Handoff for TDD-RED Phase

```
=============================================
READY FOR TDD-RED PHASE
=============================================
Ticket ID:       T-1505-FRONT
Feature name:    Element Model Frontend Integration
Sprint:          Sprint 6 (US-015)
Story Points:    3 SP
Estimated time:  6-8 hours (RED 2h, GREEN 3h, REFACTOR 2h, AUDIT 1h)

KEY TEST CASES (Priority Order):
1. HP-ZOD-01: ElementSchema validates API response
2. HP-SVC-01: fetchElements() returns validated elements
3. HP-CMP-02: ModelLoader positions at bbox.center
4. ERR-ZOD-02: MaterialTypeSchema rejects invalid material
5. INT-MOCK-01: Fix Three.Object3D mock (BLOCKER)

FILES TO CREATE (TDD-RED Phase):
  - tests/frontend/unit/elements.schema.test.ts (300 lines, 37 tests)
  - src/schemas/elements.schema.ts (STUB all exports, return mock data)
  - src/types/elements.ts (STUB all types, minimal implementation)
  - src/constants/materials.ts (STUB MATERIAL_COLORS with 3 materials)
  - src/services/elements.service.ts (STUB fetch functions, throw NotImplementedError)
  - src/stores/elements.store.ts (STUB store actions)

FILES TO MODIFY (TDD-RED Phase):
  - src/components/Dashboard/ModelLoader.test.tsx (ADD 3 failing tests)
  - src/components/Dashboard/Dashboard3D.test.tsx (ADD 2 failing tests)
  - src/components/Dashboard/PartDetailModal.test.tsx (ADD 2 failing tests)

EXPECTED TDD-RED RESULT:
  - 37 NEW tests FAILING ✅ (correct behavior)
  - 407 EXISTING tests PASSING ✅ (zero regression)
  - Total: 37 FAILED / 444 TOTAL

BLOCKERS TO RESOLVE FIRST:
  - Install zod: npm install zod (if not present)
  - Verify MATERIAL_COLORS in backend (src/agent/constants.py exists)
  - Confirm T-1504-BACK Element API is deployed/accessible

READY TO PROCEED? (yes/no):
=============================================
```

---

## 12. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Three.js mock fixes break existing tests** | HIGH (407 tests at risk) | MEDIUM | Run full test suite after each mock change, revert if regressions |
| **Zod validation too strict (rejects valid data)** | MEDIUM (API calls fail) | LOW | Use `.passthrough()` on schemas to allow extra fields |
| **Material color rendering performance** | LOW (canvas FPS drop) | LOW | Benchmark with 500+ elements, memoize color lookups |
| **62 materials overwhelm UI filters dropdown** | MEDIUM (UX issue) | HIGH | Group materials by category (Warm, Gray, Blue, etc.) |
| **Breaking changes impact US-010 Modal** | HIGH (Modal broken) | LOW | Test PartDetailModal with Element type before merge |

---

## 13. Dependencies Checklist

Before starting TDD-RED, verify:

- [ ] **Backend API deployed:** Endpoints `/api/elements`, `/api/elements/{id}`, `/api/elements/{id}/navigation` accessible
- [ ] **Database migrated:** `material_type` column exists, `workshop_id` removed (T-1501-DB)
- [ ] **Zod installed:** `npm list zod` shows `zod@^3.22.0`
- [ ] **MATERIAL_COLORS exists:** File `src/agent/constants.py` has 62-entry dictionary
- [ ] **Test baseline established:** Current frontend tests: 407 total, X passing (document in TDD-RED start)

---

## 14. Documentation Updates Required

1. **Update `docs/US-015/README.md`**
   - Add "Frontend Migration Completed" section
   - Link to this Technical Spec
   - Document breaking changes (PartCanvasItem → Element)

2. **Update `memory-bank/systemPatterns.md`**
   - Add Element API contract patterns
   - Document Zod validation pattern
   - Add MATERIAL_COLORS reference

3. **Update `memory-bank/activeContext.md`**
   - Move T-1505-FRONT to "In Progress"
   - Document current phase: "TDD-RED"

4. **Create `docs/US-015/MIGRATION-GUIDE.md`**
   - Step-by-step for future developers
   - Code examples: Old (Part) vs New (Element)
   - Common pitfalls and fixes

---

**END OF TECHNICAL SPECIFICATION**

This spec is ready for TDD-RED phase. Use `:tdd-red` snippet with ticket ID `T-1505-FRONT`.
