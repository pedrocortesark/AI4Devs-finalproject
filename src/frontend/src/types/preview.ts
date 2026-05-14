// Types for US-020: Preview, ingestion status, and reset

export interface BlockPreview {
  name: string;
  is_instance_object: boolean;
  has_metadata: boolean;
  codi: string | null;
  material: string | null;
  iso_valid: boolean;
  iso_issues: string[];
  user_strings: Record<string, string>;
  already_exists: boolean;
}

export interface FilePreviewResponse {
  filename: string;
  total_blocks: number;
  valid_blocks: number;
  invalid_blocks: number;
  duplicate_blocks: number;
  blocks: BlockPreview[];
}

/** Per-block ingestion state tracked in real time via Supabase Realtime. */
export type BlockIngestionState =
  | 'uploaded'
  | 'processing'
  | 'validated'
  | 'error_processing'
  | 'rejected'
  | 'skipped'
  | 'pending';

export interface BlockIngestionRow {
  id: string;
  iso_code: string;
  state: BlockIngestionState;
  error_reason?: string;
  skipped: boolean;
  // Validation step
  validation_report?: {
    is_valid: boolean;
    validated_at?: string;
    errors?: Array<{ category: string; message: string }>;
  } | null;
  // Geometry pipeline
  high_poly_url?: string | null;
  mid_poly_url?: string | null;
  low_poly_url?: string | null;
  // Timing
  created_at?: string;
  updated_at?: string;
}

export interface IngestionSummary {
  total: number;
  completed: number;   // state === 'validated'
  processing: number;  // state === 'processing' | 'uploaded'
  failed: number;      // state === 'error_processing' | 'rejected'
  skipped: number;     // state === 'skipped'
  rows: BlockIngestionRow[];
}
