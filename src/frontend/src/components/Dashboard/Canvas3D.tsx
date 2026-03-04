/**
 * Canvas3D Component
 * T-0504-FRONT: Three.js Canvas wrapper with scene configuration
 * T-0508-FRONT: Selection handlers (ESC key, background click)
 * 
 * Wraps @react-three/fiber Canvas with standardized camera, lights, and controls
 */

import React, { useEffect, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, GizmoHelper, GizmoViewcube, Stats, Bounds } from '@react-three/drei';
import type { Canvas3DProps } from './Dashboard3D.types';
import { 
  CAMERA_CONFIG, 
  GRID_CONFIG, 
  LIGHTING_CONFIG, 
  CONTROLS_CONFIG 
} from './Dashboard3D.constants';
import { usePartsStore } from '@/stores/parts.store';
import { DESELECTION_KEYS } from '@/constants/selection.constants';
import { PartsScene } from './PartsScene';
import { DebugHelpers } from './DebugHelpers';

const Canvas3D: React.FC<Canvas3DProps> = ({ 
  showStats = false, 
  cameraConfig 
}) => {
  const clearSelection = usePartsStore((state: any) => state.clearSelection);
  const parts = usePartsStore((state: any) => state.parts); // reactive: re-renders when parts load
  const getFilteredParts = usePartsStore((state: any) => state.getFilteredParts);
  const filteredParts = useMemo(() => getFilteredParts(), [parts, getFilteredParts]);

  // Merge default config with custom config
  const cameraPosition = cameraConfig?.position || CAMERA_CONFIG.POSITION;
  const cameraFov = cameraConfig?.fov !== undefined ? cameraConfig.fov : CAMERA_CONFIG.FOV;
  const cameraNear = cameraConfig?.near || CAMERA_CONFIG.NEAR;
  const cameraFar = cameraConfig?.far || CAMERA_CONFIG.FAR;

  // T-0508-FRONT: ESC key handler for deselection
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      // Support both 'Escape' and legacy 'Esc' key
      if (event.key === DESELECTION_KEYS.ESCAPE || event.key === DESELECTION_KEYS.ESC) {
        clearSelection();
      }
    };

    window.addEventListener('keydown', handleEscape);

    return () => {
      window.removeEventListener('keydown', handleEscape);
    };
  }, [clearSelection]);

  // T-0508-FRONT: Background click handler for deselection
  const handleBackgroundClick = () => {
    clearSelection();
  };

  return (
    <div
      data-testid="canvas"
      data-camera-position={cameraPosition.join(',')}
      data-camera-fov={String(cameraFov)}
      data-has-grid="true"
      data-grid-size={GRID_CONFIG.SIZE.join('x')}
      data-has-controls="true"
      data-controls-damping={String(CONTROLS_CONFIG.ENABLE_DAMPING)}
      data-shadows="true"
      data-dpr="1,2"
      data-has-lights="true"
      data-ambient-intensity={String(LIGHTING_CONFIG.AMBIENT_INTENSITY)}
      data-directional-intensity={String(LIGHTING_CONFIG.DIRECTIONAL_INTENSITY)}
      data-directional-shadows="true"
      data-has-gizmo="true"
      data-gizmo-alignment="bottom-right"
      data-has-stats={showStats ? 'true' : undefined}
      data-controls-max-polar-angle={String(Math.PI / 2)}
      data-controls-min-distance={String(CONTROLS_CONFIG.MIN_DISTANCE)}
      data-controls-max-distance={String(CONTROLS_CONFIG.MAX_DISTANCE)}
      style={{ width: '100%', height: '100%' }}
    >
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{
          fov: cameraFov,
          position: cameraPosition,
          near: cameraNear,
          far: cameraFar,
        }}
        onPointerMissed={handleBackgroundClick}
      >
        {/* Coordinate System Helper — Shows origin (0,0,0) with RGB axes */}
        <axesHelper args={[100]} /> {/* 100m axes for scale reference */}

        {/* Ambient Light */}
        <ambientLight intensity={LIGHTING_CONFIG.AMBIENT_INTENSITY} />

        {/* Directional Light with Shadows */}
        <directionalLight
          position={LIGHTING_CONFIG.DIRECTIONAL_POSITION as [number, number, number]}
          intensity={LIGHTING_CONFIG.DIRECTIONAL_INTENSITY}
          castShadow
          shadow-mapSize-width={LIGHTING_CONFIG.SHADOW_MAP_SIZE}
          shadow-mapSize-height={LIGHTING_CONFIG.SHADOW_MAP_SIZE}
        />

        {/* Grid */}
        <Grid
          args={GRID_CONFIG.SIZE as [number, number]}
          cellSize={GRID_CONFIG.CELL_SIZE}
          sectionSize={GRID_CONFIG.SECTION_SIZE}
          cellColor={GRID_CONFIG.CELL_COLOR}
          sectionColor={GRID_CONFIG.SECTION_COLOR}
          fadeDistance={GRID_CONFIG.FADE_DISTANCE}
          fadeStrength={GRID_CONFIG.FADE_STRENGTH}
          infiniteGrid
        />

        {/* Orbit Controls — makeDefault registers controls in R3F context so <Bounds> can find them */}
        <OrbitControls
          makeDefault
          enableDamping={CONTROLS_CONFIG.ENABLE_DAMPING}
          dampingFactor={CONTROLS_CONFIG.DAMPING_FACTOR}
          minDistance={CONTROLS_CONFIG.MIN_DISTANCE}
          maxDistance={CONTROLS_CONFIG.MAX_DISTANCE}
          maxPolarAngle={CONTROLS_CONFIG.MAX_POLAR_ANGLE}
        />

        {/* GizmoHelper (bottom-right) */}
        <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
          <GizmoViewcube />
        </GizmoHelper>

        {/* Parts Scene — Bounds auto-fits camera to all visible geometry on load.
             clip is omitted: it sets near/far from scene bounds, which causes NaN
             when parts are still loading (empty scene on first render).
             margin=2.0: adds 200% padding around bounding box for comfortable view */}
        <Bounds fit observe margin={2.0}>
          <PartsScene parts={filteredParts} />
        </Bounds>

        {/* Debug Helpers — Outside Bounds to not interfere with camera fitting */}
        <DebugHelpers parts={filteredParts} enabled={true} />

        {/* Stats Panel (dev only) */}
        {showStats && <Stats />}
      </Canvas>
    </div>
  );
};

export default Canvas3D;
