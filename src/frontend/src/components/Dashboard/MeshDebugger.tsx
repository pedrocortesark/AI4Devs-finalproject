/**
 * MeshDebugger - Shows wireframe boxes at part positions to verify spatial layout
 */

import { Box } from '@react-three/drei';
import type { PartCanvasItem } from '@/types/parts';
import type { Position3D } from './PartsScene.types';

interface MeshDebuggerProps {
  parts: PartCanvasItem[];
  positions: Position3D[];
}

export function MeshDebugger({ parts, positions }: MeshDebuggerProps) {
  console.log('🔧 MeshDebugger: Rendering', positions.length, 'debug boxes');
  
  return (
    <group name="mesh-debugger">
      {positions.map((position, index) => {
        const part = parts[index];
        if (!part) return null;
        
        // Small visible box at each part position
        return (
          <Box
            key={part.id}
            position={position}
            args={[0.5, 0.5, 0.5]} // 50cm cube for visibility
          >
            <meshStandardMaterial
              color="red"
              wireframe={true}
              opacity={0.8}
              transparent={true}
            />
          </Box>
        );
      })}
    </group>
  );
}
