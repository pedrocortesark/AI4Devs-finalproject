/**
 * LOD (Level of Detail) System Configuration
 *
 * T-0507-FRONT: 3-level LOD system for performance optimization
 * US-015: Real LOD System with high/mid/low-poly GLBs (March 2026)
 *
 * Based on POC validation (docs/US-005/PERFORMANCE-ANALYSIS-3D-FORMATS.md):
 * - 60 FPS achieved with 1197 meshes (39,360 triangles)
 * - 41 MB heap memory (5x better than 500 MB target)
 * - Extrapolation: 150 parts × 12 tris/bbox = 1,800 triangles (96% reduction at distance)
 *
 * UNIT SYSTEM: all distances are in metres (1 scene unit = 1 m).
 *
 * @module lod.constants
 */

/**
 * LOD level distances in metres (scene units).
 * 
 * US-015: Updated to 4 levels (high/mid/low + bbox) based on architectural CAD best practices
 *
 * Arrays are passed to drei <Detailed distances={LOD_DISTANCES}>:
 * - Level 0: 0 to 5m     → high-poly (5000-8000 tris, detailed inspection)
 * - Level 1: 5 to 20m    → mid-poly (1500-2000 tris, normal working distance)
 * - Level 2: 20 to 50m   → low-poly (400-600 tris, overview)
 * - Level 3: 50m+        → BBox proxy (12 tris, distant view)
 *
 * @constant
 * @readonly
 */
export const LOD_DISTANCES = [0, 5, 20, 50] as const;

/**
 * LOD level identifiers
 * Maps semantic names to array indices for clarity
 *
 * @constant
 * @readonly
 */
export const LOD_LEVELS = {
  /** Level 0: High-poly geometry (<5 m) - 5000-8000 triangles */
  HIGH_POLY: 0,

  /** Level 1: Mid-poly geometry (5-20 m) - 1500-2000 triangles */
  MID_POLY: 1,

  /** Level 2: Low-poly geometry (20-50 m) - 400-600 triangles */
  LOW_POLY: 2,

  /** Level 3: BBox wireframe proxy (>50 m) - 12 triangles */
  BBOX_PROXY: 3,
} as const;

/**
 * LOD Configuration Metadata
 * Targets and thresholds for performance monitoring
 *
 * @constant
 * @readonly
 */
export const LOD_CONFIG = {
  /** Target FPS with 150 parts rendered */
  TARGET_FPS: 30,

  /** Maximum acceptable memory heap size (MB) */
  MAX_MEMORY_MB: 500,

  /** Triangle counts per LOD level */
  TRIANGLES: {
    MID_POLY: 1000,
    LOW_POLY: 500,
    BBOX: 12,
  },

  /** Distance thresholds in metres */
  DISTANCE_THRESHOLDS: {
    MID_POLY_MAX: 20,    // Level 0 active from 0 to 20 m
    LOW_POLY_MIN: 20,    // Level 1 active from 20 m to 50 m
    LOW_POLY_MAX: 50,
    BBOX_MIN: 50,        // Level 2 active from 50 m onwards
  },
} as const;

/**
 * Type guard: Check if value is valid LOD level
 *
 * @param level - Value to check
 * @returns True if level is 0, 1, or 2
 *
 * @example
 * ```ts
 * if (isValidLodLevel(userInput)) {
 *   switchToLevel(userInput); // TypeScript knows it's 0 | 1 | 2
 * }
 * ```
 */
export function isValidLodLevel(level: number): level is 0 | 1 | 2 {
  return level === 0 || level === 1 || level === 2;
}
