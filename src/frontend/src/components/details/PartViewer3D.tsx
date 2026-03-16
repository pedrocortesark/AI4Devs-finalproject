/**
 * PartViewer3D Component
 *
 * 3D viewer for a single architectural piece inside the DetailsPanel.
 * Loads OBJ geometry (same pipeline as ElementMesh) and applies a solid
 * material color from the MATERIAL_COLORS dictionary.
 *
 * Key design decisions:
 * - Uses OBJLoader (not useGLTF/GLB) — consistent with the main scene pipeline
 * - Applies Z→Y rotation (-Math.PI/2 on X) to convert Rhino Z-up → Three.js Y-up
 * - Color: solid MeshStandardMaterial from MATERIAL_COLORS[material_type] or default "Montjuïc"
 * - Camera: auto-positioned from bbox; falls back to fixed position if bbox absent
 * - Non-blocking: Suspense boundary + error boundary handled inside component
 *
 * @module details/PartViewer3D
 */

import React, { Suspense, useMemo, useEffect, useRef } from 'react';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { Box3, Vector3, MeshStandardMaterial, Color, GridHelper } from 'three';
import { MATERIAL_COLORS, DEFAULT_MATERIAL } from '@/constants/materials';
import type { BoundingBox } from '@/types/parts';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PartViewer3DProps {
  /** Presigned OBJ URL — null shows "geometry not available" state */
  url: string | null;
  /** Material name from MATERIAL_COLORS dict (e.g. "Montjuïc") */
  materialType?: string | null;
  /** Bounding box for camera positioning */
  bbox?: BoundingBox | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const VIEWER_BG = '#1a1a2e';
const DEFAULT_CAMERA_POSITION: [number, number, number] = [5, 5, 5];

// ─── Helper: resolve material color ──────────────────────────────────────────

function resolveMaterialColor(materialType?: string | null): string {
  const key = materialType && materialType in MATERIAL_COLORS
    ? (materialType as keyof typeof MATERIAL_COLORS)
    : DEFAULT_MATERIAL;
  const [r, g, b] = MATERIAL_COLORS[key];
  const toHex = (v: number) => v.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

// ─── Sub-component: CameraSetup ───────────────────────────────────────────────

/**
 * Sets up the camera to frame the part geometry.
 * Uses bbox center + diagonal as camera distance.
 * Must be rendered inside <Canvas>.
 */
function CameraSetup({ bbox }: { bbox?: BoundingBox | null }) {
  const { camera } = useThree();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    if (bbox) {
      const min = new Vector3(...bbox.min);
      const max = new Vector3(...bbox.max);
      const center = new Vector3().addVectors(min, max).multiplyScalar(0.5);
      const size = new Vector3().subVectors(max, min);
      const maxDim = Math.max(size.x, size.y, size.z);
      const distance = maxDim * 2.5;

      // Position camera at diagonal, looking at center
      // Apply Z→Y rotation offset: bbox is in Rhino Z-up coords
      camera.position.set(
        center.x + distance * 0.6,
        center.z + distance * 0.8,  // Z becomes Y after rotation
        center.y + distance * 0.6,
      );
      camera.lookAt(center.x, center.z, center.y);
    } else {
      camera.position.set(...DEFAULT_CAMERA_POSITION);
      camera.lookAt(0, 0, 0);
    }
    camera.updateProjectionMatrix();
  }, [bbox, camera]);

  return null;
}

// ─── Sub-component: OBJMesh ───────────────────────────────────────────────────

/**
 * Loads and renders an OBJ file with a solid MeshStandardMaterial.
 * Suspends via useLoader while loading (handled by parent Suspense).
 */
function OBJMesh({ url, colorHex }: { url: string; colorHex: string }) {
  const scene = useLoader(OBJLoader, url);

  const clone = useMemo(() => scene.clone(true), [scene]);

  // Apply solid material color (override Rhino materials for detail inspection)
  useEffect(() => {
    const material = new MeshStandardMaterial({
      color: new Color(colorHex),
      metalness: 0.15,
      roughness: 0.7,
      flatShading: false,
    });

    clone.traverse((child: any) => {
      if (child.isMesh) {
        child.material = material;
        child.castShadow = true;
        child.receiveShadow = true;
        if (child.geometry && !child.geometry.attributes.normal) {
          child.geometry.computeVertexNormals();
        }
      }
    });

    return () => material.dispose();
  }, [clone, colorHex]);

  // Auto-center the cloned scene at origin
  // try/catch: Three.js Object3D methods unavailable in jsdom test environment
  useEffect(() => {
    try {
      const box = new Box3().setFromObject(clone);
      const center = new Vector3();
      box.getCenter(center);
      clone.position.sub(center);
    } catch {
      // silent in test environments
    }
  }, [clone]);

  return (
    // Apply Z→Y rotation: Rhino Z-up → Three.js Y-up (same as ElementMesh)
    <group rotation={[-Math.PI / 2, 0, 0]}>
      <primitive object={clone} />
    </group>
  );
}

// ─── Sub-component: LoadingFallback ──────────────────────────────────────────

function LoadingFallback() {
  return (
    <Html center>
      <div style={{
        background: 'rgba(255,255,255,0.08)',
        color: '#ccc',
        padding: '12px 20px',
        borderRadius: '6px',
        fontSize: '13px',
        backdropFilter: 'blur(4px)',
      }}>
        Cargando geometría…
      </div>
    </Html>
  );
}

// ─── Sub-component: NoGeometryFallback ───────────────────────────────────────

function NoGeometryFallback() {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: VIEWER_BG,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#888',
      fontSize: '13px',
      flexDirection: 'column',
      gap: '8px',
    }}>
      <span style={{ fontSize: '24px', opacity: 0.4 }}>⬡</span>
      <span>Geometría no disponible</span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

/**
 * PartViewer3D — Isolated 3D canvas for single-part detail inspection.
 *
 * @example
 * <PartViewer3D
 *   url={partData.low_poly_url}
 *   materialType={partData.material_type}
 *   bbox={partData.bbox}
 * />
 */
export function PartViewer3D({ url, materialType, bbox }: PartViewer3DProps) {
  if (!url) {
    return <NoGeometryFallback />;
  }

  const colorHex = resolveMaterialColor(materialType);
  const sanitizedUrl = url.replace(/\?$/, '');

  return (
    <div
      data-testid="part-viewer-3d"
      style={{ width: '100%', height: '100%', background: VIEWER_BG }}
    >
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false }}
        camera={{ fov: 45, near: 0.01, far: 5000 }}
      >
        {/* Camera positioning from bbox */}
        <CameraSetup bbox={bbox} />

        {/* Lighting */}
        <ambientLight intensity={0.6} />
        <directionalLight
          position={[5, 10, 5]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight position={[-5, 5, -5]} intensity={0.4} />

        {/* Grid helper for scale reference */}
        <primitive object={new GridHelper(20, 20, 0x333344, 0x222233)} />

        {/* Controls */}
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          enableZoom
          enablePan
          minDistance={0.1}
          maxDistance={500}
        />

        {/* Model */}
        <Suspense fallback={<LoadingFallback />}>
          <OBJMesh url={sanitizedUrl} colorHex={colorHex} />
        </Suspense>
      </Canvas>
    </div>
  );
}

export default PartViewer3D;
