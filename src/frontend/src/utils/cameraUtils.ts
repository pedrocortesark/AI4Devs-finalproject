/**
 * Camera Utilities for Three.js
 * 
 * Professional CAD-style camera controls with proper trigonometric calculations.
 * Handles objects in any coordinate space (including negative extremes).
 * 
 * @module cameraUtils
 */

import * as THREE from 'three';
import type { OrbitControls } from 'three-stdlib';

/**
 * Configuration for camera fitting
 */
export interface FitCameraOptions {
  /** Offset multiplier for bounding sphere (1.2 = 20% margin) */
  offset?: number;
  /** Duration of animation in seconds (0 = instant) */
  animationDuration?: number;
  /** Callback when animation completes */
  onComplete?: () => void;
}

/**
 * Result of camera fitting calculation
 */
export interface CameraFitResult {
  /** New camera position */
  position: THREE.Vector3;
  /** New controls target (center of object) */
  target: THREE.Vector3;
  /** Distance from camera to target */
  distance: number;
  /** Radius of bounding sphere */
  radius: number;
  /** Size of bounding box */
  size: THREE.Vector3;
}

/**
 * Calculate optimal camera position to frame an object or group of objects.
 * 
 * Uses Box3 for precise bounding box calculation and trigonometry based on
 * camera FOV and aspect ratio. Works correctly with objects at any coordinates
 * (positive, negative, or mixed).
 * 
 * @param camera - PerspectiveCamera instance
 * @param object - Object3D or Group to frame (or array of objects)
 * @param offset - Multiplier for distance (default 1.2 = 20% margin)
 * @param controls - Optional OrbitControls to update target
 * 
 * @returns Camera fit result with position, target, and metadata
 * 
 * @example
 * ```typescript
 * const result = calculateCameraFit(camera, scene, 1.3, controls);
 * camera.position.copy(result.position);
 * camera.lookAt(result.target);
 * controls.target.copy(result.target);
 * controls.update();
 * ```
 */
export function calculateCameraFit(
  camera: THREE.PerspectiveCamera,
  object: THREE.Object3D | THREE.Object3D[],
  offset: number = 1.2,
  controls?: OrbitControls
): CameraFitResult {
  // Create bounding box in world space
  const box = new THREE.Box3();
  
  if (Array.isArray(object)) {
    // Multiple objects - expand box for each
    object.forEach(obj => {
      obj.updateMatrixWorld(true);
      box.expandByObject(obj);
    });
  } else {
    // Single object - ensure matrix is updated
    object.updateMatrixWorld(true);
    box.setFromObject(object);
  }

  // Get box center and size (already in world coordinates)
  const center = new THREE.Vector3();
  box.getCenter(center);
  
  const size = new THREE.Vector3();
  box.getSize(size);

  // Debug logging with explicit string formatting
  console.log('📦 calculateCameraFit debug:');
  console.log(`   boxMin: [${box.min.x.toFixed(2)}, ${box.min.y.toFixed(2)}, ${box.min.z.toFixed(2)}]`);
  console.log(`   boxMax: [${box.max.x.toFixed(2)}, ${box.max.y.toFixed(2)}, ${box.max.z.toFixed(2)}]`);
  console.log(`   center: [${center.x.toFixed(2)}, ${center.y.toFixed(2)}, ${center.z.toFixed(2)}]`);
  console.log(`   size: [${size.x.toFixed(3)}, ${size.y.toFixed(3)}, ${size.z.toFixed(3)}]`);

  // Calculate bounding sphere radius (half of diagonal)
  const radius = size.length() / 2;

  // Apply safety check for empty scenes
  if (radius === 0 || !isFinite(radius)) {
    console.warn('⚠️ calculateCameraFit: Object has zero size or invalid bounds');
    return {
      position: camera.position.clone(),
      target: center,
      distance: 0,
      radius: 0,
      size,
    };
  }

  // Calculate effective FOV considering aspect ratio
  // For landscape viewports, horizontal FOV is limiting factor
  const vFOV = camera.fov;
  const hFOV = vFOV * camera.aspect;
  const effectiveFOV = Math.min(vFOV, hFOV);
  
  // Convert to radians
  const fovRadians = (effectiveFOV * Math.PI) / 180;
  
  // Calculate distance using trigonometry: distance = radius / sin(FOV/2)
  // This ensures the bounding sphere fits exactly in the viewport
  const distance = (radius * offset) / Math.sin(fovRadians / 2);

  // Get current camera direction (or use default if controls not available)
  let direction: THREE.Vector3;
  
  if (controls) {
    // Use current camera direction relative to controls target
    direction = camera.position.clone().sub(controls.target).normalize();
  } else {
    // Default: diagonal view (similar to Rhino "Perspective" view)
    direction = new THREE.Vector3(1, 1, 1).normalize();
  }

  // Calculate new camera position: center + (direction * distance)
  const newPosition = center.clone().add(direction.multiplyScalar(distance));

  return {
    position: newPosition,
    target: center,
    distance,
    radius,
    size,
  };
}

/**
 * Immediately position camera to frame object (no animation).
 * Updates camera position, lookAt, and controls target synchronously.
 * 
 * @param camera - PerspectiveCamera to reposition
 * @param object - Object3D or array of objects to frame
 * @param offset - Distance multiplier (default 1.2)
 * @param controls - OrbitControls to update (required for proper pivot)
 * 
 * @example
 * ```typescript
 * fitCameraToObject(camera, partsGroup, 1.3, controls);
 * ```
 */
export function fitCameraToObject(
  camera: THREE.PerspectiveCamera,
  object: THREE.Object3D | THREE.Object3D[],
  offset: number = 1.2,
  controls?: OrbitControls
): void {
  const result = calculateCameraFit(camera, object, offset, controls);

  // Apply immediately
  camera.position.copy(result.position);
  camera.lookAt(result.target);
  camera.updateProjectionMatrix();

  // Update controls target (CRITICAL for correct rotation pivot)
  if (controls) {
    controls.target.copy(result.target);
    controls.update();
  }

  console.log('📷 Camera fitted to object', {
    target: result.target.toArray().map(v => v.toFixed(2)),
    position: result.position.toArray().map(v => v.toFixed(2)),
    distance: result.distance.toFixed(3),
    radius: result.radius.toFixed(3),
    size: result.size.toArray().map(v => v.toFixed(3)),
  });
}

/**
 * Calculate camera position for "Fit All" - frames all objects in scene.
 * Filters out helpers, lights, and other non-mesh objects.
 * 
 * @param camera - PerspectiveCamera
 * @param scene - Scene or Group containing objects
 * @param offset - Distance multiplier
 * @param controls - OrbitControls
 * 
 * @returns Camera fit result, or null if no valid objects found
 */
export function fitCameraToScene(
  camera: THREE.PerspectiveCamera,
  scene: THREE.Scene | THREE.Group,
  offset: number = 1.2,
  controls?: OrbitControls
): CameraFitResult | null {
  // Find all meshes in scene (exclude helpers, lights, cameras)
  const meshes: THREE.Object3D[] = [];
  
  scene.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.Group) {
      // Exclude helpers (AxesHelper, GridHelper, etc.)
      if (!child.name.includes('helper') && !child.name.includes('Helper')) {
        meshes.push(child);
      }
    }
  });

  if (meshes.length === 0) {
    console.warn('⚠️ fitCameraToScene: No meshes found in scene');
    return null;
  }

  return calculateCameraFit(camera, meshes, offset, controls);
}

/**
 * Calculate "look-at" direction maintaining current camera angle.
 * Useful for smooth panning while preserving viewing angle.
 * 
 * @param camera - Current camera
 * @param newTarget - New target point to look at
 * @param distance - Distance to maintain from target
 * 
 * @returns New camera position
 */
export function calculateCameraOrbit(
  camera: THREE.PerspectiveCamera,
  newTarget: THREE.Vector3,
  distance: number
): THREE.Vector3 {
  // Get current camera direction
  const direction = new THREE.Vector3();
  camera.getWorldDirection(direction);
  
  // Invert direction and scale by distance
  direction.multiplyScalar(-distance);
  
  // New position = target + (direction * distance)
  return newTarget.clone().add(direction);
}
