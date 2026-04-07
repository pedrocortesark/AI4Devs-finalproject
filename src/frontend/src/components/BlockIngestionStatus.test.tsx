/**
 * BlockIngestionStatus — Unit Tests
 * Covers Realtime subscription setup, initial DB fetch, and unmount cleanup.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BlockIngestionStatus } from './BlockIngestionStatus';

// ── Mock supabase client ──────────────────────────────────────────────────────

const mockUnsubscribe = vi.fn();
const mockSubscribe = vi.fn().mockReturnThis();
const mockOn = vi.fn().mockReturnThis();

const mockChannel = {
  on: mockOn,
  subscribe: mockSubscribe,
  unsubscribe: mockUnsubscribe,
};

const mockFrom = vi.fn();

const mockSupabase = {
  from: mockFrom,
  channel: vi.fn().mockReturnValue(mockChannel),
};

vi.mock('../services/supabase.client', () => ({
  getSupabaseClient: () => mockSupabase,
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function setupInitialFetch(rows: any[]) {
  mockFrom.mockReturnValue({
    select: vi.fn().mockReturnValue({
      eq: vi.fn().mockResolvedValue({ data: rows, error: null }),
    }),
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('BlockIngestionStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOn.mockReturnThis();
    mockSubscribe.mockReturnThis();
    mockSupabase.channel.mockReturnValue(mockChannel);
  });

  it('fetches initial blocks on mount and displays them', async () => {
    setupInitialFetch([
      { id: 'block-1', iso_code: 'SF-NAV-CO-001', status: 'uploaded', validation_report: null },
    ]);

    render(<BlockIngestionStatus fileKey="raw-uploads/abc/model.3dm" />);

    await waitFor(() => {
      expect(screen.getByText('SF-NAV-CO-001')).toBeDefined();
    });
  });

  it('displays "Esperando bloques…" when no blocks returned', async () => {
    setupInitialFetch([]);
    render(<BlockIngestionStatus fileKey="raw-uploads/abc/model.3dm" />);

    await waitFor(() => {
      expect(screen.getByText(/Esperando bloques/)).toBeDefined();
    });
  });

  it('creates Realtime channel with correct filter', async () => {
    setupInitialFetch([]);
    render(<BlockIngestionStatus fileKey="raw-uploads/abc/model.3dm" />);

    await waitFor(() => {
      expect(mockSupabase.channel).toHaveBeenCalled();
      expect(mockOn).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          filter: 'url_original=eq.raw-uploads/abc/model.3dm',
          table: 'blocks',
          schema: 'public',
        }),
        expect.any(Function)
      );
    });
  });

  it('calls subscribe on the channel', async () => {
    setupInitialFetch([]);
    render(<BlockIngestionStatus fileKey="raw-uploads/abc/model.3dm" />);

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalled();
    });
  });

  it('unsubscribes channel on unmount', async () => {
    setupInitialFetch([]);
    const { unmount } = render(<BlockIngestionStatus fileKey="raw-uploads/abc/model.3dm" />);

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalled();
    });

    unmount();
    expect(mockUnsubscribe).toHaveBeenCalled();
  });

  it('shows "Subido" badge for uploaded block', async () => {
    setupInitialFetch([
      { id: 'b1', iso_code: 'SF-NAV-CO-001', status: 'uploaded', validation_report: null },
    ]);
    render(<BlockIngestionStatus fileKey="k" />);

    await waitFor(() => {
      expect(screen.getByText('Subido')).toBeDefined();
    });
  });

  it('shows "Validado" badge for validated block', async () => {
    setupInitialFetch([
      { id: 'b1', iso_code: 'SF-NAV-CO-001', status: 'validated', validation_report: null },
    ]);
    render(<BlockIngestionStatus fileKey="k" />);

    await waitFor(() => {
      expect(screen.getByText('Validado')).toBeDefined();
    });
  });

  it('shows "Error" badge and error message for error_processing block', async () => {
    setupInitialFetch([
      {
        id: 'b1',
        iso_code: 'SF-NAV-CO-001',
        status: 'error_processing',
        validation_report: { errors: [{ message: 'Geometry too complex' }] },
      },
    ]);
    render(<BlockIngestionStatus fileKey="k" />);

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeDefined();
      expect(screen.getByText('Geometry too complex')).toBeDefined();
    });
  });

  it('shows "Nueva subida" button when all blocks done and onNewUpload provided', async () => {
    setupInitialFetch([
      { id: 'b1', iso_code: 'SF-NAV-CO-001', status: 'validated', validation_report: null },
    ]);
    const onNewUpload = vi.fn();
    render(<BlockIngestionStatus fileKey="k" onNewUpload={onNewUpload} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /nueva subida/i })).toBeDefined();
    });
  });

  it('does NOT show "Nueva subida" button when blocks still processing', async () => {
    setupInitialFetch([
      { id: 'b1', iso_code: 'SF-NAV-CO-001', status: 'processing', validation_report: null },
    ]);
    render(<BlockIngestionStatus fileKey="k" onNewUpload={vi.fn()} />);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /nueva subida/i })).toBeNull();
    });
  });
});
