/**
 * Parts Service - API Layer (DEPRECATED - Uses Elements API)
 * 
 * NOTE: This service now calls /api/elements endpoint but maintains
 * backward compatibility by converting Element → PartCanvasItem
 * 
 * TODO: Migrate codebase to use elements.service.ts directly
 */

import axios from 'axios';
import type { PartCanvasItem } from '@/types/parts';

/**
 * Base URL for backend API calls.
 * In dev: '' → Vite proxy handles /api/* → http://backend:8000
 * In prod: VITE_API_URL → https://sf-pm-backend.up.railway.app
 */
const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * API endpoint for fetching elements (replaces /api/parts)
 */
const ELEMENTS_ENDPOINT = `${API_BASE}/api/elements`;

/**
 * Fetch all parts from backend (now using /api/elements)
 * 
 * @param filters - Optional filters (status, material_type)
 * @returns Promise resolving to parts array
 * 
 * @throws {Error} If backend request fails
 * 
 * @example
 * ```typescript
 * const parts = await listParts({ status: 'validated' });
 * console.log(`Found ${parts.length} validated parts`);
 * ```
 */
export async function listParts(
  filters?: Record<string, string | string[] | null | undefined>
): Promise<PartCanvasItem[]> {
  // Call /api/elements instead of /api/parts
  const response = await axios.get(ELEMENTS_ENDPOINT, {
    params: filters,
  });

  // Convert ElementsListResponse to PartCanvasItem[] for backward compatibility
  const elementsResponse = response.data;
  
  // Map Element → PartCanvasItem (add missing fields with defaults)
  const parts: PartCanvasItem[] = elementsResponse.elements.map((element: any) => ({
    id: element.id,
    iso_code: element.iso_code,
    status: element.status,
    tipologia: element.material_type, // Map material_type → tipologia for backward compat
    low_poly_url: element.low_poly_url,
    bbox: element.bbox,
    workshop_id: null, // Elements don't have workshop_id
    workshop_name: null, // Elements don't have workshop_name
  }));

  return parts;
}
