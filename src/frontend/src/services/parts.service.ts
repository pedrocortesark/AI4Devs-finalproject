/**
 * Parts Service - API Layer
 * 
 * T-0501-BACK Contract: GET /api/parts
 * Handles communication with backend parts endpoints
 */

import axios from 'axios';
import type { PartsListResponse, PartCanvasItem } from '@/types/parts';

/**
 * Base URL for backend API calls.
 * In dev: '' → Vite proxy handles /api/* → http://backend:8000
 * In prod: VITE_API_URL → https://sf-pm-backend.up.railway.app
 */
const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * API endpoint for fetching parts list
 */
const PARTS_ENDPOINT = `${API_BASE}/api/parts`;

/**
 * Fetch all parts from backend
 * 
 * @param filters - Optional filters (status, tipologia, workshop_id)
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
  const response = await axios.get<PartsListResponse>(PARTS_ENDPOINT, {
    params: filters,
  });

  return response.data.parts;
}
