/**
 * T-1505-FRONT: Elements Store (replaces parts.store.ts)
 * 
 * Breaking changes:
 * - Renamed: parts → elements
 * - Uses Element type (not PartCanvasItem)
 * - Uses fetchElements service (not fetchParts)
 * - Filters updated: tipologia → material_type
 */

import { create } from 'zustand';
import type { Element } from '../types/elements';
import type { ElementsQueryParams } from '../schemas/elements.schema';
import { fetchElements } from '../services/elements.service';

interface ElementsFilters {
  status?: string;
  material_type?: string;
}

interface ElementsStore {
  elements: Element[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  filters: ElementsFilters;
  
  // Actions
  /**
   * Load elements from API with current filters
   * Sets isLoading/error state and re-throws errors for test compatibility
   */
  loadElements: () => Promise<void>;
  
  /**
   * Select an element by ID (for detail modal)
   * @param id - Element UUID
   */
  selectElement: (id: string) => void;
  
  /** Clear element selection (close modal) */
  clearSelection: () => void;
  
  /**
   * Update filters and auto-reload elements
   * @param filters - New filter values (status, material_type)
   */
  setFilters: (filters: ElementsFilters) => void;
}

/**
 * Elements store with fetchElements integration
 */
export const useElementsStore = create<ElementsStore>((set, get) => ({
  elements: [],
  isLoading: false,
  error: null,
  selectedId: null,
  filters: {},

  loadElements: async () => {
    set({ isLoading: true, error: null });
    try {
      const { filters } = get();
      const response = await fetchElements(filters as ElementsQueryParams);
      set({ elements: response.elements, isLoading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load elements';
      set({ 
        error: errorMessage,
        isLoading: false 
      });
      // Re-throw for test compatibility (ERR-CMP-01 expects rejection)
      throw error;
    }
  },

  selectElement: (id: string) => {
    set({ selectedId: id });
  },

  clearSelection: () => {
    set({ selectedId: null });
  },

  setFilters: (filters: ElementsFilters) => {
    set({ filters });
    // Auto-reload elements when filters change
    get().loadElements();
  },
}));
