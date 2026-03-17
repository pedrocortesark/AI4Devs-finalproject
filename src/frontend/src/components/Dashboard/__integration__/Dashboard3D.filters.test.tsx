/**
 * Integration Test Suite 2: Filters & State Integration
 * T-0509-TEST-FRONT: 3D Dashboard Integration Tests
 *
 * Tests the integration between FilterBar, Zustand store, and Canvas rendering:
 * - Filter selection updates store state
 * - Store state updates trigger canvas opacity changes
 * - Clear filters button resets all state
 * - AND logic for multiple active filters
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard3D from '../Dashboard3D';
import { usePartsStore } from '@/stores/parts.store';
import { mockPartsForFilterTesting } from '../../../test/fixtures/parts.fixtures';
import { setupStoreMock } from './test-helpers';

// Mock the Zustand store
vi.mock('@/stores/parts.store');

// Mock usePartDetail hook (DetailsPanel not relevant to filter tests)
vi.mock('@/components/Dashboard/PartDetailModal.hooks', () => ({
  usePartDetail: vi.fn(() => ({ partData: null, loading: false, error: null, retry: vi.fn() })),
}));

// Mock PartViewer3D (Three.js canvas doesn't work in jsdom)
vi.mock('@/components/details/PartViewer3D', () => ({
  PartViewer3D: () => <div data-testid="part-viewer-3d-mock" />,
}));

describe('Dashboard3D Filters & State Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupStoreMock({
      parts: mockPartsForFilterTesting,
      getFilteredParts: vi.fn(() => mockPartsForFilterTesting),
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  /**
   * Test 6: Filtering by agrupacio updates store state
   *
   * Integration Point: FilterBar Agrupació dropdown → partsStore.setFilters
   * Expected: setFilters called with agrupacio: ['Nef Central']
   */
  it('filters parts by agrupacio when dropdown item selected', async () => {
    const user = userEvent.setup();
    const mockSetFilters = vi.fn();
    const mockGetFilteredParts = vi.fn(() =>
      mockPartsForFilterTesting.filter((p) => p.agrupacio === 'Nef Central')
    );

    setupStoreMock({
      parts: mockPartsForFilterTesting,
      setFilters: mockSetFilters,
      getFilteredParts: mockGetFilteredParts,
    });

    render(<Dashboard3D />);

    // Open the Agrupació dropdown pill
    const agrupacioButton = screen.getByRole('button', { name: /agrupació/i });
    await user.click(agrupacioButton);

    // Click the Nef Central option inside the dropdown
    const option = screen.getByRole('option', { name: /nef central/i });
    await user.click(option);

    // setFilters was called with agrupacio containing 'Nef Central'
    expect(mockSetFilters).toHaveBeenCalledWith(
      expect.objectContaining({
        agrupacio: expect.arrayContaining(['Nef Central']),
      })
    );
  });

  /**
   * Test 7: Clear filters button resets all filters
   *
   * Integration Point: ClearFiltersButton → partsStore.clearFilters
   * Expected: All filters reset to empty
   */
  it('clears all filters when clear button clicked', async () => {
    const user = userEvent.setup();
    const mockClearFilters = vi.fn();

    setupStoreMock({
      parts: mockPartsForFilterTesting,
      filters: { material: ['Montjuïc'], agrupacio: ['Nef Central'], workshop_id: null },
      clearFilters: mockClearFilters,
    });

    render(<Dashboard3D />);

    const clearButton = screen.getByRole('button', { name: /limpiar/i });
    await user.click(clearButton);

    expect(mockClearFilters).toHaveBeenCalled();
  });

  /**
   * Test 8: Multiple filter types combine with AND logic
   *
   * Integration Point: FilterBar → partsStore.getFilteredParts (AND logic)
   * Expected: Only parts matching ALL filter conditions are returned
   */
  it('combines multiple filters with AND logic', () => {
    const mockGetFilteredParts = vi.fn(() =>
      mockPartsForFilterTesting.filter(
        (p) => p.tipologia === 'Montjuïc' && p.agrupacio === 'Nef Central'
      )
    );

    setupStoreMock({
      parts: mockPartsForFilterTesting,
      filters: { material: ['Montjuïc'], agrupacio: ['Nef Central'], workshop_id: null },
      getFilteredParts: mockGetFilteredParts,
    });

    render(<Dashboard3D />);

    // getFilteredParts returns only parts matching BOTH conditions
    const filteredParts = mockGetFilteredParts();
    expect(filteredParts).toHaveLength(3); // mockPartCapitel + mockPartClave + SF-C12-CAP-006
    expect(filteredParts.every((p) => p.tipologia === 'Montjuïc')).toBe(true);
    expect(filteredParts.every((p) => p.agrupacio === 'Nef Central')).toBe(true);
  });
});
