/**
 * MSW Request Handlers for T-1507-TEST Frontend Integration Tests
 * 
 * TDD Phase: RED
 * Purpose: Mock API responses for Element endpoints
 * 
 * Mocked Endpoints:
 *   - GET /api/elements → List elements with pagination
 *   - GET /api/elements/:id → Element detail
 */

import { http, HttpResponse } from 'msw';
import { mockElement } from '../helpers/element-helpers';

/**
 * Sample mock elements using 62 MATERIAL_COLORS
 */
const mockElements = [
  mockElement({
    iso_code: 'MOCK-E2E-001',
    material_type: 'Montjuïc',
    status: 'validated',
  }),
  mockElement({
    iso_code: 'MOCK-E2E-002',
    material_type: 'Ulldecona',
    status: 'validated',
  }),
  mockElement({
    iso_code: 'MOCK-E2E-003',
    material_type: 'Floresta',
    status: 'processing',
  }),
];

/**
 * MSW Handlers for Element API
 */
export const handlers = [
  /**
   * GET /api/elements - List elements with filtering
   */
  http.get('/api/elements', ({ request }) => {
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get('status');
    const materialFilter = url.searchParams.get('material_type');

    let filtered = mockElements;

    if (statusFilter) {
      filtered = filtered.filter(el => el.status === statusFilter);
    }

    if (materialFilter) {
      filtered = filtered.filter(el => el.material_type === materialFilter);
    }

    return HttpResponse.json({
      elements: filtered,
      meta: {
        total: mockElements.length,
        filtered: filtered.length,
      },
    });
  }),

  /**
   * GET /api/elements/:id - Get element detail
   * 
   * Strategy: Return existing element from mockElements if found,
   * otherwise generate dynamic mock element (allows tests to create elements on-the-fly)
   */
  http.get('/api/elements/:id', ({ params }) => {
    const { id } = params;
    
    // Check if element exists in predefined mocks
    let element = mockElements.find(el => el.id === id);
    
    // If not found and id is valid UUID (not '00000000...'), generate dynamic mock
    const isInvalidId = id === '00000000-0000-0000-0000-000000000000';
    
    if (!element && !isInvalidId) {
      // Generate dynamic element for test-created IDs
      element = mockElement({ id: id as string });
    }
    
    if (!element || isInvalidId) {
      return HttpResponse.json(
        { detail: 'Element not found' },
        { status: 404 }
      );
    }

    // Element detail includes additional fields
    return HttpResponse.json({
      ...element,
      validation_report: null,
      rhino_metadata: {
        layer_name: 'Default',
        user_strings: { Codi: element.iso_code },
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),

  /**
   * GET https://example.com/*.glb - Mock GLB file load failures
   * Used by ERR-FE-02 test to simulate 404 on GLB fetch
   */
  http.get('https://example.com/*.glb', () => {
    return new HttpResponse(null, { status: 404 });
  }),

  /**
   * GET https://example.supabase.co/storage/* - Mock successful GLB loads
   * Returns empty blob for successful GLB loads in tests
   */
  http.get('https://example.supabase.co/storage/*', () => {
    return new HttpResponse(new Blob(), {
      status: 200,
      headers: {
        'Content-Type': 'model/gltf-binary',
      },
    });
  }),
];
