/**
 * Parts Store - Zustand State Management
 * 
 * T-0505-FRONT: Global state for 3D parts scene
 * T-0506-FRONT: Added filter functionality
 * 
 * @module parts.store
 */

import { create } from 'zustand';
import { PartCanvasItem } from '@/types/parts';
import { listParts } from '@/services/parts.service';

/**
 * Parts filter structure
 */
export interface PartsFilters {
  material: string[];    // Filter by material_type (Montjuïc, Ulldecona, etc.)
  agrupacio: string[];   // Filter by SF_ARC_Agrupacio1 Rhino metadata key
  tipologia: string[];   // Filter by tipologia (capitel, columna, dovela, etc.)
  status: string[];      // Filter by status (validated, uploaded, etc.)
  workshop_id: string | null;
  [key: string]: string | string[] | null | undefined;  // Index signature for Record compatibility (allows undefined from Partial)
}

/**
 * Parts store state interface
 */
interface PartsState {
  /** Array of all parts */
  parts: PartCanvasItem[];
  
  /** Active filters */
  filters: PartsFilters;
  
  /** Currently selected part ID */
  selectedId: string | null;
  
  /** Loading state */
  isLoading: boolean;
  
  /** Error message if fetch fails */
  error: string | null;
  
  /** Fetch parts from API. Pass silent=true to skip the loading indicator (background polls). */
  fetchParts: (silent?: boolean) => Promise<void>;
  
  /** Update filters (partial merge) */
  setFilters: (filters: Partial<PartsFilters>) => void;
  
  /** Clear all filters */
  clearFilters: () => void;
  
  /** Get filtered parts based on current filters */
  getFilteredParts: () => PartCanvasItem[];
  
  /** Select a part by ID */
  selectPart: (id: string) => void;
  
  /** Clear selection */
  clearSelection: () => void;
}

/**
 * Zustand store for parts management
 * 
 * @example
 * ```typescript
 * const { parts, fetchParts, selectPart, setFilters } = usePartsStore();
 * 
 * useEffect(() => {
 *   fetchParts();
 * }, []);
 * 
 * const handleClick = (id: string) => {
 *   selectPart(id);
 * };
 * 
 * const handleFilter = () => {
 *   setFilters({ tipologia: ['capitel'] });
 * };
 * ```
 */
export const usePartsStore = create<PartsState>((set, get) => ({
  parts: [],
  filters: {
    material: [],
    agrupacio: [],
    tipologia: [],
    status: [],
    workshop_id: null,
  },
  selectedId: null,
  isLoading: false,
  error: null,

  fetchParts: async (silent = false) => {
    if (!silent) set({ isLoading: true, error: null });

    try {
      const parts = await listParts(get().filters);
      // Skip store update if data is structurally identical to avoid
      // unnecessary re-renders in Canvas3D / PartsScene (re-render cascade).
      const current = get().parts;
      const unchanged =
        current.length === parts.length &&
        current.every((p, i) => p.id === parts[i].id && p.status === parts[i].status && p.low_poly_url === parts[i].low_poly_url);
      if (unchanged) {
        if (!silent) set({ isLoading: false });
      } else {
        set({ parts, isLoading: false });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch parts';
      if (!silent) set({ error: errorMessage, isLoading: false });
    }
  },

  setFilters: (newFilters) => {
    const currentFilters = get().filters;
    set({ 
      filters: {
        ...currentFilters,
        ...newFilters,
      }
    });
    // Don't auto-refetch for now (tests just check state update)
  },

  clearFilters: () => {
    set({
      filters: {
        material: [],
        agrupacio: [],
        tipologia: [],
        status: [],
        workshop_id: null,
      }
    });
  },

  getFilteredParts: () => {
    const { parts, filters } = get();

    return parts.filter(part => {
      // Apply material filter (OR logic) — filters by material_type via tipologia field
      if (filters.material.length > 0 && !filters.material.includes(part.tipologia)) {
        return false;
      }

      // Apply agrupacio filter (OR logic) — filters by SF_ARC_Agrupacio1
      if (filters.agrupacio.length > 0 && (part.agrupacio === null || !filters.agrupacio.includes(part.agrupacio))) {
        return false;
      }

      // Apply tipologia filter (OR logic)
      if (filters.tipologia && filters.tipologia.length > 0 && !filters.tipologia.includes(part.tipologia)) {
        return false;
      }

      // Apply status filter (OR logic)
      if (filters.status && filters.status.length > 0 && !filters.status.includes(part.status)) {
        return false;
      }

      // Apply workshop_id filter
      if (filters.workshop_id && part.workshop_id !== filters.workshop_id) {
        return false;
      }

      return true;
    });
  },

  selectPart: (id) => {
    set({ selectedId: id });
  },

  clearSelection: () => {
    set({ selectedId: null });
  },
}));
