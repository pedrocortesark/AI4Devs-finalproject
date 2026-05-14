/**
 * DetailsPanel Component Tests
 *
 * Covers:
 * - Panel visibility (open / closed CSS classes)
 * - No-selection state
 * - Loading state
 * - Tab switching
 * - Close button / Escape key
 * - JSON Raw copy button presence
 *
 * @module details/DetailsPanel.test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DetailsPanel } from './DetailsPanel';
import type { PartDetail, BlockStatus } from '@/types/parts';

// ─── Mocks ───────────────────────────────────────────────────────────────────

// Mock usePartDetail hook (lives in Dashboard folder, unrelated to this component)
vi.mock('@/components/Dashboard/PartDetailModal.hooks', () => ({
  usePartDetail: vi.fn(),
}));

// Mock PartViewer3D — Three.js canvas doesn't work in jsdom
vi.mock('./PartViewer3D', () => ({
  PartViewer3D: () => <div data-testid="part-viewer-3d-mock" />,
}));

import { usePartDetail } from '@/components/Dashboard/PartDetailModal.hooks';
const mockUsePartDetail = usePartDetail as ReturnType<typeof vi.fn>;

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_PART: PartDetail = {
  id: 'abc-123',
  iso_code: 'SF-C12-D-001',
  status: 'validated' as BlockStatus,
  tipologia: 'capitel',
  created_at: '2026-03-11T10:00:00Z',
  low_poly_url: 'https://cdn.example.com/part.obj',
  bbox: { min: [0, 0, 0], max: [1, 2, 3] },
  workshop_id: 'ws-1',
  workshop_name: 'Taller A',
  validation_report: null,
  glb_size_bytes: null,
  triangle_count: null,
  material_type: 'Montjuïc',
  rhino_metadata: { SF_GEN_Material: 'Montjuïc', SF_GEN_Pes_t: '1.2' },
};

function idleHook(): ReturnType<typeof usePartDetail> {
  return { partData: MOCK_PART, loading: false, error: null, retry: vi.fn() } as any;
}

function loadingHook(): ReturnType<typeof usePartDetail> {
  return { partData: null, loading: true, error: null, retry: vi.fn() } as any;
}

function errorHook(): ReturnType<typeof usePartDetail> {
  return { partData: null, loading: false, error: new Error('Network error'), retry: vi.fn() } as any;
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('DetailsPanel', () => {
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePartDetail.mockReturnValue(idleHook());
  });

  // ─── Panel visibility ───────────────────────────────────────────────────────

  it('applies panelOpen class when isOpen=true', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    const panel = screen.getByTestId('details-panel');
    expect(panel.className).toMatch(/panelOpen/);
  });

  it('applies panelClosed class when isOpen=false', () => {
    render(<DetailsPanel partId="abc-123" isOpen={false} onClose={onClose} />);
    const panel = screen.getByTestId('details-panel');
    expect(panel.className).toMatch(/panelClosed/);
  });

  // ─── No-selection state ─────────────────────────────────────────────────────

  it('shows no-selection state when partId is null', () => {
    render(<DetailsPanel partId={null} isOpen={true} onClose={onClose} />);
    expect(screen.getByText(/selecciona una pieza/i)).toBeInTheDocument();
  });

  it('does not render tabs when partId is null', () => {
    render(<DetailsPanel partId={null} isOpen={true} onClose={onClose} />);
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  });

  // ─── Loading state ──────────────────────────────────────────────────────────

  it('shows loading message while data is loading', () => {
    mockUsePartDetail.mockReturnValue(loadingHook());
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    expect(screen.getByText(/cargando pieza/i)).toBeInTheDocument();
  });

  // ─── Error state ────────────────────────────────────────────────────────────

  it('shows error message when fetch fails', () => {
    mockUsePartDetail.mockReturnValue(errorHook());
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    expect(screen.getByText(/no se pudieron cargar los datos/i)).toBeInTheDocument();
  });

  // ─── Tab switching ──────────────────────────────────────────────────────────

  it('renders 4 tabs when partId is set', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(4);
  });

  it('General tab is active by default', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    const generalTab = screen.getByRole('tab', { name: /general/i });
    expect(generalTab).toHaveAttribute('aria-selected', 'true');
  });

  it('shows iso_code in General tab', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    // iso_code appears in both header and General tab content
    expect(screen.getAllByText('SF-C12-D-001').length).toBeGreaterThan(0);
  });

  it('switches to Geometría tab and shows bbox section', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    fireEvent.click(screen.getByRole('tab', { name: /geometría/i }));
    expect(screen.getByText(/bounding box/i)).toBeInTheDocument();
  });

  it('switches to JSON tab and shows Copy button', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    fireEvent.click(screen.getByRole('tab', { name: /json/i }));
    expect(screen.getByRole('button', { name: /copiar json/i })).toBeInTheDocument();
  });

  // ─── Close button ───────────────────────────────────────────────────────────

  it('calls onClose when close button is clicked', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText(/cerrar panel/i));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // ─── Escape key ─────────────────────────────────────────────────────────────

  it('calls onClose when Escape key is pressed and panel is open', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not call onClose on Escape when panel is closed', () => {
    render(<DetailsPanel partId="abc-123" isOpen={false} onClose={onClose} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
  });

  // ─── Header title ───────────────────────────────────────────────────────────

  it('shows iso_code in header when data is loaded', () => {
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    // iso_code appears in both header and General tab — at least one present
    expect(screen.getAllByText('SF-C12-D-001').length).toBeGreaterThan(0);
  });

  it('shows loading text in header when data is loading', () => {
    mockUsePartDetail.mockReturnValue(loadingHook());
    render(<DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />);
    // Both header ("Cargando…") and content ("Cargando pieza…") may match — at least one present
    expect(screen.getAllByText(/cargando/i).length).toBeGreaterThan(0);
  });

  // ─── Tab reset on part change ───────────────────────────────────────────────

  it('resets to General tab when partId changes', () => {
    const { rerender } = render(
      <DetailsPanel partId="abc-123" isOpen={true} onClose={onClose} />
    );
    // Switch to JSON tab
    fireEvent.click(screen.getByRole('tab', { name: /json/i }));
    expect(screen.getByRole('tab', { name: /json/i })).toHaveAttribute('aria-selected', 'true');

    // Change part
    rerender(<DetailsPanel partId="xyz-999" isOpen={true} onClose={onClose} />);
    expect(screen.getByRole('tab', { name: /general/i })).toHaveAttribute('aria-selected', 'true');
  });
});
