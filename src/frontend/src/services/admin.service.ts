export interface ResetBlocksResponse {
  deleted_blocks: number;
  cleared_storage: boolean;
}

/**
 * Delete all blocks and clear Storage buckets (development only).
 * The backend returns 403 in production environments.
 */
export async function resetBlocks(): Promise<ResetBlocksResponse> {
  const response = await fetch('/api/admin/reset-blocks', {
    method: 'DELETE',
  });

  if (!response.ok) {
    let detail = `Reset failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }

  return response.json() as Promise<ResetBlocksResponse>;
}
