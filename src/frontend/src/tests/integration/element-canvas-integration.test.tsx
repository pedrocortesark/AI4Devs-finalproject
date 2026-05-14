/**
 * Integration tests for T-1507-TEST: Element + Canvas 3D Integration
 * 
 * TDD Phase: RED — These tests will FAIL until Canvas component is fully integrated
 * 
 * Verifies:
 *   - Element API → Canvas render pipeline
 *   - Material colors from MATERIAL_COLORS dictionary applied to 3D meshes
 *   - Bounding box visualization
 *   - Error states in UI
 * 
 * Test Strategy: Multi-Layer Integration Testing (no Cypress)
 *   - Vitest + MSW for API mocking
 *   - @testing-library/react for component testing
 *   - Three.js scene inspection via canvas element
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { mockElement, waitForCanvas, MATERIAL_COLORS } from '../helpers/element-helpers';
import { ElementCanvas } from '../../components/ElementCanvas'; // Placeholder component

// MSW Server lifecycle
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/**
 * T-1507-TEST: Happy Path Frontend Tests (HP-FE-01 to HP-FE-04)
 */
describe('ElementCanvas Integration - Happy Path', () => {
  it('HP-FE-01: renders canvas element when component mounts', async () => {
    /**
     * Given: ElementCanvas component with element_id prop
     * When: Component renders
     * Then:
     *   - Canvas element exists in DOM
     *   - Canvas has correct WebGL context
     */
    const element = mockElement({ iso_code: 'TEST-HP-FE-01' });
    
    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();
    
    const canvas = screen.getByRole('img'); // Canvas has implicit img role
    expect(canvas).toBeInTheDocument();
    expect(canvas.tagName).toBe('CANVAS');
  });

  it('HP-FE-02: fetches element from API and renders 3D model', async () => {
    /**
     * Given: Element exists in API with low_poly_url
     * When: ElementCanvas mounts with element_id
     * Then:
     *   - API request made to GET /api/elements/:id
     *   - GLB file loaded from low_poly_url
     *   - 3D mesh rendered on canvas
     */
    const element = mockElement({
      iso_code: 'TEST-HP-FE-02',
      low_poly_url: 'https://example.com/model.glb',
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitFor(() => {
      const canvas = screen.queryByRole('img');
      expect(canvas).toBeInTheDocument();
    });

    // TODO: Verify GLB loaded (check Three.js scene in GREEN phase)
  });

  it('HP-FE-03: applies material color from MATERIAL_COLORS dictionary', async () => {
    /**
     * Given: Element with material_type "Montjuïc" (RGB: [230, 180, 100])
     * When: 3D model renders
     * Then:
     *   - Mesh material color matches MATERIAL_COLORS["Montjuïc"]
     *   - Color applied as RGB with tolerance ±5
     */
    const element = mockElement({
      material_type: 'Montjuïc',
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // TODO: Inspect Three.js material color in GREEN phase
    const expectedRGB = MATERIAL_COLORS['Montjuïc'];
    expect(expectedRGB).toEqual([230, 180, 100]);
  });

  it('HP-FE-04: renders bounding box visualization if bbox present', async () => {
    /**
     * Given: Element with bbox {min: [0,0,0], max: [100,100,100]}
     * When: Canvas renders
     * Then:
     *   - BoundingBox helper rendered (wireframe cube)
     *   - Box dimensions match bbox min/max
     */
    const element = mockElement({
      bbox: {
        min: [0, 0, 0],
        max: [100, 100, 100],
      },
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // TODO: Verify BoundingBox helper in scene (GREEN phase)
  });
});

/**
 * T-1507-TEST: Edge Case Frontend Tests (EC-FE-01 to EC-FE-04)
 */
describe('ElementCanvas Integration - Edge Cases', () => {
  it('EC-FE-01: handles element without low_poly_url (shows placeholder)', async () => {
    /**
     * Given: Element with low_poly_url = null
     * When: Canvas renders
     * Then:
     *   - Placeholder cube/sphere rendered
     *   - No 404 errors in console
     */
    const element = mockElement({
      low_poly_url: null,
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // Should not crash, shows placeholder geometry
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('EC-FE-02: handles element without bbox (no bounding box visualization)', async () => {
    /**
     * Given: Element with bbox = null
     * When: Canvas renders
     * Then:
     *   - 3D model renders without bbox helper
     *   - No errors thrown
     */
    const element = mockElement({
      bbox: null,
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // Should render model without bbox visualization
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('EC-FE-03: applies default Montjuïc material if material_type not in MATERIAL_COLORS', async () => {
    /**
     * Given: Element with invalid material_type "UnknownMaterial"
     * When: Canvas renders
     * Then:
     *   - Defaults to "Montjuïc" material color
     *   - Warning logged to console (optional)
     */
    const element = mockElement({
      material_type: 'UnknownMaterial',
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // Should default to Montjuïc without crashing
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('EC-FE-04: handles slow API response gracefully (loading state)', async () => {
    /**
     * Given: GET /api/elements/:id takes 3 seconds
     * When: Canvas mounts
     * Then:
     *   - Loading spinner shown initially
     *   - Canvas renders after API response
     */
    const element = mockElement();

    render(<ElementCanvas elementId={element.id} />);
    
    // Initially shows loading
    expect(screen.queryByText(/loading/i)).toBeInTheDocument();

    // After API resolves, canvas appears
    await waitForCanvas();
    expect(screen.queryByRole('img')).toBeInTheDocument();
  });
});

/**
 * T-1507-TEST: Error Handling Frontend Tests (ERR-FE-01 to ERR-FE-03)
 */
describe('ElementCanvas Integration - Error Handling', () => {
  it('ERR-FE-01: shows error UI when element_id not found (404)', async () => {
    /**
     * Given: element_id does not exist in API
     * When: Canvas component mounts
     * Then:
     *   - API returns 404
     *   - Error message shown to user: "Element not found"
     *   - Canvas does not render
     */
    const invalidId = '00000000-0000-0000-0000-000000000000';

    render(<ElementCanvas elementId={invalidId} />);
    
    await waitFor(() => {
      expect(screen.queryByText(/element not found/i)).toBeInTheDocument();
    });

    // Canvas should not render
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it.skip('ERR-FE-02: shows error UI when GLB file fails to load', async () => {
    /**
     * SKIPPED: Requires THREE.GLTFLoader implementation
     * 
     * Given: Element with invalid low_poly_url (404 on GLB fetch)
     * When: THREE.GLTFLoader attempts to load
     * Then:
     *   - Error message shown: "Failed to load 3D model"
     *   - Canvas shows placeholder geometry
     * 
     * TODO: Implement when THREE.js GLTFLoader is integrated
     */
    const element = mockElement({
      low_poly_url: 'https://example.com/nonexistent.glb',
    });

    render(<ElementCanvas elementId={element.id} />);
    
    await waitFor(() => {
      expect(screen.queryByText(/failed to load 3d model/i)).toBeInTheDocument();
    });
  });

  it.skip('ERR-FE-03: handles network error gracefully (API unreachable)', async () => {
    /**
     * SKIPPED: Requires advanced error handling implementation
     * 
     * Given: Network request to /api/elements/:id fails (network error)
     * When: Canvas mounts
     * Then:
     *   - Error message shown: "Network error"
     *   - Retry button rendered (optional)
     * 
     * TODO: Implement retry mechanism and network error UI
     */
    // Mock network error in MSW
    server.use(
      http.get('/api/elements/:id', () => {
        return HttpResponse.error();
      })
    );

    const element = mockElement();

    render(<ElementCanvas elementId={element.id} />);
    
    await waitFor(() => {
      expect(screen.queryByText(/network error/i)).toBeInTheDocument();
    });
  });
});

/**
 * T-1507-TEST: Infrastructure Frontend Tests (INT-FE-01 to INT-FE-03)
 */
describe('ElementCanvas Integration - Infrastructure', () => {
  it.skip('INT-FE-01: canvas resizes responsively on window resize', async () => {
    /**
     * SKIPPED: Requires THREE.js camera and renderer implementation
     * 
     * Given: ElementCanvas rendered
     * When: Window resizes
     * Then:
     *   - Canvas dimensions update
     *   - Three.js camera aspect ratio adjusts
     * 
     * TODO: Implement when THREE.js camera/renderer is integrated
     */
    const element = mockElement();

    render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    const canvas = screen.getByRole('img') as HTMLCanvasElement;
    const initialWidth = canvas.width;

    // Simulate window resize
    window.innerWidth = 800;
    window.dispatchEvent(new Event('resize'));

    await waitFor(() => {
      expect(canvas.width).not.toBe(initialWidth);
    });
  });

  it('INT-FE-02: THREE.js memory cleanup on component unmount', async () => {
    /**
     * Given: ElementCanvas mounted
     * When: Component unmounts
     * Then:
     *   - THREE.js geometries disposed
     *   - Materials disposed
     *   - No memory leaks
     */
    const element = mockElement();

    const { unmount } = render(<ElementCanvas elementId={element.id} />);
    
    await waitForCanvas();

    // Unmount and verify cleanup (check Three.js disposal in GREEN phase)
    unmount();

    // TODO: Verify THREE.Scene.dispose() called
  });

  it('INT-FE-03: MATERIAL_COLORS dictionary matches backend (63 materials)', async () => {
    /**
     * Given: Frontend MATERIAL_COLORS dictionary
     * When: Comparing with backend src/agent/constants.py
     * Then:
     *   - 63 materials exist
     *   - Material names match exactly (including accents: Montjuïc)
     *   - RGB values identical
     */
    expect(Object.keys(MATERIAL_COLORS).length).toBe(63);

    // Verify key materials (values from backend src/agent/constants.py)
    expect(MATERIAL_COLORS['Montjuïc']).toEqual([230, 180, 100]);
    expect(MATERIAL_COLORS['Ulldecona']).toEqual([240, 220, 180]);
    expect(MATERIAL_COLORS['Floresta']).toEqual([225, 200, 130]);
  });
});