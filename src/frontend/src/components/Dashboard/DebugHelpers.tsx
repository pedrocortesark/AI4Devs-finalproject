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
 */
function calculateGlobalBounds(parts: PartCanvasItem[]) {
  if (parts.length === 0) return null;

  const partsWithBbox = parts.filter(p => p.bbox);
  if (partsWithBbox.length === 0) return null;

  const globalMin = [Infinity, Infinity, Infinity];
  const globalMax = [-Infinity, -Infinity, -Infinity];

  partsWithBbox.forEach(part => {
    if (!part.bbox) return;
    
    for (let i = 0; i < 3; i++) {
      globalMin[i] = Math.min(globalMin[i], part.bbox.min[i]);
      globalMax[i] = Math.max(globalMax[i], part.bbox.max[i]);
    }
  });

  const center = [
    (globalMin[0] + globalMax[0]) / 2,
    (globalMin[1] + globalMax[1]) / 2,
    (globalMin[2] + globalMax[2]) / 2,
  ];

  const size = [
    globalMax[0] - globalMin[0],
    globalMax[1] - globalMin[1],
    globalMax[2] - globalMin[2],
  ];

  return { globalMin, globalMax, center, size };
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
    console.log('Global bounds (raw coordinates):');
    console.log(`  Min: [${bounds.globalMin.map(v => v.toFixed(2)).join(', ')}]`);
    console.log(`  Max: [${bounds.globalMax.map(v => v.toFixed(2)).join(', ')}]`);
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
      {/* Origin marker - Sphere at (0, 0, 0) */}
      <mesh position={[0, 0, 0]} name="origin-marker">
        <sphereGeometry args={[1, 16, 16]} />
        <meshStandardMaterial 
          color="#ff0000" 
          emissive="#ff0000" 
          emissiveIntensity={0.5}
          opacity={0.8}
          transparent
        />
      </mesh>

      {/* Centroid marker - Shows center of all parts */}
      <mesh 
        position={bounds.center as [number, number, number]} 
        name="centroid-marker"
      >
        <sphereGeometry args={[2, 16, 16]} />
        <meshStandardMaterial 
          color="#00ff00" 
          emissive="#00ff00" 
          emissiveIntensity={0.5}
          opacity={0.8}
          transparent
        />
      </mesh>

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
