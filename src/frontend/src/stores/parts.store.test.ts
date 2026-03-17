/**
 * T-0506-FRONT: Parts Store Tests - Filter Functionality
 *
 * Tests for Zustand store filter methods using the new
 * material (material_type) and agrupacio (SF_ARC_Agrupacio1) fields.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { usePartsStore } from './parts.store';
import { PartCanvasItem, BlockStatus } from '@/types/parts';

const mockParts: PartCanvasItem[] = [
  {
    id: '1',
    iso_code: 'SF-C12-D-001',
    status: 'validated' as BlockStatus,
    tipologia: 'Montjuïc',
    agrupacio: 'Nef Central',
    low_poly_url: 'https://example.com/1.glb',
    bbox: { min: [0, 0, 0], max: [1, 1, 1] },
    workshop_id: 'workshop-123',
  },
  {
    id: '2',
    iso_code: 'SF-C12-D-002',
    status: 'uploaded' as BlockStatus,
    tipologia: 'Ulldecona',
    agrupacio: 'Absis',
    low_poly_url: 'https://example.com/2.glb',
    bbox: { min: [0, 0, 0], max: [1, 1, 1] },
    workshop_id: 'workshop-456',
  },
  {
    id: '3',
    iso_code: 'SF-C12-D-003',
    status: 'uploaded' as BlockStatus,
    tipologia: 'Montjuïc',
    agrupacio: 'Nef Central',
    low_poly_url: 'https://example.com/3.glb',
    bbox: { min: [0, 0, 0], max: [1, 1, 1] },
    workshop_id: null,
  },
];

describe('PartsStore - Filter Functionality', () => {
  beforeEach(() => {
    usePartsStore.setState({
      parts: [],
      filters: { material: [], agrupacio: [], workshop_id: null },
      selectedId: null,
      isLoading: false,
      error: null,
    });
  });

  describe('setFilters', () => {
    it('should update filters with partial updates', () => {
      const { setFilters } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc'] });

      expect(usePartsStore.getState().filters.material).toEqual(['Montjuïc']);
      expect(usePartsStore.getState().filters.agrupacio).toEqual([]);
    });

    it('should merge new filters with existing filters', () => {
      const { setFilters } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc'] });
      setFilters({ agrupacio: ['Nef Central'] });

      const state = usePartsStore.getState();
      expect(state.filters.material).toEqual(['Montjuïc']);
      expect(state.filters.agrupacio).toEqual(['Nef Central']);
    });
  });

  describe('clearFilters', () => {
    it('should reset all filters to initial empty state', () => {
      const { setFilters, clearFilters } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc'], agrupacio: ['Nef Central'] });
      clearFilters();

      const state = usePartsStore.getState();
      expect(state.filters.material).toEqual([]);
      expect(state.filters.agrupacio).toEqual([]);
      expect(state.filters.workshop_id).toBeNull();
    });
  });

  describe('getFilteredParts', () => {
    beforeEach(() => {
      usePartsStore.setState({ parts: mockParts });
    });

    it('should return all parts when no filters applied', () => {
      const { getFilteredParts } = usePartsStore.getState();
      expect(getFilteredParts()).toHaveLength(3);
    });

    it('should filter by single material (OR logic)', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc'] });
      const filtered = getFilteredParts();

      expect(filtered).toHaveLength(2);
      expect(filtered.every((p) => p.tipologia === 'Montjuïc')).toBe(true);
    });

    it('should filter by multiple materials (OR logic)', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc', 'Ulldecona'] });
      expect(getFilteredParts()).toHaveLength(3);
    });

    it('should filter by single agrupacio', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ agrupacio: ['Absis'] });
      const filtered = getFilteredParts();

      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('2');
    });

    it('should filter by multiple agrupacions (OR logic)', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ agrupacio: ['Nef Central', 'Absis'] });
      expect(getFilteredParts()).toHaveLength(3);
    });

    it('should combine material and agrupacio with AND logic', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ material: ['Montjuïc'], agrupacio: ['Nef Central'] });
      const filtered = getFilteredParts();

      expect(filtered).toHaveLength(2);
      expect(filtered.every((p) => p.tipologia === 'Montjuïc')).toBe(true);
      expect(filtered.every((p) => p.agrupacio === 'Nef Central')).toBe(true);
    });

    it('should filter by workshop_id', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ workshop_id: 'workshop-123' });
      const filtered = getFilteredParts();

      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('1');
    });

    it('should return empty array when no parts match filters', () => {
      const { setFilters, getFilteredParts } = usePartsStore.getState();

      setFilters({ material: ['Floresta'] }); // No parts with this material
      expect(getFilteredParts()).toHaveLength(0);
    });
  });
});
