import type { FilePreviewResponse } from '../types/preview';

/**
 * Send a .3dm file to the backend preview endpoint and return per-block analysis.
 * Uses fetch with FormData — browser sets the multipart boundary automatically.
 * Does NOT upload to Storage or write to the database.
 */
export async function previewFile(file: File): Promise<FilePreviewResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/upload/preview', {
    method: 'POST',
    body: formData,
    // Do NOT set Content-Type header — browser must set it with the boundary
  });

  if (!response.ok) {
    let detail = `Preview failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }

  return response.json() as Promise<FilePreviewResponse>;
}
