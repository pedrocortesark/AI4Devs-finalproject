/**
 * MeshWithEdges - Wraps a mesh with edge lines for better visibility
 */

import { useMemo } from 'react';
import * as THREE from 'three';

interface MeshWithEdgesProps {
  mesh: THREE.Object3D;
  edgeColor?: string;
  edgeThreshold?: number;
}

/**
 * Adds edge lines to a mesh to improve visual definition
 * Useful when solid colors make geometry look flat
 */
export function MeshWithEdges({ 
  mesh, 
  edgeColor = '#000000', 
  edgeThreshold = 15 
}: MeshWithEdgesProps) {
  
  const edges = useMemo(() => {
    const edgeObjects: JSX.Element[] = [];
    let edgeIndex = 0;
    
    mesh.traverse((child: any) => {
      if (child.isMesh && child.geometry) {
        // Create EdgesGeometry from the mesh geometry
        const edgesGeometry = new THREE.EdgesGeometry(child.geometry, edgeThreshold);
        
        edgeObjects.push(
          <lineSegments 
            key={`edge-${edgeIndex++}`} 
            geometry={edgesGeometry}
            position={child.position}
            rotation={child.rotation}
            scale={child.scale}
          >
            <lineBasicMaterial color={edgeColor} linewidth={1} />
          </lineSegments>
        );
      }
    });
    
    return edgeObjects;
  }, [mesh, edgeColor, edgeThreshold]);

  return <>{edges}</>;
}
