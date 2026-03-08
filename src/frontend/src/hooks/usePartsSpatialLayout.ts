/**
 * Hook: usePartsSpatialLayout
 *
 * T-0505-FRONT: Calculate 3D positions for parts in the scene
 *
 * Strategy: Parts are positioned at their real building coordinates from Rhino.
 * Each part's position is calculated from its bounding box center (bbox.min + bbox.max) / 2.
 * This creates a true digital twin where parts maintain their actual spatial relationships.
 *
 * Scene unit = 1 m (Rhino native units for Sagrada Família). Parts appear at their
 * real building positions (e.g., [-8, -53, 74] m for a part at its location in the building).
 *
 * Fallback: If bbox is NULL (part still processing), position defaults to [0, 0, 0].
 * The GLB geometry already contains the Z→Y rotation applied during export (backend).
 *
 * @module usePartsSpatialLayout
 */

import { useMemo } from 'react';
import { PartCanvasItem } from '@/types/parts';
import { Position3D } from '@/components/Dashboard/PartsScene.types';

/**
 * Calculate spatial positions for parts in 3D scene from their bbox centers.
 *
 * @param parts - Array of parts to position
 * @returns Array of Position3D tuples representing real building coordinates
 */
export function usePartsSpatialLayout(parts: PartCanvasItem[]): Position3D[] {
  return useMemo(() => {
    return parts.map((part) => {
      if (!part.bbox) {
        // Fallback: if bbox is NULL (processing), default to origin
        console.warn(`Part ${part.iso_code} has no bbox, defaulting to [0,0,0]`);
        return [0, 0, 0] as Position3D;
      }
      
      // Calculate bbox center (real building position)
      const centerX = (part.bbox.min[0] + part.bbox.max[0]) / 2;
      const centerY = (part.bbox.min[1] + part.bbox.max[1]) / 2;
      const centerZ = (part.bbox.min[2] + part.bbox.max[2]) / 2;
      
      return [centerX, centerY, centerZ] as Position3D;
    });
  }, [parts]);
}
