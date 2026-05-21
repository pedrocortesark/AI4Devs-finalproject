/**
 * T-1005-FRONT: Model Loader Component
 * Loads GLB models from CDN with fallback to BBox wireframe.
 * 
 * Features:
 * - Fetches part detail from GET /api/parts/{id}
 * - Loads GLB using @react-three/drei useGLTF
 * - Fallback to BBoxProxy if low_poly_url IS NULL
 * - Error handling for 404, timeouts, CORS errors
 * - Automatic model centering and scaling
 * - Preloading of adjacent parts for instant navigation
 */

import React, { useEffect, useRef, useState } from 'react';
import { Html } from '@react-three/drei';
import { useLoader } from '@react-three/fiber';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { Group, Box3, Vector3 } from 'three';
import { BBoxProxy } from './Dashboard/BBoxProxy';
import { getPartDetail } from '@/services/upload.service';
import type { PartDetail } from '@/types/parts';
import type { ModelLoaderProps } from './ModelLoader.types';
import { MODEL_LOADER_DEFAULTS, LOADING_MESSAGES } from './ModelLoader.constants';

/**
 * ModelLoader Component
 * Main component that orchestrates model loading and rendering
 */
export const ModelLoader: React.FC<ModelLoaderProps> = ({
  partId,
  enablePreload = MODEL_LOADER_DEFAULTS.ENABLE_PRELOAD,
  // showLoadingSpinner = MODEL_LOADER_DEFAULTS.SHOW_LOADING_SPINNER, // Reserved for future use
  onLoadSuccess,
  onLoadError,
  autoCenter = MODEL_LOADER_DEFAULTS.AUTO_CENTER,
  autoScale = MODEL_LOADER_DEFAULTS.AUTO_SCALE,
  targetSize = MODEL_LOADER_DEFAULTS.TARGET_SIZE,
}) => {
  const [partData, setPartData] = useState<PartDetail | null>(null);
  const [modelLoadedTick, setModelLoadedTick] = useState(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const groupRef = useRef<Group>(null);
  const renderUrl = partData?.high_poly_url || partData?.low_poly_url || null;

  /**
   * Effect 1: Fetch part detail from backend
   */
  useEffect(() => {
    const fetchPartData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const data = await getPartDetail(partId);
        setPartData(data);
        
        // Call success callback
        if (onLoadSuccess) {
          onLoadSuccess(data);
        }
        
        // Preload adjacent parts if enabled
        if (enablePreload && data.low_poly_url) {
          preloadAdjacentModels(partId);
        }
        
      } catch (err) {
        if (process.env.NODE_ENV === 'development') {
          console.error('[ModelLoader] Failed to fetch part data:', err);
        }
        const errorObj = err instanceof Error ? err : new Error('Unknown error');
        setError(errorObj);
        
        // Call error callback
        if (onLoadError) {
          onLoadError(errorObj);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchPartData();
  }, [partId, enablePreload, onLoadSuccess, onLoadError]);

  /**
   * Effect 2: Auto-center and auto-scale model after load
   */
  useEffect(() => {
    if (!groupRef.current || !partData?.low_poly_url || modelLoadedTick === 0) return;

    try {
      const group = groupRef.current;
      // Reset transform before recomputing to avoid accumulating offsets when navigating parts
      group.position.set(0, 0, 0);
      group.scale.set(1, 1, 1);

      const bbox = new Box3().setFromObject(group);
      const size = new Vector3();
      bbox.getSize(size);
      const center = new Vector3();
      bbox.getCenter(center);

      // Center model at origin
      if (autoCenter) {
        group.position.sub(center);
      }

      // Scale model to target size
      if (autoScale) {
        const maxDimension = Math.max(size.x, size.y, size.z);
        if (maxDimension > 0) {
          const scale = (targetSize * 0.85) / maxDimension;
          group.scale.setScalar(scale);
        }
      }
    } catch (err) {
      // In test environments (jsdom), Three.js methods may not be fully available
      // Only log in development mode to avoid noise in production
      if (process.env.NODE_ENV === 'development') {
        console.warn('[ModelLoader] Auto-center/scale skipped (test environment):', err);
      }
    }
  }, [partData, autoCenter, autoScale, targetSize, modelLoadedTick]);

  /**
   * Conditional rendering: error → loading → no URL → GLB
   */

  // Error state: Show BBox + error message
  if (error) {
    return (
      <ErrorFallback
        error={error}
        bbox={partData?.bbox || null}
        isoCode={partData?.iso_code || partId}
      />
    );
  }

  // Loading state: Show spinner
  if (loading || !partData) {
    return <LoadingSpinner message={LOADING_MESSAGES.FETCHING_DATA} />;
  }

  // Case 1: low_poly_url IS NULL → Show BBox wireframe (geometry not processed yet)
  if (!partData.low_poly_url) {
    return (
      <ProcessingFallback
        bbox={partData.bbox}
        isoCode={partData.iso_code}
      />
    );
  }

  // Case 2: low_poly_url exists → Load GLB
  return (
    <group ref={groupRef} data-testid="model-loader" rotation={[-Math.PI / 2, 0, 0]}>
      <OBJModel
        url={renderUrl}
        mtlUrl={partData.mtl_url || null}
        onReady={() => setModelLoadedTick((prev) => prev + 1)}
      />
    </group>
  );
};

/**
 * GLBModel Component
 * Renders 3D model from GLB file using Three.js useGLTF hook from @react-three/drei.
 * The model is loaded asynchronously and cached by useGLTF.
 * 
 * CRITICAL: Error Boundary Protection
 * - useGLTF suspends during loading (handled by parent Suspense boundary)
 * - Throws error BEFORE render if scene is invalid (prevents R3F crash)
 * - NEVER allows undefined to reach <primitive object={...}>
 * - Sanitizes URLs to remove trailing '?' (database bug causing cache issues)
 * 
 * @param url - CDN presigned URL to GLB file (S3 + CloudFront)
 * @returns Three.js primitive object rendered in the scene
 * @throws Error if URL is invalid or scene fails to load
 */
const OBJModel: React.FC<{ url: string; mtlUrl: string | null; onReady?: () => void }> = ({ url, mtlUrl, onReady }) => {
  // Validate URL before attempting load (throw early)
  if (!url || typeof url !== 'string' || url.trim() === '') {
    const msg = `[GLBModel] Invalid URL: ${url}`;
    console.error(msg);
    throw new Error(msg);
  }

  // Remove trailing '?' from URLs (legacy data compatibility)
  const sanitizedUrl = url.replace(/\?$/, '');
  const sanitizedMtlUrl = mtlUrl ? mtlUrl.replace(/\?$/, '') : null;
  const objScene = useLoader(OBJLoader, sanitizedUrl);
  if (!objScene || !objScene.isObject3D) {
    const msg = `[OBJModel] Invalid OBJ scene for URL: ${sanitizedUrl}`;
    console.error(msg, { objScene });
    throw new Error(msg);
  }

  const scene = objScene.clone(true);

  useEffect(() => {
    const normalizeName = (value: string | undefined | null) =>
      (value || '').trim().replace(/^\"|\"$/g, '');

    const applyToMaterial = (mat: any, baseColor: string) => {
      if (mat?.color?.set) {
        mat.color.set(baseColor);
      }
      mat.side = 2;
      mat.needsUpdate = true;
    };

    const applyVisualProps = (child: any, baseColor: string) => {
      if (Array.isArray(child.material)) {
        child.material.forEach((mat: any) => applyToMaterial(mat, baseColor));
      } else if (child.material) {
        applyToMaterial(child.material, baseColor);
      }
      child.castShadow = true;
      child.receiveShadow = true;
      if (child.geometry && !child.geometry.attributes.normal) {
        child.geometry.computeVertexNormals();
      }
    };

    const applyMTLColors = (targetScene: any, colorMap: Record<string, string>) => {
      const neutralGray = '#A0A0A0';
      targetScene.traverse((child: any) => {
        if (!child.isMesh || !child.material) {
          return;
        }
        const meshName = normalizeName(child.name);
        if (Array.isArray(child.material)) {
          child.material.forEach((mat: any) => {
            const matName = normalizeName(mat?.name);
            applyToMaterial(mat, colorMap[matName] || colorMap[meshName] || neutralGray);
          });
          child.castShadow = true;
          child.receiveShadow = true;
          if (child.geometry && !child.geometry.attributes.normal) {
            child.geometry.computeVertexNormals();
          }
        } else {
          const matName = normalizeName(child.material?.name);
          applyVisualProps(child, colorMap[matName] || colorMap[meshName] || neutralGray);
        }
      });
    };

    if (sanitizedMtlUrl) {
      fetch(sanitizedMtlUrl)
        .then((res) => {
          if (!res.ok) {
            throw new Error(`MTL HTTP ${res.status}`);
          }
          return res.text();
        })
        .then((mtlText) => {
          const colorMap: Record<string, string> = {};
          let currentMat = '';
          for (const line of mtlText.split('\n')) {
            const tokens = line.trim().split(/\s+/);
            if (tokens[0] === 'newmtl' && tokens[1]) {
              currentMat = normalizeName(tokens[1]);
            } else if (tokens[0] === 'Kd' && currentMat && tokens.length >= 4) {
              const r = Math.round(parseFloat(tokens[1]) * 255);
              const g = Math.round(parseFloat(tokens[2]) * 255);
              const b = Math.round(parseFloat(tokens[3]) * 255);
              colorMap[currentMat] = `rgb(${r},${g},${b})`;
            }
          }
          applyMTLColors(scene, colorMap);
        })
        .catch((err) => {
          if (process.env.NODE_ENV === 'development') {
            console.warn('[ModelLoader] Failed to apply Kd colors from MTL:', err);
          }
        })
        .finally(() => {
          onReady?.();
        });
      return;
    }

    scene.traverse((child: any) => {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
    onReady?.();
  }, [scene, sanitizedMtlUrl, onReady]);

  return <primitive object={scene} />;
};

/**
 * ProcessingFallback Component
 * Displayed when low_poly_url IS NULL, indicating geometry is still being processed.
 * Shows BBox wireframe (if available) + informative message to user.
 * 
 * @param bbox - Bounding box coordinates (min/max) from database, null if not calculated yet
 * @param isoCode - Part ISO code (e.g., "SF-C12-D-002") for display in message
 * @returns Group with BBoxProxy wireframe + HTML overlay message
 */
const ProcessingFallback: React.FC<{
  bbox: PartDetail['bbox'];
  isoCode: string;
}> = ({ bbox, isoCode }) => {
  return (
    <group data-testid="bbox-proxy">
      {/* BBox wireframe */}
      {bbox && <BBoxProxy bbox={bbox} color="#3B82F6" opacity={0.3} wireframe={true} />}
      
      {/* Info message (HTML overlay) */}
      <Html center>
        <div style={{
          background: 'rgba(255, 255, 255, 0.95)',
          padding: '1rem 1.5rem',
          borderRadius: '8px',
          textAlign: 'center',
          maxWidth: '300px',
        }}>
          <p style={{ margin: 0, fontWeight: 600, color: '#333' }}>
            {LOADING_MESSAGES.PROCESSING_GEOMETRY}
          </p>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.875rem', color: '#666' }}>
            La pieza <strong>{isoCode}</strong> está siendo convertida a formato 3D.
            Intenta nuevamente en unos minutos.
          </p>
        </div>
      </Html>
    </group>
  );
};

/**
 * ErrorFallback Component
 * Displayed when part data fetch fails (404, 403, network errors) or GLB load fails.
 * Shows error message + BBox wireframe if available.
 * 
 * @param error - Error object with descriptive message (e.g., "Pieza no encontrada")
 * @param bbox - Bounding box coordinates (min/max), null if fetch failed before BBox retrieved
 * @param isoCode - Part ISO code or partId fallback for display in error message
 * @returns Group with optional BBoxProxy + HTML overlay error message
 */
const ErrorFallback: React.FC<{
  error: Error;
  bbox: PartDetail['bbox'] | null;
  isoCode: string;
}> = ({ error, bbox, isoCode }) => {
  return (
    <group>
      {/* BBox wireframe if available */}
      {bbox && <BBoxProxy bbox={bbox} color="#DC2626" opacity={0.3} wireframe={true} />}
      
      {/* Error message */}
      <Html center>
        <div style={{
          background: 'rgba(255, 230, 230, 0.95)',
          padding: '1rem 1.5rem',
          borderRadius: '8px',
          textAlign: 'center',
          maxWidth: '300px',
          border: '1px solid rgba(220, 38, 38, 0.3)',
        }}>
          <p style={{ margin: 0, fontWeight: 600, color: '#dc2626' }}>
            Error al cargar modelo
          </p>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.875rem', color: '#666' }}>
            No se pudo cargar la geometría de <strong>{isoCode}</strong>.
          </p>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem', color: '#999' }}>
            {error.message}
          </p>
        </div>
      </Html>
    </group>
  );
};

/**
 * LoadingSpinner Component
 * Displayed while fetching part detail from GET /api/parts/{id}.
 * Shows animated spinner (CSS) + informative message.
 * 
 * @param message - Loading message text (from LOADING_MESSAGES constants)
 * @returns HTML overlay with spinner and message (centered in canvas)
 */
const LoadingSpinner: React.FC<{ message: string }> = ({ message }) => {
  return (
    <Html center>
      <div style={{
        background: 'rgba(255, 255, 255, 0.9)',
        padding: '1rem 2rem',
        borderRadius: '8px',
        textAlign: 'center',
      }}>
        <div className="spinner" />
        <p style={{ margin: '0.5rem 0 0 0', color: '#333' }}>{message}</p>
      </div>
    </Html>
  );
};

/**
 * Preload adjacent models for instant navigation between parts.
 * Fetches prev_id/next_id from T-1003-BACK navigation endpoint,
 * then preloads GLB models using useGLTF.preload() for cache warming.
 * 
 * @param _currentPartId - UUID of currently displayed part (reserved for future use)
 * @returns Promise<void> - Non-blocking, errors are logged but not thrown
 * @internal This function is a stub pending T-1003-BACK integration
 */
const preloadAdjacentModels = async (_currentPartId: string) => {
  try {
    // TODO: Fetch adjacent IDs from T-1003-BACK endpoint
    // const adjacent = await getAdjacentParts(_currentPartId);
    // if (adjacent.prev_id) {
    //   const prevPart = await getPartDetail(adjacent.prev_id);
    //   if (prevPart.low_poly_url) {
    //     useGLTF.preload(prevPart.low_poly_url);
    //   }
    // }
    // if (adjacent.next_id) {
    //   const nextPart = await getPartDetail(adjacent.next_id);
    //   if (nextPart.low_poly_url) {
    //     useGLTF.preload(nextPart.low_poly_url);
    //   }
    // }
  } catch (err) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[ModelLoader] Preload failed:', err);
    }
    // Non-critical error, don't show to user
  }
};

export default ModelLoader;
