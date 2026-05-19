/**
 * Shared design tokens — single source of truth for the canvas/Apple-inspired
 * dark UI language used across the app (Dashboard canvas, upload flow, etc.).
 *
 * Historically the `DS` object was duplicated inline in several components
 * (App.tsx, BlockIngestionStatus.tsx, FilePreviewPanel.tsx, ProgressSteps.tsx,
 * UploadDrawer.tsx). This module is the canonical version; new/restyled
 * components should import from here. (Migrating the legacy inline copies to
 * this module is a safe follow-up, intentionally out of scope here.)
 */

export const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  // Surfaces
  bgCard: '#1C1C1E',
  bgSurface: '#2C2C2E',
  bgElevated: '#3A3A3C',
  overlay: 'rgba(0, 0, 0, 0.6)',
  // Borders
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid: 'rgba(255, 255, 255, 0.14)',
  // Text
  textPrimary: 'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary: 'rgba(255, 255, 255, 0.3)',
  // Accents
  blue: '#007AFF',
  green: '#34C759',
  yellow: '#FF9F0A',
  red: '#FF453A',
} as const;

export type StatusTone = { color: string; bg: string; label: string };

/**
 * Block lifecycle status → DS pill colors + Spanish label.
 * Mirrors STATE_BADGE used in the upload/ingestion UI for consistency.
 */
export const STATUS_TONE: Record<string, StatusTone> = {
  uploaded: { color: DS.blue, bg: 'rgba(0,122,255,0.12)', label: 'Subido' },
  processing: { color: DS.yellow, bg: 'rgba(255,159,10,0.12)', label: 'Procesando' },
  validated: { color: DS.green, bg: 'rgba(52,199,89,0.12)', label: 'Validado' },
  error_processing: { color: DS.red, bg: 'rgba(255,69,58,0.12)', label: 'Error' },
  rejected: { color: DS.red, bg: 'rgba(255,69,58,0.12)', label: 'Rechazado' },
  archived: { color: DS.textSecondary, bg: 'rgba(255,255,255,0.06)', label: 'Archivado' },
  in_fabrication: { color: DS.yellow, bg: 'rgba(255,159,10,0.12)', label: 'En fabricación' },
  completed: { color: DS.green, bg: 'rgba(52,199,89,0.12)', label: 'Completado' },
};

export function statusTone(status: string | null | undefined): StatusTone {
  return (
    (status && STATUS_TONE[status]) || {
      color: DS.textSecondary,
      bg: 'rgba(255,255,255,0.06)',
      label: status ?? '—',
    }
  );
}
