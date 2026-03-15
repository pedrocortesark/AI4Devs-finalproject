/**
 * PartsScene Component
 * 
 * T-0505-FRONT: Orchestrator component for 3D parts rendering
 * T-0507-FRONT: Added LOD system (preload disabled for OBJ format)
 * US-015: Updated to use ElementMesh (renamed from PartMesh)
 * 
 * Renders N parts with OBJLoader (loaded in ElementMesh), skipping parts without geometry.
 * OBJ files contain absolute Rhino Z-up coordinates, rotated to Y-up in ElementMesh.
 * Includes professional CAD-style camera controls (Fit All + Focus Selected).
 * 
 * @module PartsScene
 */

import { useMemo } from 'react';
import { ElementMesh } from './ElementMesh';
import { CameraController } from './CameraController';
import { DebugOverlay } from './DebugOverlay';
import { usePartsSpatialLayout } from '@/hooks/usePartsSpatialLayout';
import type { PartsSceneProps } from './PartsScene.types';

/**
 * PartsScene: Renders N parts in 3D space with LOD
 *
 * @param props.parts - Array of parts to render
 * @param props.selectedId - Currently selected part ID (for camera focus)
 * 
 * @example
 * ```tsx
 * <Canvas>
 *   <PartsScene parts={parts} selectedId={selectedId} />
 * </Canvas>
 * ```
 */
export function PartsScene({ parts, selectedId = null }: PartsSceneProps) {
  // Filter parts with valid geometry
  const partsWithGeometry = useMemo(() => {
    return parts.filter((part) => part.low_poly_url !== null);
  }, [parts]);

  // Calculate positions for all parts with geometry (bbox center with Z-up → Y-up rotation)
  const positions = usePartsSpatialLayout(partsWithGeometry);

  // PRELOAD DISABLED: OBJLoader doesn't have a .preload() method like useGLTF
  // When we used GLBs, this prevented pop-in during LOD transitions
  // With OBJ files, Three.js loader cache handles this automatically
  // useEffect(() => {
  //   const sanitizeUrl = (url: string) => url.replace(/\?$/, '');
  //   partsWithGeometry.forEach((part) => {
  //     if (part.mid_poly_url) {
  //       useGLTF.preload(sanitizeUrl(part.mid_poly_url));
  //     }
  //     if (part.low_poly_url) {
  //       useGLTF.preload(sanitizeUrl(part.low_poly_url));
  //     }
  //   });
  // }, [partsWithGeometry]);

  return (
    <group name="parts-scene">
      {/* Professional CAD-style camera controls */}
      <CameraController parts={partsWithGeometry} selectedId={selectedId} />
      
      {/* Debug Overlay - Visual diagnostics */}
      <DebugOverlay parts={parts} />
      
      {/* Mesh Debugger - DISABLED (was interfering with visualization) */}
      {/* <MeshDebugger parts={partsWithGeometry} positions={positions} /> */}
      
      {/* Render individual element meshes with LOD */}
      {/* OBJ geometry contains absolute Rhino coordinates; no position offset needed */}
      {partsWithGeometry.map((part, index) => (
        <ElementMesh
          key={part.id}
          part={part}
          position={positions[index]}
          enableLod={true}
        />
      ))}
    </group>
  );
}
