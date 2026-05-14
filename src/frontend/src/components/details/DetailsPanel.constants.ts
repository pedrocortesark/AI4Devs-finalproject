/**
 * DetailsPanel Constants
 *
 * UI configuration for the sliding details side-panel.
 * Design system: material-inspired, dark-on-light, enterprise dashboard style.
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
  primary:        '#1976d2',
  primaryLight:   '#e3f2fd',
  secondary:      '#424242',
  background:     '#ffffff',
  surface:        '#f5f5f5',
  border:         '#e0e0e0',
  text:           '#212121',
  textSecondary:  '#757575',
  textMuted:      '#9e9e9e',
  error:          '#d32f2f',
  errorLight:     '#ffebee',
  warning:        '#ffa726',
  warningLight:   '#fff3e0',
  success:        '#388e3c',
  successLight:   '#e8f5e9',
  info:           '#1976d2',
  infoLight:      '#e3f2fd',
} as const;

// ─── Status Badge Colors ──────────────────────────────────────────────────────

export interface StatusStyle {
  background: string;
  color: string;
  border: string;
}

export const STATUS_BADGE_STYLES: Record<string, StatusStyle> = {
  validated:        { background: COLORS.successLight, color: COLORS.success,  border: '#a5d6a7' },
  error_processing: { background: COLORS.errorLight,   color: COLORS.error,    border: '#ef9a9a' },
  processing:       { background: COLORS.warningLight, color: '#e65100',       border: '#ffcc02' },
  uploaded:         { background: COLORS.infoLight,    color: COLORS.primary,  border: '#90caf9' },
  in_fabrication:   { background: '#e8eaf6',           color: '#3949ab',       border: '#9fa8da' },
  completed:        { background: '#e0f2f1',           color: '#00695c',       border: '#80cbc4' },
  rejected:         { background: '#fce4ec',           color: '#c62828',       border: '#f48fb1' },
  archived:         { background: '#f5f5f5',           color: '#616161',       border: '#bdbdbd' },
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
