/**
 * Hook: useLOD
 * 
 * Custom LOD (Level of Detail) system for ElementMesh.
 * Replaces drei's <Detailed> component which has issues with OBJ geometry.
 * 
 * Calculates camera distance to element and returns appropriate LOD level.
 * 
 * LOD Levels:
 * - 0 (high): 0-5m - Maximum detail for close inspection
 * - 1 (mid): 5-20m - Normal working distance
 * - 2 (low): 20-50m - Overview mode
 * - 3 (bbox): >50m - Wireframe proxy for distant view
 * 
 * @module useLOD
 */

import { useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * LOD distance thresholds (in meters)
 * Same as drei's <Detailed distances={[0, 5, 20, 50]}>
 */
const LOD_DISTANCES = [5, 20, 50];

/**
 * Calculate LOD level based on camera distance
 * 
 * @param elementPosition - Position of the element [x, y, z]
 * @returns Current LOD level (0-3)
 */
export function useLOD(elementPosition: [number, number, number]): number {
  const { camera } = useThree();
  const [lodLevel, setLodLevel] = useState(1); // Default to mid-poly

  useFrame(() => {
    // Calculate distance from camera to element
    const elementPos = new THREE.Vector3(...elementPosition);
    const distance = camera.position.distanceTo(elementPos);

    // Determine LOD level based on distance
    let newLevel = 3; // Default: bbox (furthest)
    if (distance < LOD_DISTANCES[0]) {
      newLevel = 0; // high-poly
    } else if (distance < LOD_DISTANCES[1]) {
      newLevel = 1; // mid-poly
    } else if (distance < LOD_DISTANCES[2]) {
      newLevel = 2; // low-poly
    }

    // Update state only if level changed (avoid unnecessary re-renders)
    if (newLevel !== lodLevel) {
      setLodLevel(newLevel);
    }
  });

  return lodLevel;
}
