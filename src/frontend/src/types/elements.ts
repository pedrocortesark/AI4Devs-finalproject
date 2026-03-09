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
 * - Renamed: PartMesh Component → Element, PartsListResponse → ElementsListResponse
 * - Renamed: tipologia → material_type (now validated string against 62 materials)
 * 
 * @see src/backend/schemas.py - Element, ElementDetail, ElementsListResponse
 * @see src/agent/constants.py - MATERIAL_COLORS (62 materials with RGB tuples)
 */

// ===== Re-export types from Zod schemas =====
// This ensures runtime validation and TypeScript types stay in sync

export type {
  Element,
  ElementStatus,
  MaterialType,
  ElementsListResponse,
  ElementDetail,
  ElementNavigationResponse,
  ElementsQueryParams,
} from '../schemas/elements.schema';

// ===== Bounding Box =====

export interface BoundingBox {
  min: [number, number, number];  // [x, y, z] - exactly 3 elements
  max: [number, number, number];  // [x, y, z] - exactly 3 elements
}

/**
 * Helper to compute bbox center (for canvas positioning in T-1505)
 * 
 * @param bbox - Bounding box with min and max coordinates
 * @returns Center point [x, y, z]
 * 
 * @example
 * const bbox = { min: [-1, -2, -1], max: [1, 2, 1] };
 * const center = computeBBoxCenter(bbox); // [0, 0, 0]
 */
export function computeBBoxCenter(bbox: BoundingBox): [number, number, number] {
  return [
    (bbox.min[0] + bbox.max[0]) / 2,
    (bbox.min[1] + bbox.max[1]) / 2,
    (bbox.min[2] + bbox.max[2]) / 2,
  ];
}
