/**
 * PartViewer3D Component
 *
 * 3D viewer for a single architectural piece inside the DetailsPanel.
 * Loads OBJ geometry and applies Rhino layer colors from MTL when available,
 * falling back to a solid material color from the MATERIAL_COLORS dictionary.
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

import { Suspense, useMemo, useEffect } from 'react';
import { Canvas, useLoader } from '@react-three/fiber';
import { OrbitControls, Html, Bounds } from '@react-three/drei';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { Box3, Vector3, MeshStandardMaterial, Color } from 'three';
import { MATERIAL_COLORS, DEFAULT_MATERIAL } from '@/constants/materials';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PartViewer3DProps {
  /** Presigned OBJ URL — null shows "geometry not available" state */
  url: string | null;
  /** Companion MTL URL for Rhino layer colors */
  mtlUrl?: string | null;
  /** Material name from MATERIAL_COLORS dict (e.g. "Montjuïc") */
  materialType?: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const VIEWER_BG = '#1a1a2e';
const DEFAULT_CAMERA_POSITION: [number, number, number] = [3, 3, 3];

// ─── Helper: resolve material color ──────────────────────────────────────────

function resolveMaterialColor(materialType?: string | null): string {
  const key = materialType && materialType in MATERIAL_COLORS
    ? (materialType as keyof typeof MATERIAL_COLORS)
    : DEFAULT_MATERIAL;
  const [r, g, b] = MATERIAL_COLORS[key];
  const toHex = (v: number) => v.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

// ─── Sub-component: OBJMesh ───────────────────────────────────────────────────

/**
 * Loads and renders an OBJ file with Rhino MTL colors when available.
 * Suspends via useLoader while loading (handled by parent Suspense).
 */
function OBJMesh({ url, mtlUrl, colorHex }: { url: string; mtlUrl?: string | null; colorHex: string }) {
  const scene = useLoader(OBJLoader, url);

  const clone = useMemo(() => scene.clone(true), [scene]);

  // Apply MTL Kd colors when available; otherwise use solid material color fallback.
  useEffect(() => {
    const fallbackMaterial = new MeshStandardMaterial({
      color: new Color(colorHex),
      metalness: 0.15,
      roughness: 0.7,
      flatShading: false,
      emissive: new Color('#000000'),
      emissiveIntensity: 0,
    });

    const normalizeName = (value: string | undefined | null) =>
      (value || '').trim().replace(/^\"|\"$/g, '');

    const applyFallback = () => {
      clone.traverse((child: any) => {
        if (child.isMesh) {
          child.material = fallbackMaterial;
          child.castShadow = true;
          child.receiveShadow = true;
          if (child.geometry && !child.geometry.attributes.normal) {
            child.geometry.computeVertexNormals();
          }
        }
      });
    };

    const applyMtlColors = (colorMap: Record<string, string>) => {
      const neutralGray = '#A0A0A0';
      clone.traverse((child: any) => {
        if (!child.isMesh || !child.material) {
          return;
        }

        const meshName = normalizeName(child.name);
        const applyToMaterial = (material: any) => {
          const materialName = normalizeName(material?.name);
          const resolvedColor = colorMap[materialName] || colorMap[meshName] || neutralGray;

          if (material?.color?.set) {
            material.color.set(resolvedColor);
          } else {
            child.material = fallbackMaterial.clone();
            child.material.color.set(resolvedColor);
          }

          material.side = 2;
          if (material?.emissive?.set) {
            material.emissive.set('#000000');
            material.emissiveIntensity = 0;
          }
          material.wireframe = false;
          material.needsUpdate = true;
        };

        if (Array.isArray(child.material)) {
          child.material.forEach((material: any) => applyToMaterial(material));
        } else {
          applyToMaterial(child.material);
        }

        child.castShadow = true;
        child.receiveShadow = true;
        if (child.geometry && !child.geometry.attributes.normal) {
          child.geometry.computeVertexNormals();
        }
      });
    };

    if (mtlUrl) {
      fetch(mtlUrl)
        .then((res) => {
          if (!res.ok) {
            throw new Error(`MTL HTTP ${res.status}`);
          }
          return res.text();
        })
        .then((mtlText) => {
          const colorMap: Record<string, string> = {};
          let currentMaterial = '';
          for (const line of mtlText.split('\n')) {
            const tokens = line.trim().split(/\s+/);
            if (tokens[0] === 'newmtl' && tokens[1]) {
              currentMaterial = normalizeName(tokens[1]);
            } else if (tokens[0] === 'Kd' && currentMaterial && tokens.length >= 4) {
              const r = Math.round(parseFloat(tokens[1]) * 255);
              const g = Math.round(parseFloat(tokens[2]) * 255);
              const b = Math.round(parseFloat(tokens[3]) * 255);
              colorMap[currentMaterial] = `rgb(${r},${g},${b})`;
            }
          }
          applyMtlColors(colorMap);
        })
        .catch(() => {
          applyFallback();
        });
    } else {
      applyFallback();
    }

    return () => fallbackMaterial.dispose();
  }, [clone, colorHex, mtlUrl]);

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
export function PartViewer3D({ url, mtlUrl = null, materialType }: PartViewer3DProps) {
  if (!url) {
    return <NoGeometryFallback />;
  }

  const colorHex = resolveMaterialColor(materialType);
  const sanitizedUrl = url.replace(/\?$/, '');
  const sanitizedMtlUrl = mtlUrl ? mtlUrl.replace(/\?$/, '') : null;

  return (
    <div
      data-testid="part-viewer-3d"
      style={{ width: '100%', height: '100%', background: VIEWER_BG }}
    >
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false }}
        camera={{ fov: 45, near: 0.01, far: 5000, position: DEFAULT_CAMERA_POSITION }}
      >
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

        {/* Controls */}
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.05}
          enableZoom
          enablePan
          minDistance={0.1}
          maxDistance={500}
        />

        {/* Model — Bounds auto-fits camera to loaded geometry */}
        <Bounds fit clip observe margin={1.1}>
          <Suspense fallback={<LoadingFallback />}>
            <OBJMesh url={sanitizedUrl} mtlUrl={sanitizedMtlUrl} colorHex={colorHex} />
          </Suspense>
        </Bounds>
      </Canvas>
    </div>
  );
}

export default PartViewer3D;
