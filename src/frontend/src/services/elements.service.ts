/**
 * T-1505-FRONT: Element API Service
 * 
 * Purpose: Service layer for Element API endpoints with Zod validation
 * Pattern: 
 * - All API calls isolated here (not in components)
 * - Zod schema validation on responses (fail-fast on contract mismatch)
 * - Error handling with typed exceptions
 * 
 * Endpoints:
 * - GET /api/elements → fetch all elements matching filters
 * - GET /api/elements/{id} → fetch element detail
 * - GET /api/elements/{id}/navigation → fetch prev/next IDs
 */

import { 
  ElementsListResponseSchema,
  ElementDetailSchema,
  ElementNavigationResponseSchema,
  type ElementsListResponse,
  type ElementDetail,
  type ElementNavigationResponse,
  type ElementsQueryParams,
} from '../schemas/elements.schema';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Error thrown when Element API call fails
 */
export class ElementApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: unknown
  ) {
    super(message);
    this.name = 'ElementApiError';
  }
}

/**
 * Fetch elements list with optional filters
 * 
 * @param params - Query parameters (status, material_type)
 * @returns Validated ElementsListResponse
 * @throws ElementApiError if request fails or validation fails
 * 
 * @example
 * const response = await fetchElements({ status: "validated" });
 * console.log(response.elements); // Array of Element objects
 */
export async function fetchElements(
  params?: ElementsQueryParams
): Promise<ElementsListResponse> {
  try {
    // Build query string from params
    const queryParams = new URLSearchParams();
    if (params?.status) {
      queryParams.append('status', params.status);
    }
    // material_type filter was removed from the model/API (commit 2a702b9);
    // the elements list endpoint only filters by status.
    const queryString = queryParams.toString();
    const url = `${API_BASE_URL}/api/elements${queryString ? `?${queryString}` : ''}`;

    // Fetch data
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new ElementApiError(
        `Failed to fetch elements: ${response.statusText}`,
        response.status
      );
    }

    const data = await response.json();

    // Validate with Zod schema
    return ElementsListResponseSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      'Failed to fetch elements',
      undefined,
      error
    );
  }
}

/**
 * Fetch element detail by ID
 * 
 * @param id - Element UUID
 * @returns Validated ElementDetail
 * @throws ElementApiError if element not found or validation fails
 * 
 * @example
 * const detail = await fetchElementDetail('550e8400-e29b-41d4-a716-446655440000');
 * console.log(detail.material_type); // "Montjuïc"
 */
export async function fetchElementDetail(id: string): Promise<ElementDetail> {
  try {
    const url = `${API_BASE_URL}/api/elements/${id}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new ElementApiError(
          `Element not found: ${id}`,
          404
        );
      }
      throw new ElementApiError(
        `Failed to fetch element detail: ${response.statusText}`,
        response.status
      );
    }

    const data = await response.json();

    // Validate with Zod schema
    return ElementDetailSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      `Failed to fetch element detail for ${id}`,
      undefined,
      error
    );
  }
}

/**
 * Fetch element navigation (prev/next IDs)
 * 
 * @param id - Current element UUID
 * @returns Validated ElementNavigationResponse
 * @throws ElementApiError if request fails or validation fails
 * 
 * @example
 * const nav = await fetchElementNavigation('550e8400-e29b-41d4-a716-446655440000');
 * console.log(nav.next_id); // Next element UUID or null
 */
export async function fetchElementNavigation(
  id: string
): Promise<ElementNavigationResponse> {
  try {
    const url = `${API_BASE_URL}/api/elements/${id}/navigation`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new ElementApiError(
        `Failed to fetch element navigation: ${response.statusText}`,
        response.status
      );
    }

    const data = await response.json();

    // Validate with Zod schema
    return ElementNavigationResponseSchema.parse(data);
  } catch (error) {
    if (error instanceof ElementApiError) {
      throw error;
    }
    throw new ElementApiError(
      `Failed to fetch element navigation for ${id}`,
      undefined,
      error
    );
  }
}
