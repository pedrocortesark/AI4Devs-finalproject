/**
 * ElementMesh Component
 * 
 * T-0505-FRONT: Individual part mesh rendering
 * T-0506-FRONT: Added filter-based opacity
 * T-0507-FRONT: Added 3-level LOD system
 * US-015: Complete 4-level LOD system (high/mid/low/bbox)
 * 
 * RECENT CHANGES (2026-03-13):
 * - Switched from GLB to OBJ format (trimesh GLB export has persistent bugs in v4.0.5 & 4.11.3)
 * - Replaced drei's <Detailed> component with custom useLOD hook (Detailed incompatible with OBJ geometry)
 * - OBJ files preserve absolute Rhino Z-up coordinates from backend (no centering)
 * - Frontend applies Z→Y rotation via group rotation prop
 * 
 * Renders elements at their real building coordinates from Rhino (absolute positioning).
 * LOD system: 
 *   - Level 0 (0-5m): high-poly ~7k tris, maximum detail for close inspection
 *   - Level 1 (5-20m): mid-poly ~2k tris, normal working distance
 *   - Level 2 (20-50m): low-poly ~500 tris, overview mode
 *   - Level 3 (>50m): bbox 12 tris, wireframe proxy for distant view
 * 
 * @module ElementMesh
 */

import { useState, useEffect, useMemo } from 'react';
import { useLoader } from '@react-three/fiber';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { Html } from '@react-three/drei';
import { STATUS_COLORS } from '@/constants/dashboard3d.constants';
import { FILTER_VISUAL_FEEDBACK } from '@/constants/parts.constants';
import { MATERIAL_COLORS, DEFAULT_MATERIAL, getMaterialColorHex } from '@/constants/materials';
import { usePartsStore } from '@/stores/parts.store';
import { useLOD } from '@/hooks/useLOD';
import { BBoxProxy } from './BBoxProxy';
// import { WireframeHelper } from './WireframeHelper'; // DISABLED
import type { ElementMeshProps } from './PartsScene.types';

/**
 * Tooltip styles for element information display
 * Extracted as constant for consistency and maintainability
 */
const TOOLTIP_STYLES: React.CSSProperties = {
  background: 'rgba(0, 0, 0, 0.8)',
  color: 'white',
  padding: '8px 12px',
  borderRadius: '4px',
  fontSize: '12px',
  whiteSpace: 'nowrap',
};

/**
 * Calculate opacity value based on selection and filter state
 * 
 * Opacity rules:
 * 1. Selected element: always fully visible (1.0)
 * 2. No filters applied: all elements fully visible (1.0)
 * 3. Filters applied + matches: fully visible (1.0)
 * 4. Filters applied + no match: faded out (0.2)
 * 5. Backward compatibility: legacy tests without filter system (0.8)
 * 
 * @param isSelected - Whether element is currently selected
 * @param hasFilterSystem - Whether filters object has status/tipologia properties
 * @param hasActiveFilters - Whether any filter is currently applied
 * @param matchesFilters - Whether element matches current filter criteria
 * @returns Opacity value as number (0.2, 0.8, or 1.0)
 */
function calculatePartOpacity(
  isSelected: boolean,
  hasFilterSystem: boolean,
  hasActiveFilters: boolean,
  matchesFilters: boolean
): number {
  // Selected parts always fully visible
  if (isSelected) {
    return 1.0;
  }
  
  // Filter-based opacity (T-0506)
  if (hasFilterSystem) {
    if (!hasActiveFilters) {
      // No filters applied: all parts fully visible
      return FILTER_VISUAL_FEEDBACK.MATCH_OPACITY;
    } else if (matchesFilters) {
      // Filters applied and part matches
      return FILTER_VISUAL_FEEDBACK.MATCH_OPACITY;
    } else {
      // Filters applied and part doesn't match
      return FILTER_VISUAL_FEEDBACK.NON_MATCH_OPACITY;
    }
  }
  
  // Backward compatibility for T-0505 tests (no filter system)
  return 0.8;
}

/**
 * ElementMesh: Renders individual element with OBJ geometry and LOD system
 * 
 * OBJ files contain ABSOLUTE Rhino coordinates (Z-up) exported by geometry_processing.py.
 * Frontend applies Z→Y rotation to align with Three.js coordinate system.
 * Custom useLOD hook calculates camera distance for LOD level switching.
 * 
 * @param props.part - Element data (iso_code, status, low_poly_url, mid_poly_url, bbox, etc.)
 * @param props.position - 3D position [x, y, z] calculated from bbox center (used for LOD distance)
 * @param props.enableLod - Enable LOD system (default true). Set false for T-0505 backward compatibility
 * 
 * @example
 * ```tsx
 * // With LOD (default)
 * <ElementMesh part={element} position={[10, 20, 30]} />
 * 
 * // Without LOD (backward compatibility)
 * <ElementMesh part={element} position={[10, 20, 30]} enableLod={false} />
 * ```
 */
export function ElementMesh({ part, position, enableLod = true }: ElementMeshProps) {
  const [hovered, setHovered] = useState(false);
  
  // Debug logging - DISABLED (too noisy with React StrictMode)
  // console.log(`🎨 ElementMesh: Rendering ${part.iso_code} at [${position.join(', ')}], LOD: ${enableLod}`);
  
  const store = usePartsStore();
  const { selectPart, selectedId } = store;
  const getFilteredParts = store.getFilteredParts || (() => [part]); // Default: no filtering
  const filters = store.filters || { status: [], tipologia: [], workshop_id: null }; // Default: empty filters
  const colorMode = usePartsStore((state) => state.colorMode);
  
  const isSelected = selectedId === part.id;
  const filteredParts = getFilteredParts();
  const matchesFilters = filteredParts.some((p: typeof part) => p.id === part.id);
  
  // Check if any filters are applied
  const hasFilterSystem = filters && ('material' in filters || 'agrupacio' in filters);
  const hasActiveFilters = hasFilterSystem && (
    (filters.material?.length ?? 0) > 0 ||
    (filters.agrupacio?.length ?? 0) > 0 ||
    filters.workshop_id !== null
  );
  
  // Load OBJ geometries for complete LOD system (US-015: 4 levels)
  // Level 0 (0-5m): high_poly (~7k tris, max detail)
  // Level 1 (5-20m): mid_poly (~2k tris, normal working distance)
  // Level 2 (20-50m): low_poly (~500 tris, overview)
  // Level 3 (>50m): bbox (12 tris, wireframe proxy)
  // 
  // Fallback strategy if LOD assets missing:
  // - high_poly missing → use mid_poly
  // - mid_poly missing → use low_poly
  // - low_poly missing → component will error (low_poly_url required field)
  // 
  // BUG FIX: Sanitize URLs to remove trailing '?' (legacy compatibility)
  // Backend now strips '?' during export, but old URLs may still have it
  const sanitizeUrl = (url: string) => url.replace(/\?$/, '');
  
  // Required URLs
  const lowPolyUrl = sanitizeUrl(part.low_poly_url!);
  
  // Optional LOD URLs with fallback chain
  const midPolyUrl = part.mid_poly_url 
    ? sanitizeUrl(part.mid_poly_url) 
    : lowPolyUrl; // Fallback: use low_poly if mid missing
    
  const highPolyUrl = part.high_poly_url
    ? sanitizeUrl(part.high_poly_url)
    : midPolyUrl; // Fallback: use mid_poly (or its fallback) if high missing

  // MTL for per-face Rhino layer colors (only for high-poly, only when colorMode='layer')
  const mtlUrl = (colorMode === 'layer' && part.mtl_url)
    ? sanitizeUrl(part.mtl_url)
    : null;

  // useLoader suspends during loading (handled by parent <Suspense> boundary)
  // IMPORTANT: These hooks always return valid scenes or suspend - no need for null checks
  // OBJ format used instead of GLB due to trimesh GLB export bugs (versions 4.0.5, 4.11.3)
  const lowPolyScene = useLoader(OBJLoader, lowPolyUrl);
  const midPolyScene = useLoader(OBJLoader, midPolyUrl);
  const highPolyScene = useLoader(OBJLoader, highPolyUrl);

  // Clone scenes so each LOD level owns its own Three.js Object3D.
  // useLoader returns the same cached object for the same URL; a Three.js
  // object can only have one parent, so sharing the reference across
  // multiple <primitive> elements causes the second to reparent the scene,
  // removing it from the first LOD level.
  //
  // OBJ geometry preserves Rhino Z-up absolute coordinates from backend.
  // Frontend applies Z→Y rotation via group rotation prop.
  const lowPolyClone = useMemo(() => lowPolyScene.clone(true), [lowPolyScene]);
  const midPolyClone = useMemo(() => midPolyScene.clone(true), [midPolyScene]);
  const highPolyClone = useMemo(() => highPolyScene.clone(true), [highPolyScene]);
  
  // Calculate LOD level based on camera distance (replaces drei's <Detailed>)
  // position prop is bbox center in Three.js Y-up coordinates (from usePartsSpatialLayout)
  const lodLevel = useLOD(position);

  // Handle cursor change on hover
  useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : 'auto';
  }, [hovered]);

  // Handle click
  const handleClick = (e: any) => {
    e.stopPropagation();
    selectPart(part.id);
  };

  // Stone material color: derived from part.tipologia (material_type from Rhino metadata)
  // OBJ files do NOT carry Rhino layer colors — OBJLoader assigns default gray.
  // We apply the stone color explicitly from MATERIAL_COLORS (62 types).
  const stoneMaterial = (part.tipologia in MATERIAL_COLORS
    ? part.tipologia
    : DEFAULT_MATERIAL) as keyof typeof MATERIAL_COLORS;
  const stoneColor = getMaterialColorHex(stoneMaterial);

  // Status color: used only for selection/hover emissive feedback
  const statusColor = STATUS_COLORS[part.status];
  const emissive = isSelected ? statusColor : '#000000';
  const emissiveIntensity = isSelected ? 0.4 : 0;
  
  // Calculate opacity based on selection and filter state
  const opacity = calculatePartOpacity(
    isSelected,
    hasFilterSystem,
    hasActiveFilters,
    matchesFilters
  );

  // Apply material properties to all LOD clones (high, mid, low)
  // Two modes:
  //   'material' — uniform stone color from MATERIAL_COLORS[tipologia] (default, always works)
  //   'layer'    — per-material-group colors from Rhino layer MTL file (high-poly only)
  //                mid/low always use stoneColor as fallback (decimation destroys face groups)
  useEffect(() => {
    // Helper: apply visual props to a single Three.js material object
    const applyToMaterial = (mat: any, baseColor: string) => {
      mat.color.set(baseColor);
      mat.emissive.set(emissive);
      mat.emissiveIntensity = emissiveIntensity;
      mat.opacity = opacity;
      mat.transparent = opacity < 1.0;
      mat.flatShading = false;
      mat.side = 2; // DoubleSide
      mat.needsUpdate = true;
    };

    // Helper: apply shared visual properties to a mesh — handles both single
    // material and multi-material arrays (OBJLoader with multiple usemtl groups
    // may produce either depending on OBJ structure).
    const applyVisualProps = (child: any, baseColor: string) => {
      if (Array.isArray(child.material)) {
        child.material.forEach((mat: any) => applyToMaterial(mat, baseColor));
      } else {
        applyToMaterial(child.material, baseColor);
      }
      child.castShadow = true;
      child.receiveShadow = true;
      if (child.geometry && !child.geometry.attributes.normal) {
        child.geometry.computeVertexNormals();
      }
    };

    // Mid and low always use stone color (material mode AND textura mode)
    [midPolyClone, lowPolyClone].forEach((clone) => {
      clone.traverse((child: any) => {
        if (child.isMesh && child.material) applyVisualProps(child, stoneColor);
      });
    });

    if (colorMode === 'layer' && mtlUrl) {
      // Textura mode: fetch MTL and apply per-layer Rhino colors to high-poly only
      fetch(mtlUrl)
        .then((res) => res.text())
        .then((mtlText) => {
          // Parse MTL: extract newmtl → Kd color mapping
          const colorMap: Record<string, string> = {};
          let currentMat = '';
          for (const line of mtlText.split('\n')) {
            const tokens = line.trim().split(/\s+/);
            if (tokens[0] === 'newmtl' && tokens[1]) {
              currentMat = tokens[1];
            } else if (tokens[0] === 'Kd' && currentMat && tokens.length >= 4) {
              const r = Math.round(parseFloat(tokens[1]) * 255);
              const g = Math.round(parseFloat(tokens[2]) * 255);
              const b = Math.round(parseFloat(tokens[3]) * 255);
              colorMap[currentMat] = `rgb(${r},${g},${b})`;
            }
          }
          // High-poly: per-material-group colors from MTL (layer_N → Kd color)
          highPolyClone.traverse((child: any) => {
            if (child.isMesh && child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat: any) => {
                  applyToMaterial(mat, colorMap[mat.name ?? ''] ?? stoneColor);
                });
                child.castShadow = true;
                child.receiveShadow = true;
                if (child.geometry && !child.geometry.attributes.normal) {
                  child.geometry.computeVertexNormals();
                }
              } else {
                applyVisualProps(child, colorMap[child.material.name ?? ''] ?? stoneColor);
              }
            }
          });
        })
        .catch(() => {
          // Fetch error fallback: stone color on high-poly too
          highPolyClone.traverse((child: any) => {
            if (child.isMesh && child.material) applyVisualProps(child, stoneColor);
          });
        });
    } else {
      // Material mode: stone color on high-poly (mid/low already set above)
      highPolyClone.traverse((child: any) => {
        if (child.isMesh && child.material) applyVisualProps(child, stoneColor);
      });
    }
  }, [colorMode, mtlUrl, stoneColor, emissive, emissiveIntensity, opacity, highPolyClone, midPolyClone, lowPolyClone]);

  // Backward compatibility: Single-level rendering when enableLod=false
  if (!enableLod) {
    return (
      // OBJ geometry contains ABSOLUTE RHINO COORDINATES in Z-up coordinate system.
      // Apply Z→Y rotation (Rhino → Three.js) and render at absolute building locations.
      // userData stores partId for camera focus functionality ('F' key)
      <group 
        name={`part-${part.iso_code}`}
        position={[0, 0, 0]}
        rotation={[-Math.PI / 2, 0, 0]} // Rotate -90° on X axis: Z-up → Y-up
        userData={{ partId: part.id }}
      >
        <primitive
          object={lowPolyClone}
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        />

        {/* Tooltip on hover or selection */}
        {(hovered || isSelected) && (
          <Html>
            <div style={TOOLTIP_STYLES}>
              <div>{part.iso_code}</div>
              <div>{part.tipologia}</div>
              {part.workshop_name && <div>{part.workshop_name}</div>}
            </div>
          </Html>
        )}
      </group>
    );
  }

  // US-015: Complete 4-level LOD System
  // Level 0 (0-5m): high_poly (~7k tris, max detail for close inspection)
  // Level 1 (5-20m): mid_poly (~2k tris, normal working distance)
  // Level 2 (20-50m): low_poly (~500 tris, overview mode)
  // Level 3 (>50m): bbox (12 tris, wireframe proxy for distant view)
  
  return (
    // OBJ geometry contains ABSOLUTE RHINO COORDINATES in Z-up coordinate system.
    // Apply Z→Y rotation (Rhino → Three.js) and render at absolute building locations.
    // Custom LOD system: useLOD calculates distance from camera to bbox center.
    // userData stores partId for camera focus functionality ('F' key)
    <group 
      name={`part-${part.iso_code}`}
      position={[0, 0, 0]}
      rotation={[-Math.PI / 2, 0, 0]} // Rotate -90° on X axis: Z-up → Y-up
      userData={{ partId: part.id }}
    >
      {/* Tooltip on hover or selection (shared across all LOD levels) */}
      {(hovered || isSelected) && (
        <Html>
          <div style={TOOLTIP_STYLES}>
            <div>{part.iso_code}</div>
            <div>{part.tipologia}</div>
            {part.workshop_name && <div>{part.workshop_name}</div>}
          </div>
        </Html>
      )}

      {/* LOD Level 0: High-poly geometry (0-5m) */}
      {lodLevel === 0 && (
        <primitive
          name={`part-${part.iso_code}-high`}
          object={highPolyClone}
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
          castShadow
          receiveShadow
        />
      )}

      {/* LOD Level 1: Mid-poly geometry (5-20m) */}
      {lodLevel === 1 && (
        <primitive
          name={`part-${part.iso_code}-mid`}
          object={midPolyClone}
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
          castShadow
          receiveShadow
        />
      )}

      {/* LOD Level 2: Low-poly geometry (20-50m) */}
      {lodLevel === 2 && (
        <primitive
          name={`part-${part.iso_code}-low`}
          object={lowPolyClone}
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        />
      )}

      {/* LOD Level 3: BBox proxy (>50m) - Wireframe for distant view */}
      {lodLevel === 3 && (
        <group
          name="lod-3-bbox"
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        >
          {part.bbox ? (
            <BBoxProxy
              bbox={part.bbox!}
              color={stoneColor}
              opacity={opacity}
              wireframe={true}
            />
          ) : (
            // Fallback: use low-poly geometry if bbox missing
            <primitive object={lowPolyClone} />
          )}
        </group>
      )}
    </group>
  );
}
