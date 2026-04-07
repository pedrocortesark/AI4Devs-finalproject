/**
 * FilePreviewPanel — Unit Tests
 * Covers badge logic, button states, and callbacks.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilePreviewPanel } from './FilePreviewPanel';
import type { FilePreviewResponse, BlockPreview } from '../types/preview';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeBlock(overrides: Partial<BlockPreview> = {}): BlockPreview {
  return {
    name: 'SF-NAV-CO-001',
    is_instance_object: true,
    has_metadata: true,
    codi: 'SF-NAV-CO-001',
    material: 'Montjuïc',
    iso_valid: true,
    iso_issues: [],
    user_strings: {},
    already_exists: false,
    ...overrides,
  };
}

function makePreview(overrides: Partial<FilePreviewResponse> = {}): FilePreviewResponse {
  const blocks = overrides.blocks ?? [makeBlock()];
  return {
    filename: 'test.3dm',
    total_blocks: blocks.length,
    valid_blocks: blocks.filter(
      (b) => b.is_instance_object && b.iso_valid && b.has_metadata && !b.already_exists
    ).length,
    invalid_blocks: blocks.filter(
      (b) => !b.already_exists && (!b.is_instance_object || !b.iso_valid || !b.has_metadata)
    ).length,
    duplicate_blocks: blocks.filter((b) => b.already_exists).length,
    blocks,
    ...overrides,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('FilePreviewPanel', () => {
  it('renders filename in summary bar', () => {
    render(
      <FilePreviewPanel
        preview={makePreview({ filename: 'myfab.3dm' })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText('myfab.3dm')).toBeDefined();
  });

  it('shows total block count', () => {
    const blocks = [makeBlock(), makeBlock({ name: 'SF-NAV-CO-002' })];
    render(
      <FilePreviewPanel
        preview={makePreview({ blocks })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText(/2 bloques/)).toBeDefined();
  });

  it('enables "Subir archivo" when valid_blocks > 0', () => {
    render(
      <FilePreviewPanel
        preview={makePreview()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    const btn = screen.getByRole('button', { name: /subir archivo/i });
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('disables "Subir archivo" when valid_blocks === 0', () => {
    render(
      <FilePreviewPanel
        preview={makePreview({ valid_blocks: 0 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    const btn = screen.getByRole('button', { name: /subir archivo/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('disables "Subir archivo" when isUploading is true', () => {
    render(
      <FilePreviewPanel
        preview={makePreview()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        isUploading
      />
    );
    const btn = screen.getByRole('button', { name: /subiendo/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('calls onCancel when Cancelar button is clicked', () => {
    const onCancel = vi.fn();
    render(
      <FilePreviewPanel
        preview={makePreview()}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('calls onConfirm when Subir button is clicked', () => {
    const onConfirm = vi.fn();
    render(
      <FilePreviewPanel
        preview={makePreview()}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /subir archivo/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it('shows "Válido" badge for fully valid block', () => {
    render(
      <FilePreviewPanel
        preview={makePreview()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText('Válido')).toBeDefined();
  });

  it('shows "Ya existía" badge for duplicate block', () => {
    const blocks = [makeBlock({ already_exists: true })];
    render(
      <FilePreviewPanel
        preview={makePreview({ blocks, valid_blocks: 0, duplicate_blocks: 1 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText('Ya existía')).toBeDefined();
  });

  it('shows "Sin metadata" badge for block missing metadata', () => {
    const blocks = [makeBlock({ has_metadata: false, codi: null, material: null })];
    render(
      <FilePreviewPanel
        preview={makePreview({ blocks, valid_blocks: 0, invalid_blocks: 1 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText('Sin metadata')).toBeDefined();
  });

  it('shows "Inválido" badge for block with invalid ISO name', () => {
    const blocks = [makeBlock({ iso_valid: false, iso_issues: ['bad name'] })];
    render(
      <FilePreviewPanel
        preview={makePreview({ blocks, valid_blocks: 0, invalid_blocks: 1 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText('Inválido')).toBeDefined();
  });

  it('shows ISO issue message below block name', () => {
    const blocks = [makeBlock({ iso_valid: false, iso_issues: ['bad name pattern'] })];
    render(
      <FilePreviewPanel
        preview={makePreview({ blocks, valid_blocks: 0, invalid_blocks: 1 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText(/bad name pattern/)).toBeDefined();
  });

  it('shows warning when no valid blocks exist', () => {
    render(
      <FilePreviewPanel
        preview={makePreview({ valid_blocks: 0 })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText(/No hay bloques válidos/)).toBeDefined();
  });
});
