/**
 * useURLFilters Hook
 * 
 * T-0506-FRONT: URL params synchronization with Zustand store
 * 
 * @module useURLFilters
 */

import { useEffect } from 'react';
import { usePartsStore } from '@/stores/parts.store';
import type { PartsFilters } from '@/stores/parts.store';
import { FILTER_URL_PARAMS } from '@/constants/parts.constants';

/**
 * Build URL query string from filters object
 */
function buildFilterURLString(filters: PartsFilters): string {
  const parts: string[] = [];

  if (filters.material.length > 0) {
    parts.push(
      `${FILTER_URL_PARAMS.MATERIAL}=${filters.material.join(FILTER_URL_PARAMS.SEPARATOR)}`
    );
  }

  if (filters.agrupacio.length > 0) {
    parts.push(
      `${FILTER_URL_PARAMS.AGRUPACIO}=${filters.agrupacio.join(FILTER_URL_PARAMS.SEPARATOR)}`
    );
  }

  if (filters.workshop_id) {
    parts.push(`${FILTER_URL_PARAMS.WORKSHOP}=${filters.workshop_id}`);
  }

  return parts.length > 0 ? `?${parts.join('&')}` : window.location.pathname;
}

/**
 * Parse URL params into filters object
 */
function parseURLToFilters(searchParams: URLSearchParams): PartsFilters {
  const materialParam = searchParams.get(FILTER_URL_PARAMS.MATERIAL);
  const agrupacioParam = searchParams.get(FILTER_URL_PARAMS.AGRUPACIO);
  const workshopParam = searchParams.get(FILTER_URL_PARAMS.WORKSHOP);

  return {
    material: materialParam ? materialParam.split(FILTER_URL_PARAMS.SEPARATOR) : [],
    agrupacio: agrupacioParam ? agrupacioParam.split(FILTER_URL_PARAMS.SEPARATOR) : [],
    tipologia: [],
    status: [],
    workshop_id: workshopParam || null,
  };
}

/**
 * useURLFilters: Bidirectional sync between URL params and store filters
 * 
 * On mount: Reads URL params → setFilters()
 * On store change: Updates URL with window.history.replaceState()
 * 
 * URL encoding:
 * - Arrays: comma-separated (status=validated,uploaded)
 * - Single values: plain string (workshop_id=uuid)
 * - Empty arrays: param omitted from URL
 * 
 * @example
 * ```tsx
 * function Dashboard() {
 *   useURLFilters(); // Auto-sync filters
 *   return <Canvas3D />;
 * }
 * ```
 */
export function useURLFilters() {
  const { filters, setFilters } = usePartsStore();

  // URL → Store (on mount only)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlFilters = parseURLToFilters(params);
    setFilters(urlFilters);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Store → URL (reactive)
  useEffect(() => {
    const queryString = buildFilterURLString(filters);
    window.history.replaceState({}, '', queryString);
  }, [filters]);
}
