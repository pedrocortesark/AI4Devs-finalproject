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
  // US-015: Include all 3 LOD URLs (high_poly, mid_poly, low_poly)
  const parts: PartCanvasItem[] = elementsResponse.elements.map((element: any) => ({
    id: element.id,
    iso_code: element.iso_code,
    status: element.status,
    tipologia: element.material_type, // Map material_type → tipologia for backward compat
    agrupacio: element.agrupacio ?? null, // SF_ARC_Agrupacio1 from Rhino metadata
    high_poly_url: element.high_poly_url || null,  // US-015: High-detail LOD (~7k tris)
    mid_poly_url: element.mid_poly_url || null,    // US-015: Mid-detail LOD (~2k tris)
    low_poly_url: element.low_poly_url,             // US-015: Low-detail LOD (~500 tris)
    mtl_url: element.mtl_url || null,              // Per-face Rhino layer colors
    bbox: element.bbox,
    workshop_id: null, // Elements don't have workshop_id
    workshop_name: null, // Elements don't have workshop_name
  }));

  return parts;
}
