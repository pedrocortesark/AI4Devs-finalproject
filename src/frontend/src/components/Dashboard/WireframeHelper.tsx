/**
 * WireframeHelper - Renders wireframe overlay for better geometry visualization
 */

import { useMemo } from 'react';
import * as THREE from 'three';

interface WireframeHelperProps {
  mesh: THREE.Object3D;
  color?: string;
  lineWidth?: number;
}

/**
 * Creates a wireframe representation of a mesh for debugging/visualization
 * More visible than material.wireframe = true
 */
export function WireframeHelper({ mesh, color = '#ff0000', lineWidth = 1 }: WireframeHelperProps) {
  const wireframes = useMemo(() => {
    const wires: JSX.Element[] = [];
    let wireIndex = 0;
    
    mesh.traverse((child: any) => {
      if (child.isMesh && child.geometry) {
        // Create WireframeGeometry - shows all edges
        const wireframeGeometry = new THREE.WireframeGeometry(child.geometry);
        
        wires.push(
          <lineSegments 
            key={`wire-${wireIndex++}`}
            geometry={wireframeGeometry}
            position={child.position}
            rotation={child.rotation}
            scale={child.scale}
          >
            <lineBasicMaterial color={color} linewidth={lineWidth} />
          </lineSegments>
        );
      }
    });
    
    return wires;
  }, [mesh, color, lineWidth]);

  return <>{wireframes}</>;
}
