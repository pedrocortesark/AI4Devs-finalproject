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

  // TEMPORARILY DISABLED: Fit All automatic animation
  // Reason: Camera animation during GLB loading causes LOD calculation issues
  // Camera now starts at optimal position [1, -43, 84] (~17m from elements)
  // User can still manually trigger with 'F' key
  /*
  // Fit All - runs when parts change (but not on every render)
  useEffect(() => {
    if (parts.length === 0 || !controls) {
      console.log('🎥 CameraController: Waiting for parts/controls...', { 
        partsCount: parts.length, 
        hasControls: !!controls 
      });
      return;
    }

    // Skip if we already fitted to the same number of parts (avoid redundant fits)
    if (parts.length === lastFittedCountRef.current) {
      return;
    }

    console.log(`🎥 CameraController: Fitting camera to ${parts.length} parts`);

    // Filter parts with bbox data
    const partsWithBbox = parts.filter((p) => p.bbox);
    if (partsWithBbox.length === 0) {
      console.warn('⚠️ CameraController: No parts with bbox found');
      return;
    }

    // Calculate camera position using bbox data (not mesh geometry)
    const globalMin = new THREE.Vector3(Infinity, Infinity, Infinity);
    const globalMax = new THREE.Vector3(-Infinity, -Infinity, -Infinity);

    partsWithBbox.forEach((part) => {
      if (!part.bbox) return;
      globalMin.x = Math.min(globalMin.x, part.bbox.min[0]);
      globalMin.y = Math.min(globalMin.y, part.bbox.min[1]);
      globalMin.z = Math.min(globalMin.z, part.bbox.min[2]);
      globalMax.x = Math.max(globalMax.x, part.bbox.max[0]);
      globalMax.y = Math.max(globalMax.y, part.bbox.max[1]);
      globalMax.z = Math.max(globalMax.z, part.bbox.max[2]);
    });

    const center = new THREE.Vector3(
      (globalMin.x + globalMax.x) / 2,
      (globalMin.y + globalMax.y) / 2,
      (globalMin.z + globalMax.z) / 2
    );

    const bboxSize = new THREE.Vector3(
      globalMax.x - globalMin.x,
      globalMax.y - globalMin.y,
      globalMax.z - globalMin.z
    );
    const radius = bboxSize.length() / 2;

    // Calculate distance with aspect ratio consideration
    const perspCam = camera as THREE.PerspectiveCamera;
    const vFOV = perspCam.fov;
    const hFOV = vFOV * perspCam.aspect;
    const effectiveFOV = Math.min(vFOV, hFOV);
    const fovRadians = (effectiveFOV * Math.PI) / 180;
    const distance = (radius * CAMERA_FIT_CONFIG.FIT_OFFSET) / Math.sin(fovRadians / 2);

    // Calculate new camera position (maintain current direction)
    const direction = camera.position.clone().sub(controls.target).normalize();
    const newPosition = center.clone().add(direction.multiplyScalar(distance));

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
  */

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

      // Calculate fit for selected object
      const result = calculateCameraFit(
        camera as THREE.PerspectiveCamera,
        selectedMesh,
        CAMERA_FIT_CONFIG.FIT_OFFSET,
        controls
      );

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
