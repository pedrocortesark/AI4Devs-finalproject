/**
 * DebugHelpers Component
 * 
 * Visual aids for understanding coordinate system and part positioning
 * 
 * Features:
 * - Origin marker at (0,0,0)
 * - Centroid marker showing average position of all parts
 * - Console logging of bounding box info
 * 
 * @module DebugHelpers
 */

import { useEffect, useMemo } from 'react';
import type { PartCanvasItem } from '@/types/parts';

interface DebugHelpersProps {
  parts: PartCanvasItem[];
  enabled?: boolean;
}

/**
 * Calculate bounding box encompassing all parts
 * CRITICAL: Must apply Z-up → Y-up rotation to match GLB positioning
 */
function calculateGlobalBounds(parts: PartCanvasItem[]) {
  if (parts.length === 0) return null;

  const partsWithBbox = parts.filter(p => p.bbox);
  if (partsWithBbox.length === 0) return null;

  const globalMin = [Infinity, Infinity, Infinity];
  const globalMax = [-Infinity, -Infinity, -Infinity];

  // Calculate bounds in Rhino coordinates first
  const rhinoMin = [Infinity, Infinity, Infinity];
  const rhinoMax = [-Infinity, -Infinity, -Infinity];
  
  partsWithBbox.forEach(part => {
    if (!part.bbox) return;
    
    for (let i = 0; i < 3; i++) {
      rhinoMin[i] = Math.min(rhinoMin[i], part.bbox.min[i]);
      rhinoMax[i] = Math.max(rhinoMax[i], part.bbox.max[i]);
    }
  });

  // Calculate center in Rhino coordinates
  const rhinoCenter = [
    (rhinoMin[0] + rhinoMax[0]) / 2,
    (rhinoMin[1] + rhinoMax[1]) / 2,
    (rhinoMin[2] + rhinoMax[2]) / 2,
  ];

  // Apply Z-up → Y-up rotation (same as usePartsSpatialLayout)
  // Rhino (X, Y, Z) → Three.js (X, Z, -Y)
  const center = [
    rhinoCenter[0],      // X stays same
    rhinoCenter[2],      // Rhino Z becomes Three.js Y
    -rhinoCenter[1],     // Rhino Y becomes Three.js -Z
  ];

  const size = [
    rhinoMax[0] - rhinoMin[0],
    rhinoMax[2] - rhinoMin[2],  // Height in Three.js is Rhino Z range
    rhinoMax[1] - rhinoMin[1],  // Depth in Three.js is Rhino Y range
  ];

  return { globalMin: rhinoMin, globalMax: rhinoMax, center, size };
}

/**
 * DebugHelpers: Visual aids for coordinate system debugging
 * 
 * @param props.parts - Array of parts to analyze
 * @param props.enabled - Enable debug helpers (default false)
 */
export function DebugHelpers({ parts, enabled = false }: DebugHelpersProps) {
  const bounds = useMemo(() => calculateGlobalBounds(parts), [parts]);

  useEffect(() => {
    if (!enabled || !bounds) return;

    console.group('🔍 Canvas Debug Info');
    console.log(`Parts loaded: ${parts.length}`);
    console.log(`Parts with bbox: ${parts.filter(p => p.bbox).length}`);
    console.log('Global bounds (Rhino raw coordinates):');
    console.log(`  Min: [${bounds.globalMin.map(v => v.toFixed(2)).join(', ')}]`);
    console.log(`  Max: [${bounds.globalMax.map(v => v.toFixed(2)).join(', ')}]`);
    console.log('Transformed to Three.js (with Z-up → Y-up rotation):');
    console.log(`  Center: [${bounds.center.map(v => v.toFixed(2)).join(', ')}]`);
    console.log(`  Size: [${bounds.size.map(v => v.toFixed(2)).join(', ')}]`);
    console.log('📏 Distance from origin to center:', 
      Math.sqrt(bounds.center[0]**2 + bounds.center[1]**2 + bounds.center[2]**2).toFixed(2), 'm'
    );
    console.groupEnd();
  }, [enabled, bounds, parts.length]);

  if (!enabled || !bounds) return null;

  return (
    <group name="debug-helpers">
      {/* Line from origin to centroid */}
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={2}
            array={new Float32Array([
              0, 0, 0,
              bounds.center[0], bounds.center[1], bounds.center[2]
            ])}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#ffff00" linewidth={2} />
      </line>

      {/* Bounding box wireframe around all parts */}
      <mesh 
        position={bounds.center as [number, number, number]}
        name="global-bbox"
      >
        <boxGeometry args={bounds.size as [number, number, number]} />
        <meshBasicMaterial 
          color="#00ffff" 
          wireframe 
          opacity={0.3}
          transparent
        />
      </mesh>
    </group>
  );
}
