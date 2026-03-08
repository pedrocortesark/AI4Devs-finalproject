/**
 * Dashboard 3D Constants
 *
 * T-0505-FRONT: Constants for 3D Parts Scene rendering
 *
 * UNIT SYSTEM: all Three.js distances are in metres (1 scene unit = 1 m).
 *
 * @module dashboard3d.constants
 */

import { BlockStatus } from '@/types/parts';

/**
 * Color mapping for part status in 3D scene
 * Colors use Tailwind CSS palette for consistency
 */
export const STATUS_COLORS: Record<BlockStatus, string> = {
  uploaded: '#94A3B8',        // Slate 400 - neutral gray
  processing: '#A78BFA',      // Violet 400 - processing indicator
  validated: '#3B82F6',       // Blue 500 - approved
  rejected: '#EF4444',        // Red 500 - rejected
  in_fabrication: '#F59E0B',  // Amber 500 - in progress
  completed: '#10B981',       // Emerald 500 - done
  error_processing: '#DC2626',// Red 600 - error state
  archived: '#6B7280',        // Gray 500 - archived
};

/**
 * Grid layout configuration for automatic part positioning — distances in metres.
 */
export const GRID_SPACING = 5;  // 5 m between part groups in the fallback grid layout.
export const GRID_COLUMNS = 10; // 10×10 grid for automatic layout

/**
 * LOD (Level of Detail) distance thresholds in metres
 * Used by T-0507-FRONT LOD System
 */
export const LOD_DISTANCES = {
  NEAR: 0,    // <20 m: Full detail (1000 triangles)
  MID: 20,    // 20–50 m: Mid detail (500 triangles)
  FAR: 50,    // >50 m: Bounding box proxy
};

/**
 * Camera configuration defaults — distances in metres.
 */
export const CAMERA_DEFAULTS = {
  POSITION: [50, 50, 50] as [number, number, number], // 50 m from origin
  FOV: 60,
  NEAR: 0.001,  // 1 mm
  FAR: 10000,   // 10 km
};
