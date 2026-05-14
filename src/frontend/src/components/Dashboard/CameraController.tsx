/**
 * CameraController Component
 * 
 * Implements CAD-style camera controls:
 * - "Fit All" on initial scene load
 * - "Focus Selected" with 'F' key
 * 
 * Uses professional trigonometric calculations for camera positioning
 * and smooth GSAP animations for transitions.
 * 
 * @module CameraController
 */

import { useEffect, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import { OrbitControls } from 'three-stdlib';
import * as THREE from 'three';
import { calculateCameraFit } from '@/utils/cameraUtils';
import { useCameraAnimationWithControls } from '@/hooks/useCameraAnimation';
import { CAMERA_FIT_CONFIG } from './Dashboard3D.constants';
import type { PartCanvasItem } from '@/types/parts';

interface CameraControllerProps {
  /** Array of parts to fit camera to on initial load */
  parts: PartCanvasItem[];
  /** Currently selected part ID (for 'F' key focus) */
  selectedId: string | null;
}

/**
 * CameraController - Handles "Fit All" and "Focus Selected" camera operations.
 * 
 * - Automatically fits camera to all parts on initial load (with smooth animation)
 * - Listens for 'F' key to focus on selected part
 * - Falls back to "Fit All" if 'F' pressed with no selection
 * 
 * @example
 * ```tsx
 * <Canvas>
 *   <CameraController parts={parts} selectedId={selectedId} />
 *   <PartsScene parts={parts} />
 * </Canvas>
 * ```
 */
export function CameraController({ parts, selectedId }: CameraControllerProps) {
  const { camera, scene } = useThree();
  const controls = useThree((state) => state.controls) as OrbitControls | null;
  const { animateTo } = useCameraAnimationWithControls(controls);
  
  // Track if we've successfully fitted to prevent redundant animations
  const lastFittedCountRef = useRef(0);

  // US-015: Fit All automatic animation - RE-ENABLED
  // Fits camera to all parts on initial load with smooth animation
  // User can also manually trigger with 'F' key
  
  // Fit All - runs when parts change (but not on every render)
  useEffect(() => {
    console.log('🎥 CameraController: useEffect triggered', { 
      partsCount: parts.length,
      hasControls: !!controls,
      lastFittedCount: lastFittedCountRef.current
    });

    if (parts.length === 0 || !controls) {
      console.log('🎥 CameraController: Waiting for parts/controls...', { 
        partsCount: parts.length, 
        hasControls: !!controls 
      });
      return;
    }

    // Skip if we already fitted to the same number of parts (avoid redundant fits)
    if (parts.length === lastFittedCountRef.current) {
      console.log('🎥 CameraController: Already fitted to this count, skipping');
      return;
    }

    console.log(`🎥 CameraController: ✅ Fitting camera to ${parts.length} parts`);

    // Filter parts with bbox data
    const partsWithBbox = parts.filter((p) => p.bbox);
    if (partsWithBbox.length === 0) {
      console.warn('⚠️ CameraController: No parts with bbox found');
      return;
    }

    console.log(`🎥 CameraController: Found ${partsWithBbox.length} parts with bbox data`);

    // Calculate camera position using bbox data (not mesh geometry)
    // CRITICAL: Must apply Z-up → Y-up rotation to match GLB positioning
    const rhinoMin = new THREE.Vector3(Infinity, Infinity, Infinity);
    const rhinoMax = new THREE.Vector3(-Infinity, -Infinity, -Infinity);

    partsWithBbox.forEach((part) => {
      if (!part.bbox) return;
      rhinoMin.x = Math.min(rhinoMin.x, part.bbox.min[0]);
      rhinoMin.y = Math.min(rhinoMin.y, part.bbox.min[1]);
      rhinoMin.z = Math.min(rhinoMin.z, part.bbox.min[2]);
      rhinoMax.x = Math.max(rhinoMax.x, part.bbox.max[0]);
      rhinoMax.y = Math.max(rhinoMax.y, part.bbox.max[1]);
      rhinoMax.z = Math.max(rhinoMax.z, part.bbox.max[2]);
    });

    // Calculate center in Rhino coordinates
    const rhinoCenter = new THREE.Vector3(
      (rhinoMin.x + rhinoMax.x) / 2,
      (rhinoMin.y + rhinoMax.y) / 2,
      (rhinoMin.z + rhinoMax.z) / 2
    );

    // Apply Z-up → Y-up rotation (matches usePartsSpatialLayout)
    // Rhino (X, Y, Z) → Three.js (X, Z, -Y)
    const center = new THREE.Vector3(
      rhinoCenter.x,   // X stays same
      rhinoCenter.z,   // Rhino Z becomes Three.js Y
      -rhinoCenter.y   // Rhino Y becomes Three.js -Z
    );

    const bboxSize = new THREE.Vector3(
      rhinoMax.x - rhinoMin.x,
      rhinoMax.z - rhinoMin.z,  // Height in Three.js is Rhino Z range
      rhinoMax.y - rhinoMin.y   // Depth in Three.js is Rhino Y range
    );
    const radius = bboxSize.length() / 2;

    // Calculate distance with aspect ratio consideration
    const perspCam = camera as THREE.PerspectiveCamera;
    const vFOV = perspCam.fov;
    const hFOV = vFOV * perspCam.aspect;
    const effectiveFOV = Math.min(vFOV, hFOV);
    const fovRadians = (effectiveFOV * Math.PI) / 180;
    const distance = (radius * CAMERA_FIT_CONFIG.FIT_OFFSET) / Math.sin(fovRadians / 2);

    // US-015 Fix: Use sensible viewing angle for small objects
    // Instead of maintaining current direction, use diagonal offset [0, 2, 3] 
    // for comfortable viewing from slightly above and in front
    const viewingDirection = new THREE.Vector3(0, 2, 3).normalize();
    const newPosition = center.clone().add(viewingDirection.multiplyScalar(distance));

    console.log('🎥 Fit All calculated', {
      partsCount: partsWithBbox.length,
      center: center.toArray().map((v) => v.toFixed(2)),
      bboxSize: bboxSize.toArray().map((v) => v.toFixed(3)),
      radius: radius.toFixed(3),
      distance: distance.toFixed(3),
      newPosition: newPosition.toArray().map((v) => v.toFixed(2)),
    });

    // Animate to new position
    animateTo(newPosition, center, {
      duration: CAMERA_FIT_CONFIG.ANIMATION_DURATION,
      ease: CAMERA_FIT_CONFIG.ANIMATION_EASING,
    });

    lastFittedCountRef.current = parts.length;
  }, [parts, camera, controls, animateTo]);

  // Focus Selected - 'F' key handler
  useEffect(() => {
    const handleFocusKey = (event: KeyboardEvent) => {
      // Check for 'F' key (case-insensitive)
      if (event.key.toLowerCase() !== CAMERA_FIT_CONFIG.FOCUS_KEY) return;

      // Prevent default browser behavior (e.g., Find in page)
      event.preventDefault();

      if (!controls) {
        console.warn('⚠️ CameraController: OrbitControls not available');
        return;
      }

      // Case 1: No selection - do "Fit All"
      if (!selectedId) {
        console.log('🎯 Focus key pressed (no selection): Fitting all parts');
        
        const partsGroup = scene.getObjectByName('parts-scene');
        if (!partsGroup) {
          console.warn('⚠️ Parts scene group not found');
          return;
        }

        const result = calculateCameraFit(
          camera as THREE.PerspectiveCamera,
          partsGroup,
          CAMERA_FIT_CONFIG.FIT_OFFSET,
          controls
        );

        animateTo(result.position, result.target, {
          duration: CAMERA_FIT_CONFIG.ANIMATION_DURATION,
          ease: CAMERA_FIT_CONFIG.ANIMATION_EASING,
        });

        return;
      }

      // Case 2: Focus on selected part
      console.log(`🎯 Focus key pressed: Focusing on part ${selectedId}`);

      // Find selected part mesh in scene by traversing and checking userData.partId
      let selectedMesh: THREE.Object3D | null = null;
      scene.traverse((obj) => {
        if (obj.userData?.partId === selectedId) {
          selectedMesh = obj;
        }
      });

      if (!selectedMesh) {
        console.warn(`⚠️ Selected part mesh not found: ${selectedId}`);
        return;
      }

      // Type assertion: After null check above, we know selectedMesh is not null
      const mesh = selectedMesh as THREE.Object3D;

      // Force matrix update before bounding box calculation
      mesh.updateMatrixWorld(true);

      const meshPos = mesh.position;
      const worldPos = mesh.getWorldPosition(new THREE.Vector3());
      console.log('🎯 Selected mesh found:');
      console.log(`   name: ${mesh.name}`);
      console.log(`   position: [${meshPos.x.toFixed(2)}, ${meshPos.y.toFixed(2)}, ${meshPos.z.toFixed(2)}]`);
      console.log(`   worldPosition: [${worldPos.x.toFixed(2)}, ${worldPos.y.toFixed(2)}, ${worldPos.z.toFixed(2)}]`);
      console.log(`   children: ${mesh.children.length}, type: ${mesh.type}`);

      // Calculate fit for selected object
      const result = calculateCameraFit(
        camera as THREE.PerspectiveCamera,
        mesh,
        CAMERA_FIT_CONFIG.FIT_OFFSET,
        controls
      );

      console.log('🎯 Camera fit calculated:');
      console.log(`   target: [${result.target.x.toFixed(2)}, ${result.target.y.toFixed(2)}, ${result.target.z.toFixed(2)}]`);
      console.log(`   position: [${result.position.x.toFixed(2)}, ${result.position.y.toFixed(2)}, ${result.position.z.toFixed(2)}]`);
      console.log(`   distance: ${result.distance.toFixed(2)}, radius: ${result.radius.toFixed(3)}`);

      animateTo(result.position, result.target, {
        duration: CAMERA_FIT_CONFIG.ANIMATION_DURATION,
        ease: CAMERA_FIT_CONFIG.ANIMATION_EASING,
        onComplete: () => {
          console.log(`✅ Focused on part ${selectedId}`);
        },
      });
    };

    window.addEventListener('keydown', handleFocusKey);

    return () => {
      window.removeEventListener('keydown', handleFocusKey);
    };
  }, [selectedId, camera, scene, controls, animateTo]);

  return null; // This component only handles logic, renders nothing
}
