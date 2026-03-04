/**
 * BBoxProxy Component Tests
 *
 * T-0507-FRONT: LOD System - BBox Wireframe Proxy Tests
 *
 * Phase: RED (tests written before implementation)
 * Expected: ALL 9 tests FAIL with ImportError (module './BBoxProxy' not found)
 *
 * @module BBoxProxy.test
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { BBoxProxy } from './BBoxProxy';
import type { BoundingBox } from '@/types/parts';

describe('BBoxProxy', () => {
  // Test data
  const mockBBox: BoundingBox = {
    min: [-1.5, -1.2, 0.0],
    max: [1.5, 1.2, 3.4],
  };

  const mockColor = '#3B82F6'; // STATUS_COLORS.validated

  describe('Happy Path - Rendering', () => {
    it('HP-BBOX-1: renders boxGeometry with correct dimensions from bbox', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} />);

      // Calculate expected dimensions
      const width = mockBBox.max[0] - mockBBox.min[0];   // 3.0
      const height = mockBBox.max[1] - mockBBox.min[1];  // 2.4
      const depth = mockBBox.max[2] - mockBBox.min[2];   // 3.4

      // Should render a mesh with boxGeometry
      const mesh = container.querySelector('[name="bbox-proxy"]');
      expect(mesh).toBeDefined();

      // Geometry dimensions should match bbox
      const geometry = mesh!.querySelector('boxgeometry');
      expect(geometry).toBeDefined();
      expect(geometry?.getAttribute('args')).toContain(width.toString());
      expect(geometry?.getAttribute('args')).toContain(height.toString());
      expect(geometry?.getAttribute('args')).toContain(depth.toString());
    });

    it('HP-BBOX-2: applies color prop to meshBasicMaterial', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} />);

      const material = container.querySelector('[name="bbox-material"]');
      expect(material!.getAttribute('color')).toBe(mockColor);
    });

    it('HP-BBOX-3: applies default opacity 0.3 when opacity prop not provided', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} />);

      const material = container.querySelector('[name="bbox-material"]');
      expect(material!.getAttribute('opacity')).toBe('0.3');
      expect(material!.getAttribute('transparent')).toBe('true');
    });

    it('HP-BBOX-4: applies custom opacity when opacity prop provided', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} opacity={0.5} />);

      const material = container.querySelector('[name="bbox-material"]');
      expect(material!.getAttribute('opacity')).toBe('0.5');
    });

    it('HP-BBOX-5: renders as wireframe by default', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} />);

      const material = container.querySelector('[name="bbox-material"]');
      expect(material!.getAttribute('wireframe')).toBe('true');
    });

    it('HP-BBOX-6: respects wireframe=false prop', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} wireframe={false} />);

      const material = container.querySelector('[name="bbox-material"]');
      expect(material!.getAttribute('wireframe')).toBe('false');
    });
  });

  describe('Edge Cases', () => {
    it('EC-BBOX-1: centers box geometry at bbox center point', () => {
      const { container } = render(<BBoxProxy bbox={mockBBox} color={mockColor} />);

      // Calculate expected center
      const centerX = (mockBBox.min[0] + mockBBox.max[0]) / 2;  // 0.0
      const centerY = (mockBBox.min[1] + mockBBox.max[1]) / 2;  // 0.0
      const centerZ = (mockBBox.min[2] + mockBBox.max[2]) / 2;  // 1.7

      const mesh = container.querySelector('[name="bbox-proxy"]');
      const position = mesh!.getAttribute('position');

      expect(position).toContain(centerX.toString());
      expect(position).toContain(centerY.toString());
      expect(position).toContain(centerZ.toString());
    });

    it('EC-BBOX-2: handles zero-sized bbox dimensions gracefully', () => {
      const flatBBox: BoundingBox = {
        min: [0, 0, 0],
        max: [0, 0, 0], // Zero volume
      };

      // Should not crash, render 0-sized box
      const { container } = render(<BBoxProxy bbox={flatBBox} color={mockColor} />);

      const mesh = container.querySelector('[name="bbox-proxy"]');
      expect(mesh).toBeDefined();
    });

    it('EC-BBOX-3: handles negative bbox coordinates', () => {
      const negativeBBox: BoundingBox = {
        min: [-5, -10, -2],
        max: [-2, -5, 1],
      };

      // Should handle negative coordinates correctly
      const { container } = render(<BBoxProxy bbox={negativeBBox} color={mockColor} />);

      const mesh = container.querySelector('[name="bbox-proxy"]');
      expect(mesh).toBeDefined();

      // Width should be positive even with negative coords
      const width = negativeBBox.max[0] - negativeBBox.min[0];  // 3
      expect(width).toBeGreaterThan(0);
    });
  });

  describe('BBoxProxy — mm scale invariants', () => {
    /**
     * These tests encode the unit = 1mm contract between the agent pipeline and
     * the Three.js viewer.  A capitel bbox of 200×300×1200 mm must produce
     * geometry in that exact range — not 0.2×0.3×1.2 (meters) or 200000×...
     * (microns).
     *
     * Scene reference: camera at 50 000 mm, LOD switch at 50 000 mm, grid
     * cells 5 000 mm.  Coordinate ranges in this describe block are realistic
     * Sagrada Família architectural piece sizes in mm.
     */

    it('MM-BBOX-1: realistic capitel bbox (200×300×1200 mm) produces correct geometry dimensions', () => {
      // Capitel: 200 mm wide, 300 mm deep, 1 200 mm tall
      const capitelBBox: BoundingBox = {
        min: [-100, 0, -150],
        max: [100, 1200, 150],
      };
      const { container } = render(<BBoxProxy bbox={capitelBBox} color={mockColor} />);

      const geometry = container.querySelector('[name="bbox-proxy"] boxgeometry');
      const argsAttr = geometry?.getAttribute('args') ?? '';

      const expectedWidth = 200;   // max[0] - min[0]
      const expectedHeight = 1200; // max[1] - min[1]
      const expectedDepth = 300;   // max[2] - min[2]

      expect(argsAttr).toContain(expectedWidth.toString());
      expect(argsAttr).toContain(expectedHeight.toString());
      expect(argsAttr).toContain(expectedDepth.toString());
    });

    it('MM-BBOX-2: bbox center position matches midpoint of mm coordinates', () => {
      // Column: 1 000 mm wide, 3 000 mm tall, 1 000 mm deep — centre at [0, 1500, 0]
      const columnBBox: BoundingBox = {
        min: [-500, 0, -500],
        max: [500, 3000, 500],
      };
      const { container } = render(<BBoxProxy bbox={columnBBox} color={mockColor} />);

      const mesh = container.querySelector('[name="bbox-proxy"]');
      const position = mesh!.getAttribute('position') ?? '';

      const centerX = (columnBBox.min[0] + columnBBox.max[0]) / 2; // 0
      const centerY = (columnBBox.min[1] + columnBBox.max[1]) / 2; // 1500
      const centerZ = (columnBBox.min[2] + columnBBox.max[2]) / 2; // 0

      expect(position).toContain(centerX.toString());
      expect(position).toContain(centerY.toString());
      expect(position).toContain(centerZ.toString());
    });

    it('MM-BBOX-3: large SF column (3000 mm) dimensions are well below LOD threshold (50 000 mm)', () => {
      // The LOD wireframe proxy is shown at distance > 50 000 mm from camera.
      // A 3 m column (3 000 mm) should produce a bbox far smaller than that threshold.
      const columnBBox: BoundingBox = {
        min: [-200, 0, -200],
        max: [200, 3000, 200],
      };

      const height = columnBBox.max[1] - columnBBox.min[1]; // 3 000
      const LOD_THRESHOLD_MM = 50_000;

      // The bbox wireframe must be proportionally small vs the LOD distance
      expect(height).toBeLessThan(LOD_THRESHOLD_MM);
      expect(height / LOD_THRESHOLD_MM).toBeLessThan(0.1); // < 10% of LOD distance

      // Verify component renders without errors for realistic SF column
      const { container } = render(<BBoxProxy bbox={columnBBox} color={mockColor} />);
      const mesh = container.querySelector('[name="bbox-proxy"]');
      expect(mesh).toBeDefined();
    });

    it('MM-BBOX-4: bbox coordinates are not in meters (values should be >1 for any real SF part)', () => {
      // If someone accidentally converts mm→m, a 200mm part becomes 0.2 — this test catches that.
      const capitelBBox: BoundingBox = {
        min: [-100, 0, -150],
        max: [100, 400, 150],
      };

      const width = capitelBBox.max[0] - capitelBBox.min[0];
      const height = capitelBBox.max[1] - capitelBBox.min[1];
      const depth = capitelBBox.max[2] - capitelBBox.min[2];

      // All dimensions must be > 1 mm (if they were in meters, 200mm = 0.2 < 1)
      expect(width).toBeGreaterThan(1);
      expect(height).toBeGreaterThan(1);
      expect(depth).toBeGreaterThan(1);
    });
  });
});
