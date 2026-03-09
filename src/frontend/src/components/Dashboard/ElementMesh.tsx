/**
 * ElementMesh Component
 * 
 * T-0505-FRONT: Individual part mesh rendering
 * T-0506-FRONT: Added filter-based opacity
 * T-0507-FRONT: Added 3-level LOD system
 * US-015: Renamed from PartMesh to ElementMesh (aligns with Element Model migration)
 * 
 * Renders elements at their real building coordinates from Rhino (absolute positioning).
 * GLB geometry includes Z→Y rotation applied during backend export.
 * LOD system: Level 0 (mid-poly <20km) → Level 1 (low-poly 20-50km) → Level 2 (bbox >50km)
 * 
 * @module ElementMesh
 */

import { useState, useEffect, useMemo } from 'react';
import { useGLTF, Html, Detailed } from '@react-three/drei';
import { STATUS_COLORS } from '@/constants/dashboard3d.constants';
import { FILTER_VISUAL_FEEDBACK } from '@/constants/parts.constants';
import { LOD_DISTANCES } from '@/constants/lod.constants';
import { usePartsStore } from '@/stores/parts.store';
import { BBoxProxy } from './BBoxProxy';
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
 * ElementMesh: Renders individual element with GLB geometry and optional LOD
 * 
 * @param props.part - Element data (iso_code, status, low_poly_url, mid_poly_url, bbox, etc.)
 * @param props.position - 3D position [x, y, z]
 * @param props.enableLod - Enable LOD system (default true). Set false for T-0505 backward compatibility
 * 
 * @example
 * ```tsx
 * // With LOD (default)
 * <ElementMesh part={element} position={[10, 0, 5]} />
 * 
 * // Without LOD (backward compatibility)
 * <ElementMesh part={element} position={[10, 0, 5]} enableLod={false} />
 * ```
 */
export function ElementMesh({ part, position, enableLod = true }: ElementMeshProps) {
  const [hovered, setHovered] = useState(false);
  const store = usePartsStore();
  const { selectPart, selectedId } = store;
  const getFilteredParts = store.getFilteredParts || (() => [part]); // Default: no filtering
  const filters = store.filters || { status: [], tipologia: [], workshop_id: null }; // Default: empty filters
  
  const isSelected = selectedId === part.id;
  const filteredParts = getFilteredParts();
  const matchesFilters = filteredParts.some((p: typeof part) => p.id === part.id);
  
  // Check if any filters are applied
  const hasFilterSystem = filters && ('status' in filters || 'tipologia' in filters);
  const hasActiveFilters = hasFilterSystem && (
    (filters.status?.length ?? 0) > 0 || 
    (filters.tipologia?.length ?? 0) > 0 || 
    filters.workshop_id !== null
  );
  
  // Load GLB geometries
  // When enableLod=false: only load low_poly (backward compatibility)
  // When enableLod=true: load both mid_poly (or fallback to low_poly) and low_poly
  // 
  // BUG FIX: Remove trailing '?' from URLs (database has invalid query strings)
  // URLs like "https://...glb?" cause useGLTF cache issues
  const sanitizeUrl = (url: string) => url.replace(/\?$/, '');
  
  const lowPolyUrl = sanitizeUrl(part.low_poly_url!);
  const midPolyUrl = enableLod 
    ? (part.mid_poly_url ? sanitizeUrl(part.mid_poly_url) : lowPolyUrl)
    : lowPolyUrl;

  // useGLTF suspends during loading (handled by parent <Suspense> boundary)
  // IMPORTANT: These hooks always return valid scenes or suspend - no need for null checks
  const { scene: lowPolyScene } = useGLTF(lowPolyUrl);
  const { scene: midPolyScene } = useGLTF(midPolyUrl);

  // Clone scenes so each LOD level owns its own Three.js Object3D.
  // useGLTF returns the same cached object for the same URL; a Three.js
  // object can only have one parent, so sharing the reference across
  // multiple <primitive> elements causes the second to reparent the scene,
  // removing it from the first LOD level.
  // lod2Clone is a third separate clone for LOD level 2 (same reason).
  //
  // GLB geometry is already centred at origin by geometry_processing.py
  // (_extract_and_merge_meshes subtracts the mesh centroid before export).
  // No per-part JavaScript offset calculation is needed.
  const lowPolyClone = useMemo(() => lowPolyScene.clone(true), [lowPolyScene]);
  const midPolyClone = useMemo(() => midPolyScene.clone(true), [midPolyScene]);
  const lod2Clone    = useMemo(() => lowPolyScene.clone(true), [lowPolyScene]);

  // Preload LOD assets on mount for smoother transitions
  useEffect(() => {
    if (enableLod) {
      if (part.mid_poly_url) {
        useGLTF.preload(part.mid_poly_url);
      }
      useGLTF.preload(lowPolyUrl);
    }
  }, [part.mid_poly_url, lowPolyUrl, enableLod]);

  // Handle cursor change on hover
  useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : 'auto';
  }, [hovered]);

  // Handle click
  const handleClick = (e: any) => {
    e.stopPropagation();
    selectPart(part.id);
  };

  // Color values
  const color = STATUS_COLORS[part.status];
  const emissive = isSelected ? color : '#000000';
  const emissiveIntensity = isSelected ? 0.4 : 0;
  
  // Calculate opacity based on selection and filter state
  const opacity = calculatePartOpacity(
    isSelected,
    hasFilterSystem,
    hasActiveFilters,
    matchesFilters
  );

  // Apply material properties to cloned objects
  // Traverse clones and update existing materials (GLTF objects already have materials)
  useEffect(() => {
    [lowPolyClone, midPolyClone, lod2Clone].forEach(clone => {
      clone.traverse((child: any) => {
        if (child.isMesh && child.material) {
          child.material.color.set(color);
          child.material.emissive.set(emissive);
          child.material.emissiveIntensity = emissiveIntensity;
          child.material.opacity = opacity;
          child.material.transparent = true;
          child.material.needsUpdate = true;
        }
      });
    });
  }, [color, emissive, emissiveIntensity, opacity, lowPolyClone, midPolyClone, lod2Clone]);

  // Backward compatibility: Single-level rendering when enableLod=false
  if (!enableLod) {
    return (
      // GLB is positioned at element's real building coordinates (from bbox center).
      // Z→Y rotation already applied during backend GLB export.
      // userData stores partId for camera focus functionality ('F' key)
      <group 
        name={`part-${part.iso_code}`} 
        position={position}
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

  // LOD System: 3-level distance-based rendering
  // Level 0 (<20 km): mid_poly → Level 1 (20–50 km): low_poly → Level 2 (>50 km): BBoxProxy
  return (
    // GLB is positioned at element's real building coordinates (from bbox center).
    // Z→Y rotation already applied during backend GLB export.
    // userData stores partId for camera focus functionality ('F' key)
    <group 
      name={`part-${part.iso_code}`} 
      position={position}
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

      <Detailed distances={[...LOD_DISTANCES]}>
        {/* Level 0: Mid-poly geometry (0-20 km) */}
        <group name="lod-0">
          <primitive
            name={`part-${part.iso_code}`}
            object={midPolyClone}
            onClick={handleClick}
            onPointerOver={() => setHovered(true)}
            onPointerOut={() => setHovered(false)}
          />
        </group>

        {/* Level 1: Low-poly geometry (20-50 km) */}
        <group name="lod-1">
          <primitive
            name={`part-${part.iso_code}`}
            object={lowPolyClone}
            onClick={handleClick}
            onPointerOver={() => setHovered(true)}
            onPointerOut={() => setHovered(false)}
          />
        </group>

        {/* Level 2: BBox proxy (>50 km) or low-poly fallback */}
        <group
          name="lod-2"
          onClick={handleClick}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        >
          {part.bbox ? (
            <BBoxProxy
              bbox={part.bbox}
              color={color}
              opacity={opacity}
              wireframe={true}
            />
          ) : (
            // lod2Clone is a dedicated third clone; lowPolyScene cannot be
            // shared across LOD levels (a THREE.Object3D can only have one parent).
            <primitive
              object={lod2Clone}
            />
          )}
        </group>
      </Detailed>
    </group>
  );
}
