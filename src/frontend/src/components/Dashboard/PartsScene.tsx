/**
 * PartsScene Component
 * 
 * T-0505-FRONT: Orchestrator component for 3D parts rendering
 * T-0507-FRONT: Added LOD system with preload strategy
 * 
 * Renders N parts with useGLTF(part.low_poly_url), skipping parts without geometry.
 * Preloads all geometry URLs to prevent pop-in during LOD transitions.
 * 
 * @module PartsScene
 */

import { useMemo, useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF, useBounds } from '@react-three/drei';
import { PartMesh } from './PartMesh';
import { usePartsSpatialLayout } from '@/hooks/usePartsSpatialLayout';
import type { PartsSceneProps } from './PartsScene.types';

/**
 * Triggers camera refit once GLB geometry is actually present in the scene.
 *
 * Problem with a fixed setTimeout: GLBs load asynchronously from Supabase.
 * If we call bounds.refresh().fit() before the meshes appear in the Three.js
 * scene, the bounding box is empty and the camera doesn't move.
 *
 * Solution: poll every frame with useFrame, look inside the 'parts-scene'
 * group for any Mesh object. As soon as geometry appears (Suspense resolved +
 * Three.js object added), fit the camera and stop polling.
 */
function BoundsRefitter({ count }: { count: number }) {
  const bounds = useBounds();
  const fittedRef = useRef(false);

  // Reset fitted flag whenever the number of geometry parts changes
  // (e.g., filters applied, new parts uploaded) so the camera re-fits.
  useEffect(() => {
    if (count > 0) {
      console.log(`🎥 BoundsRefitter: Resetting for ${count} parts`);
      fittedRef.current = false;
    }
  }, [count]);

  // Fallback: after a short delay, force-fit even if useFrame polling missed
  // the Suspense resolution window. This handles the case where Bounds.fit
  // fires before any GLB is in the THREE.js scene (empty bounds → no-op),
  // and the useFrame loop never catches it because hasMesh stays false.
  useEffect(() => {
    if (count === 0) return;
    const timer = setTimeout(() => {
      if (!fittedRef.current) {
        console.log('🎥 BoundsRefitter: Fallback timeout - forcing fit');
        bounds.refresh().fit();
        fittedRef.current = true;
      }
    }, 1000); // 1s timeout for faster response
    return () => clearTimeout(timer);
  }, [count, bounds]);

  useFrame((state) => {
    if (count === 0 || fittedRef.current) return;

    // Find the parts-scene group in the Three.js scene graph
    let partsGroup: any = null;
    state.scene.traverse((obj: any) => {
      if (obj.name === 'parts-scene') partsGroup = obj;
    });
    if (!partsGroup) return;

    // Check whether any Mesh has been added (GLBs resolved from Suspense)
    let hasMesh = false;
    partsGroup.traverse((obj: any) => {
      if (obj.isMesh) hasMesh = true;
    });
    if (!hasMesh) return;

    // Geometry is present — fit camera and stop polling
    console.log('🎥 BoundsRefitter: Meshes detected, fitting camera');
    bounds.refresh().fit();
    fittedRef.current = true;
  });

  return null;
}


/**
 * PartsScene: Renders N parts in 3D space with LOD
 *
 * @param props.parts - Array of parts to render
 * 
 * @example
 * ```tsx
 * <Canvas>
 *   <PartsScene parts={parts} />
 * </Canvas>
 * ```
 */
export function PartsScene({ parts }: PartsSceneProps) {
  // Filter parts with valid geometry
  const partsWithGeometry = useMemo(() => {
    return parts.filter((part) => part.low_poly_url !== null);
  }, [parts]);

  // Calculate positions for all parts with geometry
  const positions = usePartsSpatialLayout(partsWithGeometry);

  // Preload all geometry URLs to prevent pop-in during LOD transitions (T-0507)
  useEffect(() => {
    partsWithGeometry.forEach((part) => {
      // Preload mid-poly if available
      if (part.mid_poly_url) {
        useGLTF.preload(part.mid_poly_url);
      }
      // Always preload low-poly
      if (part.low_poly_url) {
        useGLTF.preload(part.low_poly_url);
      }
    });
  }, [partsWithGeometry]);

  return (
    <group name="parts-scene">
      <BoundsRefitter count={partsWithGeometry.length} />
      {partsWithGeometry.map((part, index) => (
        <PartMesh
          key={part.id}
          part={part}
          position={positions[index]}
          enableLod={true}
        />
      ))}
    </group>
  );
}
