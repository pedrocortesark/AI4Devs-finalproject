/**
 * DetailsPanel Constants
 *
 * UI configuration for the sliding details side-panel.
 * Design system: shared dark "DS" language (Apple-inspired) — mirrors
 * src/styles/designTokens.ts so the panel matches the canvas dashboard.
 *
 * @module details/DetailsPanel.constants
 */

// ─── Tab Configuration ────────────────────────────────────────────────────────

export type TabId = 'general' | 'geometry' | 'metadata' | 'raw';

export interface TabConfig {
  label: string;
  icon: string;
}

export const TAB_CONFIG: Record<TabId, TabConfig> = {
  general:  { label: 'General',   icon: '◉' },
  geometry: { label: 'Geometría', icon: '⬡' },
  metadata: { label: 'Metadata',  icon: '{}' },
  raw:      { label: 'JSON',      icon: '</>' },
};

export const TAB_ORDER: TabId[] = ['general', 'geometry', 'metadata', 'raw'];

// ─── Color Palette ────────────────────────────────────────────────────────────

export const COLORS = {
  primary:        '#007AFF',
  primaryLight:   'rgba(0, 122, 255, 0.12)',
  secondary:      'rgba(255, 255, 255, 0.92)',
  background:     '#1C1C1E',
  surface:        '#2C2C2E',
  border:         'rgba(255, 255, 255, 0.08)',
  text:           'rgba(255, 255, 255, 0.92)',
  textSecondary:  'rgba(255, 255, 255, 0.5)',
  textMuted:      'rgba(255, 255, 255, 0.3)',
  error:          '#FF453A',
  errorLight:     'rgba(255, 69, 58, 0.12)',
  warning:        '#FF9F0A',
  warningLight:   'rgba(255, 159, 10, 0.12)',
  success:        '#34C759',
  successLight:   'rgba(52, 199, 89, 0.12)',
  info:           '#007AFF',
  infoLight:      'rgba(0, 122, 255, 0.12)',
} as const;

// ─── Status Badge Colors ──────────────────────────────────────────────────────

export interface StatusStyle {
  background: string;
  color: string;
  border: string;
}

export const STATUS_BADGE_STYLES: Record<string, StatusStyle> = {
  validated:        { background: COLORS.successLight, color: COLORS.success,  border: 'rgba(52, 199, 89, 0.35)' },
  error_processing: { background: COLORS.errorLight,   color: COLORS.error,    border: 'rgba(255, 69, 58, 0.35)' },
  processing:       { background: COLORS.warningLight, color: COLORS.warning,  border: 'rgba(255, 159, 10, 0.35)' },
  uploaded:         { background: COLORS.infoLight,    color: COLORS.primary,  border: 'rgba(0, 122, 255, 0.35)' },
  in_fabrication:   { background: COLORS.warningLight, color: COLORS.warning,  border: 'rgba(255, 159, 10, 0.35)' },
  completed:        { background: COLORS.successLight, color: COLORS.success,  border: 'rgba(52, 199, 89, 0.35)' },
  rejected:         { background: COLORS.errorLight,   color: COLORS.error,    border: 'rgba(255, 69, 58, 0.35)' },
  archived:         { background: 'rgba(255, 255, 255, 0.06)', color: COLORS.textSecondary, border: 'rgba(255, 255, 255, 0.12)' },
};

export const DEFAULT_STATUS_STYLE: StatusStyle = {
  background: COLORS.surface,
  color:      COLORS.textSecondary,
  border:     COLORS.border,
};

// ─── Dimensions ───────────────────────────────────────────────────────────────

export const PANEL = {
  width:         '400px',
  viewer3dHeight: '300px',
  zIndex:        500,
  shadow:        '-2px 0 12px rgba(0,0,0,0.15)',
  headerHeight:  '52px',
  tabBarHeight:  '42px',
} as const;

// ─── Rhino Metadata Highlighted Keys ─────────────────────────────────────────

export const RHINO_HIGHLIGHT_KEYS = [
  'SF_GEN_Material',
  'SF_GEN_GrauEstructural',
  'SF_GEN_Volum_m3',
  'SF_GEN_Pes_t',
] as const;

// ─── ARIA Labels ──────────────────────────────────────────────────────────────

export const ARIA = {
  PANEL:        'Panel de detalles de pieza',
  CLOSE_BUTTON: 'Cerrar panel de detalles',
  TAB_LIST:     'Pestañas de información',
  COPY_JSON:    'Copiar JSON al portapapeles',
} as const;
