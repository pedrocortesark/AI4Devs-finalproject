/**
 * T-0501-BACK Contract: 3D Canvas Parts API Types
 * 
 * CRITICAL: Must match backend Pydantic schemas exactly (field names, types, nullability)
 * 
 * Mapping rules:
 * - Python UUID → TypeScript string
 * - Python Optional[X] → TypeScript X | null
 * - Python List[float] → TypeScript number[]
 * - Python Enum → TypeScript enum (same string values)
 * 
 * @see src/backend/schemas.py - BlockStatus, BoundingBox, PartCanvasItem, PartsListResponse
 */

import type { ValidationReport } from './validation';

export enum BlockStatus {
  Uploaded = "uploaded",
  Processing = "processing",
  Validated = "validated",
  Rejected = "rejected",
  InFabrication = "in_fabrication",
  Completed = "completed",
  ErrorProcessing = "error_processing",
  Archived = "archived",
}

export interface BoundingBox {
  min: [number, number, number];  // [x, y, z] - exactly 3 elements
  max: [number, number, number];  // [x, y, z] - exactly 3 elements
}

export interface PartCanvasItem {
  id: string;                      // UUID string
  iso_code: string;                // e.g., "SF-C12-D-001"
  status: BlockStatus;             // Enum value
  tipologia: string;               // material_type (Montjuïc, Ulldecona, etc.) — mapped from API
  material?: string | null;        // Stone material from .3dm "Material" UserString (Material filter source)
  agrupacio: string | null;        // SF_ARC_Agrupacio1 from Rhino metadata
  high_poly_url?: string | null;   // US-015: High-poly URL (~7k tris) for LOD Level 0 (0-5m)
  mid_poly_url?: string | null;    // US-015: Mid-poly URL (~2k tris) for LOD Level 1 (5-20m)
  low_poly_url: string | null;     // US-015: Low-poly URL (~500 tris) for LOD Level 2 (20-50m), required fallback
  mtl_url?: string | null;         // Companion MTL for per-face Rhino layer colors (high-poly only)
  bbox: BoundingBox | null;        // 3D bounding box, or null if not extracted yet (used for LOD Level 3 >50m)
  workshop_id: string | null;      // UUID string or null if unassigned
  workshop_name?: string | null;   // Workshop display name (joined from workshops table) or null if unassigned
  rhino_metadata?: Record<string, unknown> | null;  // Raw Rhino metadata for material extraction
}

export interface PartsListResponse {
  parts: PartCanvasItem[];
  count: number;
  filters_applied: Record<string, string | null>;
}

/**
 * Query parameters for GET /api/parts (all optional)
 * Used by frontend to filter parts list
 */
export interface PartsQueryParams {
  status?: BlockStatus;
  tipologia?: string;
  workshop_id?: string;  // UUID string
}

/**
 * LOD (Level of Detail) Configuration
 * 
 * T-0507-FRONT: Interface for geometry LOD system
 * Represents the 3 levels of geometry detail based on camera distance
 * 
 * @see src/constants/lod.constants.ts - LOD_DISTANCES, LOD_LEVELS
 */
export interface LodConfig {
  /** Level 0: Mid-poly geometry URL (<20 units) - ~1000 triangles */
  midPolyUrl?: string;
  
  /** Level 1: Low-poly geometry URL (20-50 units) - ~500 triangles */
  lowPolyUrl?: string;
  
  /** Level 2: BBox for wireframe proxy (>50 units) - 12 triangles */
  bbox?: BoundingBox;
}

/**
 * T-1002-BACK / T-1005-FRONT Contract: Part Detail API Types
 * 
 * CRITICAL: Must match backend PartDetailResponse schema exactly
 * Used by GET /api/parts/{id} endpoint for 3D viewer modal
 * 
 * @see src/backend/schemas.py - PartDetailResponse (12 fields)
 */
export interface PartDetail {
  /** Part UUID */
  id: string;
  
  /** Part identifier (ISO-19650 format, e.g., SF-C12-D-001) */
  iso_code: string;
  
  /** Lifecycle state */
  status: BlockStatus;
  
  /** Part typology (capitel, columna, dovela, etc.) */
  tipologia: string;
  
  /** Creation timestamp (ISO 8601 datetime) */
  created_at: string;
  
  /** Presigned CDN URL for high-poly OBJ file (~7k tris), null if not generated yet */
  high_poly_url: string | null;
  
  /** Presigned CDN URL for mid-poly OBJ file (~2k tris), null if not generated yet */
  mid_poly_url: string | null;
  
  /** Presigned CDN URL for low-poly OBJ file (~500 tris), null if not generated yet */
  low_poly_url: string | null;

  /** Companion MTL URL with per-material-group colors from Rhino layers */
  mtl_url?: string | null;
  
  /** 3D bounding box for camera positioning */
  bbox: BoundingBox | null;
  
  /** Assigned workshop UUID (null if unassigned) */
  workshop_id: string | null;
  
  /** Workshop human-readable name (null if unassigned) */
  workshop_name: string | null;
  
  /** Validation results from The Librarian agent */
  validation_report: ValidationReport | null;
  
  /** GLB file size in bytes */
  glb_size_bytes: number | null;
  
  /** Triangle count (for performance monitoring) */
  triangle_count: number | null;

  /** Stone/material type (e.g., "Montjuïc", "Ulldecona") — maps to MATERIAL_COLORS */
  material_type?: string | null;

  /** Stone material from the .3dm "Material" UserString (source for the Material filter) */
  material?: string | null;

  /** Raw Rhino metadata attributes from .3dm file (key/value pairs) */
  rhino_metadata?: Record<string, unknown> | null;
}
