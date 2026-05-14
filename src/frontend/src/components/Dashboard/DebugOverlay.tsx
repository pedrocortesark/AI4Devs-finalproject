/**
 * DebugOverlay Component
 * Visual debugging overlay showing real-time scene information
 */

import { useEffect, useState } from 'react';
import { useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import type { PartCanvasItem } from '@/types/parts';

interface DebugOverlayProps {
  parts: PartCanvasItem[];
}

export function DebugOverlay({ parts }: DebugOverlayProps) {
  const { camera } = useThree();
  const [cameraPos, setCameraPos] = useState<string[]>(['0', '0', '0']);

  useEffect(() => {
    const interval = setInterval(() => {
      setCameraPos([
        camera.position.x.toFixed(2),
        camera.position.y.toFixed(2),
        camera.position.z.toFixed(2),
      ]);
    }, 100);
    return () => clearInterval(interval);
  }, [camera]);

  const partsWithGeometry = parts.filter(p => p.low_poly_url);
  const partsWithBbox = parts.filter(p => p.bbox);

  // Calculate transformed positions for first part
  const firstPart = partsWithBbox[0];
  let transformedPos = null;
  let rhinoPos = null;
  
  if (firstPart?.bbox) {
    const rhinoX = (firstPart.bbox.min[0] + firstPart.bbox.max[0]) / 2;
    const rhinoY = (firstPart.bbox.min[1] + firstPart.bbox.max[1]) / 2;
    const rhinoZ = (firstPart.bbox.min[2] + firstPart.bbox.max[2]) / 2;
    
    rhinoPos = `[${rhinoX.toFixed(2)}, ${rhinoY.toFixed(2)}, ${rhinoZ.toFixed(2)}]`;
    
    const threejsX = rhinoX;
    const threejsY = rhinoZ;
    const threejsZ = -rhinoY;
    
    transformedPos = `[${threejsX.toFixed(2)}, ${threejsY.toFixed(2)}, ${threejsZ.toFixed(2)}]`;
  }

  return (
    <Html
      position={[0, 0, 0]}
      style={{
        position: 'fixed',
        top: '10px',
        right: '10px',
        background: 'rgba(0, 0, 0, 0.9)',
        color: '#00ff00',
        padding: '20px',
        borderRadius: '8px',
        fontFamily: 'monospace',
        fontSize: '14px',
        minWidth: '350px',
        maxWidth: '450px',
        zIndex: 10000,
        pointerEvents: 'none',
      }}
    >
      <div style={{ fontWeight: 'bold', fontSize: '16px', marginBottom: '15px', color: '#ffff00' }}>
        🔧 DEBUG OVERLAY
      </div>
      
      <div style={{ marginBottom: '12px' }}>
        <div style={{ color: '#00ffff' }}>📦 PARTS:</div>
        <div>  Total: {parts.length}</div>
        <div>  With Geometry: {partsWithGeometry.length}</div>
        <div>  With Bbox: {partsWithBbox.length}</div>
      </div>

      <div style={{ marginBottom: '12px' }}>
        <div style={{ color: '#00ffff' }}>📷 CAMERA:</div>
        <div>  Position: [{cameraPos.join(', ')}]</div>
      </div>

      {firstPart && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ color: '#00ffff' }}>🎯 FIRST PART ({firstPart.iso_code}):</div>
          <div>  Rhino (DB): {rhinoPos}</div>
          <div>  Three.js: {transformedPos}</div>
          <div>  Has GLB: {firstPart.low_poly_url ? '✅' : '❌'}</div>
        </div>
      )}

      <div style={{ marginTop: '15px', padding: '10px', background: 'rgba(255, 255, 0, 0.2)', borderRadius: '4px' }}>
        <div style={{ color: '#ffff00', fontWeight: 'bold' }}>⚠️ TROUBLESHOOTING:</div>
        <div style={{ fontSize: '12px', marginTop: '5px' }}>
          {partsWithGeometry.length === 0 && <div>❌ No parts with GLB files</div>}
          {partsWithBbox.length === 0 && <div>❌ No parts with bbox data</div>}
          {partsWithGeometry.length > 0 && partsWithBbox.length > 0 && (
            <div>✅ Data looks OK - check console logs</div>
          )}
        </div>
      </div>
    </Html>
  );
}
