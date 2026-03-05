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
import { useFrame, useThree } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { Vector3 } from 'three';
import { PartMesh } from './PartMesh';
import { usePartsSpatialLayout } from '@/hooks/usePartsSpatialLayout';
import type { PartsSceneProps } from './PartsScene.types';

/**
 * Manual camera fitting - immediately positions camera based on parts bbox data.
 * Does not wait for meshes to load.
 */
function ManualCameraFit({ parts }: { parts: PartsSceneProps['parts'] }) {
  const { camera, size } = useThree();
  const fittedRef = useRef(false);

  useEffect(() => {
    if (parts.length === 0) return;
    
    console.log(`🎥 ManualCameraFit: ${parts.length} parts detected`);

    // Calculate bounding box immediately from parts data
    const partsWithBbox = parts.filter(p => p.bbox);
    if (partsWithBbox.length === 0) {
      console.warn('🎥 No parts with bbox found');
      return;
    }

    const globalMin = new Vector3(Infinity, Infinity, Infinity);
    const globalMax = new Vector3(-Infinity, -Infinity, -Infinity);

    partsWithBbox.forEach(part => {
      if (!part.bbox) return;
      globalMin.x = Math.min(globalMin.x, part.bbox.min[0]);
      globalMin.y = Math.min(globalMin.y, part.bbox.min[1]);
      globalMin.z = Math.min(globalMin.z, part.bbox.min[2]);
      globalMax.x = Math.max(globalMax.x, part.bbox.max[0]);
      globalMax.y = Math.max(globalMax.y, part.bbox.max[1]);
      globalMax.z = Math.max(globalMax.z, part.bbox.max[2]);
    });

    const center = new Vector3(
      (globalMin.x + globalMax.x) / 2,
      (globalMin.y + globalMax.y) / 2,
      (globalMin.z + globalMax.z) / 2
    );

    const bboxSize = new Vector3(
      globalMax.x - globalMin.x,
      globalMax.y - globalMin.y,
      globalMax.z - globalMin.z
    );
    const radius = bboxSize.length() / 2;

    // Calculate distance with aspect ratio consideration
    const perspCam = camera as any;
    const vFOV = perspCam.fov;
    const hFOV = vFOV * perspCam.aspect;
    const effectiveFOV = Math.min(vFOV, hFOV);
    const fovRadians = (effectiveFOV * Math.PI) / 180;
    const distance = radius / Math.sin(fovRadians / 2);

    // Position camera immediately
    const offset = new Vector3(1, 1, 1).normalize().multiplyScalar(distance);
    camera.position.copy(center.clone().add(offset));
    camera.lookAt(center);
    camera.updateProjectionMatrix();

    console.log('🎥 Camera positioned IMMEDIATELY', {
      partsCount: partsWithBbox.length,
      center: center.toArray().map(v => v.toFixed(2)),
      bboxSize: bboxSize.toArray().map(v => v.toFixed(3)),
      radius: radius.toFixed(3),
      vFOV: vFOV.toFixed(1),
      hFOV: hFOV.toFixed(1),
      effectiveFOV: effectiveFOV.toFixed(1),
      aspect: perspCam.aspect.toFixed(2),
      distance: distance.toFixed(3),
      cameraPos: camera.position.toArray().map(v => v.toFixed(2)),
    });

    fittedRef.current = true;
  }, [parts, camera, size]);

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
      <ManualCameraFit parts={partsWithGeometry} />
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
