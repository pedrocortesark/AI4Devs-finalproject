/**
 * Test Helpers for T-1507-TEST Frontend Integration Tests
 * 
 * TDD Phase: RED
 * Purpose: Reusable utilities for Element + Canvas testing
 */

import { v4 as uuidv4 } from 'uuid';

/**
 * MATERIAL_COLORS Dictionary (63 materials from T-1504-AGENT)
 * 
 * Must be IDENTICAL to src/agent/constants.py MATERIAL_COLORS
 * Format: { material_name: [R, G, B] }
 */
export const MATERIAL_COLORS: Record<string, [number, number, number]> = {
  'Montjuïc': [230, 180, 100],
  'Ulldecona': [200, 160, 120],
  'Floresta': [180, 140, 100],
  // ... (remaining 60 materials - placeholder for RED phase)
  // Full dictionary should be imported from shared constants in GREEN phase
};

/**
 * Mock Element Factory
 * 
 * Generates Element objects matching API schema for testing
 */
export function mockElement(overrides: Partial<Element> = {}): Element {
  const id = overrides.id || uuidv4();
  const isoCode = overrides.iso_code || `MOCK-${uuidv4().slice(0, 8)}`;
  
  return {
    id,
    iso_code: isoCode,
    status: 'validated',
    material_type: 'Montjuïc',
    low_poly_url: `https://example.supabase.co/storage/v1/object/public/glb-files/${id}/low_poly.glb`,
    bbox: {
      min: [0, 0, 0],
      max: [100, 100, 100],
    },
    ...overrides,
  };
}

/**
 * Wait for Canvas to render (async utility)
 * 
 * Useful for React Three Fiber rendering in tests
 */
export async function waitForCanvas(timeout: number = 2000): Promise<void> {
  return new Promise<void>((resolve) => {
    const checkCanvas = () => {
      const canvas = document.querySelector('canvas');
      if (canvas) {
        resolve();
      } else if (timeout > 0) {
        timeout -= 100;
        setTimeout(checkCanvas, 100);
      } else {
        resolve(); // Timeout, resolve anyway
      }
    };
    checkCanvas();
  });
}

/**
 * Get rendered meshes from Three.js scene (test utility)
 * 
 * Note: In RED phase, this may not work until Canvas component exists
 */
export function getRenderedMeshes(_canvas: HTMLCanvasElement): number {
  // Placeholder: Inspect Three.js scene for mesh count
  // In GREEN phase, implement actual Three.js scene traversal
  return 0;
}

/**
 * Assert material color matches MATERIAL_COLORS dictionary
 * 
 * Validates that rendered material color matches expected RGB from dictionary
 */
export function assertMaterialColor(
  material_type: string,
  renderedRGB: [number, number, number]
): void {
  const expectedRGB = MATERIAL_COLORS[material_type];
  
  if (!expectedRGB) {
    throw new Error(`Material type '${material_type}' not found in MATERIAL_COLORS`);
  }

  const tolerance = 5; // Allow 5-unit difference per channel (lighting/shader)
  
  for (let i = 0; i < 3; i++) {
    const diff = Math.abs(expectedRGB[i] - renderedRGB[i]);
    if (diff > tolerance) {
      throw new Error(
        `Material color mismatch for '${material_type}': ` +
        `Expected RGB[${i}]=${expectedRGB[i]}, got ${renderedRGB[i]} (diff: ${diff})`
      );
    }
  }
}

/**
 * TypeScript Interfaces (match backend Pydantic schemas)
 */
export interface Element {
  id: string;
  iso_code: string;
  status: string;
  material_type: string;
  low_poly_url: string | null;
  bbox: BoundingBox | null;
}

export interface BoundingBox {
  min: [number, number, number];
  max: [number, number, number];
}
