/**
 * Camera Animation Hook
 * 
 * Provides smooth camera transitions using GSAP for professional CAD-style animations.
 * Animates both camera position and OrbitControls target simultaneously.
 * 
 * @module useCameraAnimation
 */

import { useRef, useCallback } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import gsap from 'gsap';
import type { OrbitControls } from 'three-stdlib';

/**
 * Animation state for camera transitions
 */
interface AnimationState {
  isAnimating: boolean;
  targetPosition: THREE.Vector3 | null;
  targetLookAt: THREE.Vector3 | null;
  onComplete?: () => void;
}

/**
 * Options for camera animation
 */
export interface CameraAnimationOptions {
  /** Duration in seconds (default: 0.8) */
  duration?: number;
  /** GSAP easing function (default: 'power2.inOut') */
  ease?: string;
  /** Callback when animation completes */
  onComplete?: () => void;
}

/**
 * Hook for animating camera position and target with smooth transitions.
 * 
 * Uses GSAP for professional easing and @react-three/fiber's useFrame
 * for synchronized updates with render loop.
 * 
 * @returns Object with animateTo function and isAnimating state
 * 
 * @example
 * ```tsx
 * function CameraController() {
 *   const { animateTo, isAnimating } = useCameraAnimation();
 *   const controls = useThree(state => state.controls as OrbitControls);
 *   
 *   const handleFocus = () => {
 *     const result = calculateCameraFit(camera, selectedObject, 1.2, controls);
 *     animateTo(result.position, result.target, { duration: 1.0 });
 *   };
 *   
 *   return null;
 * }
 * ```
 */
export function useCameraAnimation() {
  const { camera } = useThree();
  const animationState = useRef<AnimationState>({
    isAnimating: false,
    targetPosition: null,
    targetLookAt: null,
  });

  /**
   * Animate camera to new position and look-at target.
   * 
   * @param newPosition - Target camera position
   * @param newLookAt - Target look-at point (controls.target)
   * @param options - Animation configuration
   */
  const animateTo = useCallback(
    (
      newPosition: THREE.Vector3,
      newLookAt: THREE.Vector3,
      options: CameraAnimationOptions = {}
    ) => {
      const { duration = 0.8, ease = 'power2.inOut', onComplete } = options;

      // Cancel any existing animation
      gsap.killTweensOf(camera.position);
      gsap.killTweensOf(animationState.current);

      // Store state
      animationState.current = {
        isAnimating: true,
        targetPosition: newPosition.clone(),
        targetLookAt: newLookAt.clone(),
        onComplete,
      };

      console.log('🎬 Starting camera animation', {
        from: camera.position.toArray().map(v => v.toFixed(2)),
        to: newPosition.toArray().map(v => v.toFixed(2)),
        lookAt: newLookAt.toArray().map(v => v.toFixed(2)),
        duration,
      });

      // Animate camera position
      gsap.to(camera.position, {
        x: newPosition.x,
        y: newPosition.y,
        z: newPosition.z,
        duration,
        ease,
        onUpdate: () => {
          // Ensure camera looks at target during animation
          if (animationState.current.targetLookAt) {
            camera.lookAt(animationState.current.targetLookAt);
          }
        },
        onComplete: () => {
          animationState.current.isAnimating = false;
          camera.updateProjectionMatrix();
          
          console.log('✅ Camera animation complete', {
            finalPosition: camera.position.toArray().map(v => v.toFixed(2)),
          });

          if (onComplete) {
            onComplete();
          }
        },
      });
    },
    [camera]
  );

  /**
   * Get current animation status
   */
  const isAnimating = animationState.current.isAnimating;

  return {
    animateTo,
    isAnimating,
  };
}

/**
 * Hook for integrating camera animations with OrbitControls.
 * Animates both camera position and controls.target simultaneously.
 * 
 * @param controls - OrbitControls instance (from useThree or ref)
 * 
 * @returns Object with animateTo function and isAnimating state
 * 
 * @example
 * ```tsx
 * function CameraController() {
 *   const controls = useThree(state => state.controls as OrbitControls);
 *   const { animateTo } = useCameraAnimationWithControls(controls);
 *   
 *   const handleFitAll = () => {
 *     const result = fitCameraToScene(camera, scene, 1.2, controls);
 *     if (result) {
 *       animateTo(result.position, result.target);
 *     }
 *   };
 * }
 * ```
 */
export function useCameraAnimationWithControls(controls: OrbitControls | null) {
  const { camera } = useThree();
  const animationState = useRef<AnimationState>({
    isAnimating: false,
    targetPosition: null,
    targetLookAt: null,
  });

  const animateTo = useCallback(
    (
      newPosition: THREE.Vector3,
      newTarget: THREE.Vector3,
      options: CameraAnimationOptions = {}
    ) => {
      if (!controls) {
        console.warn('⚠️ useCameraAnimationWithControls: controls not available');
        return;
      }

      const { duration = 0.8, ease = 'power2.inOut', onComplete } = options;

      // Cancel existing animations
      gsap.killTweensOf(camera.position);
      gsap.killTweensOf(controls.target);

      animationState.current = {
        isAnimating: true,
        targetPosition: newPosition.clone(),
        targetLookAt: newTarget.clone(),
        onComplete,
      };

      console.log('🎬 Starting camera+controls animation', {
        cameraFrom: camera.position.toArray().map(v => v.toFixed(2)),
        cameraTo: newPosition.toArray().map(v => v.toFixed(2)),
        controlsFrom: controls.target.toArray().map(v => v.toFixed(2)),
        controlsTo: newTarget.toArray().map(v => v.toFixed(2)),
        duration,
      });

      // Animate camera position
      gsap.to(camera.position, {
        x: newPosition.x,
        y: newPosition.y,
        z: newPosition.z,
        duration,
        ease,
      });

      // Animate controls target (synchronized)
      gsap.to(controls.target, {
        x: newTarget.x,
        y: newTarget.y,
        z: newTarget.z,
        duration,
        ease,
        onUpdate: () => {
          controls.update();
        },
        onComplete: () => {
          animationState.current.isAnimating = false;
          camera.updateProjectionMatrix();
          controls.update();
          
          console.log('✅ Camera+controls animation complete');

          if (onComplete) {
            onComplete();
          }
        },
      });
    },
    [camera, controls]
  );

  return {
    animateTo,
    isAnimating: animationState.current.isAnimating,
  };
}
