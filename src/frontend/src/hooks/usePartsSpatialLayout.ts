/**
 * Hook: usePartsSpatialLayout
 *
 * T-0505-FRONT: Calculate 3D positions for parts in the scene
 *
 * Strategy: Parts are positioned at their real building coordinates from Rhino.
 * Each part's position is calculated from its bounding box center (bbox.min + bbox.max) / 2.
 * This creates a true digital twin where parts maintain their actual spatial relationships.
 *
 * CRITICAL: The bbox coordinates in the database are in Rhino coordinate system (Z-up).
 * The GLB files have Z→Y rotation applied during export (backend geometry_processing.py).
 * Therefore, we must apply the same rotation to bbox positions for spatial alignment.
 *
 * Rotation: -90° around X-axis (Rhino Z-up → Three.js Y-up)
 * Transform: (X, Y, Z_rhino) → (X, Z_rhino, -Y_rhino) in Three.js
 *
 * Scene unit = 1 m (Rhino native units for Sagrada Família). Parts appear at their
 * real building positions transformed to Three.js coordinate system.
 *
 * Fallback: If bbox is NULL (part still processing), position defaults to [0, 0, 0].
 *
 * @module usePartsSpatialLayout
 */

import { useMemo } from 'react';
import { PartCanvasItem } from '@/types/parts';
import { Position3D } from '@/components/Dashboard/PartsScene.types';

/**
 * Calculate spatial positions for parts in 3D scene from their bbox centers.
 * Applies Z-up → Y-up rotation to match GLB coordinate system.
 *
 * @param parts - Array of parts to position
 * @returns Array of Position3D tuples in Three.js coordinates (Y-up)
 */
export function usePartsSpatialLayout(parts: PartCanvasItem[]): Position3D[] {
  return useMemo(() => {
    // DEBUG: Disabled to reduce console noise during React StrictMode
    // console.log('🎯 usePartsSpatialLayout: Calculating positions for', parts.length, 'parts');
    
    const positions = parts.map((part, index) => {
      if (!part.bbox) {
        // Fallback: if bbox is NULL (processing), default to origin
        console.warn(`Part ${part.iso_code} has no bbox, defaulting to [0,0,0]`);
        return [0, 0, 0] as Position3D;
      }
      
      // Calculate bbox center in Rhino coordinates (Z-up)
      const rhinoX = (part.bbox.min[0] + part.bbox.max[0]) / 2;
      const rhinoY = (part.bbox.min[1] + part.bbox.max[1]) / 2;
      const rhinoZ = (part.bbox.min[2] + part.bbox.max[2]) / 2;
      
      // Apply Z-up → Y-up rotation (-90° around X-axis)
      // Rhino (X, Y, Z) → Three.js (X, Z, -Y)
      const threejsX = rhinoX;
      const threejsY = rhinoZ;  // Rhino Z becomes Three.js Y
      const threejsZ = -rhinoY; // Rhino Y becomes Three.js -Z
      
      // DEBUG: Disabled to reduce console noise
      // if (index === 0) {
      //   console.log(`🎯 Part 0 (${part.iso_code}):`, {
      //     rhinoCoords: `[${rhinoX.toFixed(2)}, ${rhinoY.toFixed(2)}, ${rhinoZ.toFixed(2)}]`,
      //     threejsCoords: `[${threejsX.toFixed(2)}, ${threejsY.toFixed(2)}, ${threejsZ.toFixed(2)}]`,
      //     hasGLB: !!part.low_poly_url,
      //     glbUrl: part.low_poly_url?.substring(0, 60) + '...',
      //   });
      // }
      
      return [threejsX, threejsY, threejsZ] as Position3D;
    });
    
    // DEBUG: Disabled to reduce console noise
    // console.log('🎯 All positions calculated:', positions.length, 'positions');
    return positions;
  }, [parts]);
}
