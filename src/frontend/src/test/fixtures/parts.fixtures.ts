/**
 * Test Fixtures for Parts/Dashboard Integration Tests
 * T-0509-TEST-FRONT: 3D Dashboard Integration Tests
 *
 * Provides mock data for PartCanvasItem to test dashboard rendering,
 * filtering, selection, and performance scenarios.
 *
 * @module test/fixtures/parts.fixtures
 */

import { BlockStatus, type PartCanvasItem } from '@/types/parts';

export const mockPartCapitel: PartCanvasItem = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  iso_code: 'SF-C12-CAP-001',
  status: BlockStatus.Validated,
  tipologia: 'Montjuïc',
  agrupacio: 'Nef Central',
  low_poly_url: 'https://storage.supabase.co/object/public/processed-geometry/capitel-001.glb',
  bbox: { min: [0, 0, 0], max: [1, 1, 1] },
  workshop_id: 'workshop-123',
  workshop_name: 'Taller Granollers',
};

export const mockPartColumna: PartCanvasItem = {
  id: '223e4567-e89b-12d3-a456-426614174001',
  iso_code: 'SF-C12-COL-002',
  status: BlockStatus.InFabrication,
  tipologia: 'Ulldecona',
  agrupacio: 'Absis',
  low_poly_url: 'https://storage.supabase.co/object/public/processed-geometry/columna-002.glb',
  bbox: { min: [0, 0, 0], max: [2, 2, 3] },
  workshop_id: 'workshop-456',
  workshop_name: 'Taller Barcelona',
};

export const mockPartDovela: PartCanvasItem = {
  id: '323e4567-e89b-12d3-a456-426614174002',
  iso_code: 'SF-C12-DOV-003',
  status: BlockStatus.Uploaded,
  tipologia: 'Floresta',
  agrupacio: null,
  low_poly_url: null, // Not processed yet
  bbox: null,
  workshop_id: null,
  workshop_name: null,
};

export const mockPartClave: PartCanvasItem = {
  id: '423e4567-e89b-12d3-a456-426614174003',
  iso_code: 'SF-C12-CLA-004',
  status: BlockStatus.Completed,
  tipologia: 'Montjuïc',
  agrupacio: 'Nef Central',
  low_poly_url: 'https://storage.supabase.co/object/public/processed-geometry/clave-004.glb',
  bbox: { min: [0, 0, 0], max: [0.5, 0.5, 0.5] },
  workshop_id: 'workshop-123',
  workshop_name: 'Taller Granollers',
};

export const mockPartImposta: PartCanvasItem = {
  id: '523e4567-e89b-12d3-a456-426614174004',
  iso_code: 'SF-C12-IMP-005',
  status: BlockStatus.Archived,
  tipologia: 'Ulldecona',
  agrupacio: 'Façana Passió',
  low_poly_url: 'https://storage.supabase.co/object/public/processed-geometry/imposta-005.glb',
  bbox: { min: [0, 0, 0], max: [1.5, 1.5, 0.5] },
  workshop_id: null,
  workshop_name: null,
};

/**
 * Generate N mock parts for performance testing
 */
export function generate150MockParts(count: number = 150): PartCanvasItem[] {
  const statuses = [BlockStatus.Validated, BlockStatus.InFabrication, BlockStatus.Completed];
  const materials = ['Montjuïc', 'Ulldecona', 'Floresta'] as const;
  const agrupacions = ['Nef Central', 'Absis', 'Façana Passió'] as const;
  const workshops = [
    { id: 'workshop-123', name: 'Taller Granollers' },
    { id: 'workshop-456', name: 'Taller Barcelona' },
    { id: 'workshop-789', name: 'Taller Vic' },
  ];

  return Array.from({ length: count }, (_, i) => ({
    id: `part-${String(i).padStart(4, '0')}`,
    iso_code: `SF-TEST-${String(i).padStart(3, '0')}`,
    status: statuses[i % 3],
    tipologia: materials[i % 3],
    agrupacio: agrupacions[i % 3],
    low_poly_url: `https://storage.supabase.co/object/public/processed-geometry/part-${i}.glb`,
    bbox: { min: [0, 0, 0], max: [1, 1, 1] },
    workshop_id: workshops[i % 3].id,
    workshop_name: workshops[i % 3].name,
  }));
}

/**
 * Mixed collection for complex filter testing
 * Contains parts with various combinations of agrupacio/material/workshop.
 */
export const mockPartsForFilterTesting: PartCanvasItem[] = [
  mockPartCapitel,   // Montjuïc + Nef Central + workshop-123
  mockPartColumna,   // Ulldecona + Absis + workshop-456
  mockPartDovela,    // Floresta + null agrupacio + no workshop
  mockPartClave,     // Montjuïc + Nef Central + workshop-123
  mockPartImposta,   // Ulldecona + Façana Passió + no workshop
  {
    id: '623e4567-e89b-12d3-a456-426614174005',
    iso_code: 'SF-C12-CAP-006',
    status: BlockStatus.Validated,
    tipologia: 'Montjuïc',
    agrupacio: 'Nef Central',
    low_poly_url: 'https://storage.supabase.co/object/public/processed-geometry/capitel-006.glb',
    bbox: { min: [0, 0, 0], max: [1, 1, 1] },
    workshop_id: 'workshop-456',
    workshop_name: 'Taller Barcelona',
  },
];
