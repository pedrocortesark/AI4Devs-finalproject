/**
 * T-1008-FRONT: PartMetadataPanel Constants
 * Configuration constants for metadata display
 * 
 * @module components/Dashboard/PartMetadataPanel.constants
 */

import type { SectionConfig, SectionId } from './PartMetadataPanel.types';
import { DS, STATUS_TONE } from '@/styles/designTokens';

/**
 * Default values for component props
 */
export const DEFAULTS = {
  INITIAL_EXPANDED_SECTION: 'info' as SectionId,
} as const;

/**
 * Empty value placeholders
 */
export const EMPTY_VALUES = {
  NO_ASSIGNED: 'No asignado',
  NO_DATA: 'Sin datos',
  NOT_AVAILABLE: 'N/A',
  NO_VALIDATION: 'Sin reporte de validación disponible',
} as const;

/**
 * ARIA labels for accessibility
 */
export const ARIA_LABELS = {
  SECTION_BUTTON: (title: string) => `Sección ${title}`,
  SECTION_REGION: (title: string) => `Contenido de ${title}`,
  EXPAND_ICON: 'Expandir/colapsar',
} as const;

/**
 * Section configuration
 * Defines the 4 collapsible sections and their fields
 */
export const SECTIONS_CONFIG: SectionConfig[] = [
  {
    id: 'info',
    title: 'Información',
    icon: 'ℹ️',
    fields: [
      { label: 'Código ISO', key: 'iso_code', component: 'text' },
      { label: 'Tipología', key: 'tipologia', component: 'text' },
      { label: 'Estado', key: 'status', component: 'badge' },
      { label: 'Fecha creación', key: 'created_at', component: 'text' },
      { label: 'ID', key: 'id', component: 'text', monospace: true },
    ],
  },
  {
    id: 'workshop',
    title: 'Taller',
    icon: '🏭',
    fields: [
      { label: 'Nombre', key: 'workshop_name', component: 'text', emptyValue: EMPTY_VALUES.NO_ASSIGNED },
      { label: 'ID Taller', key: 'workshop_id', component: 'text', monospace: true, emptyValue: EMPTY_VALUES.NOT_AVAILABLE },
    ],
  },
  {
    id: 'geometry',
    title: 'Geometría',
    icon: '📐',
    fields: [
      { label: 'Bounding Box', key: 'bbox', component: 'coordinates', emptyValue: EMPTY_VALUES.NO_DATA },
      { label: 'Tamaño archivo', key: 'glb_size_bytes', component: 'text', emptyValue: EMPTY_VALUES.NO_DATA },
      { label: 'Triángulos', key: 'triangle_count', component: 'text', emptyValue: EMPTY_VALUES.NO_DATA },
      { label: 'URL GLB', key: 'low_poly_url', component: 'link', emptyValue: EMPTY_VALUES.NOT_AVAILABLE },
    ],
  },
  {
    id: 'validation',
    title: 'Validación',
    icon: '✅',
    fields: [
      { label: 'Reporte', key: 'validation_report', component: 'json', emptyValue: EMPTY_VALUES.NO_VALIDATION },
    ],
  },
];

/**
 * Inline styles for Portal-safe rendering
 * (Tailwind classes may not apply inside React Portal)
 */
export const SECTION_STYLES = {
  container: {
    padding: '0',
    maxWidth: '100%',
    overflowY: 'auto' as const,
    fontFamily: DS.font,
    color: DS.textPrimary,
  },
  section: {
    marginBottom: '12px',
    border: `1px solid ${DS.borderSubtle}`,
    borderRadius: '12px',
    background: DS.bgSurface,
    overflow: 'hidden',
  },
  sectionLast: {
    marginBottom: '0',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px',
    cursor: 'pointer',
    userSelect: 'none' as const,
  },
  headerTitle: {
    fontSize: '0.9375rem',
    fontWeight: '600' as const,
    color: DS.textPrimary,
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  expandIcon: {
    fontSize: '0.6875rem',
    color: DS.textTertiary,
    transition: 'transform 0.2s',
  },
  expandIconExpanded: {
    transform: 'rotate(90deg)',
  },
  content: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '2px',
    padding: '0 16px 16px',
    borderTop: `1px solid ${DS.borderSubtle}`,
    paddingTop: '12px',
  },
  fieldRow: {
    display: 'grid',
    gridTemplateColumns: '150px 1fr',
    gap: '1rem',
    alignItems: 'baseline',
    padding: '8px 0',
    borderBottom: `1px solid ${DS.borderSubtle}`,
  },
  fieldLabel: {
    fontSize: '0.8125rem',
    fontWeight: '500' as const,
    color: DS.textSecondary,
  },
  fieldValue: {
    fontSize: '0.875rem',
    color: DS.textPrimary,
    wordBreak: 'break-word' as const,
  },
  fieldValueMono: {
    fontFamily: "'SF Mono', 'Monaco', 'Courier New', monospace",
    fontSize: '0.75rem',
    color: DS.textPrimary,
    backgroundColor: DS.bgElevated,
    padding: '0.25rem 0.5rem',
    borderRadius: '6px',
  },
  fieldValueEmpty: {
    color: DS.textTertiary,
    fontStyle: 'italic' as const,
  },
  badge: {
    padding: '0.25rem 0.75rem',
    borderRadius: '9999px',
    fontSize: '0.75rem',
    fontWeight: '500' as const,
    textTransform: 'uppercase' as const,
  },
  link: {
    color: DS.blue,
    textDecoration: 'none',
    wordBreak: 'break-all' as const,
  },
  coordinates: {
    fontFamily: "'SF Mono', 'Monaco', 'Courier New', monospace",
    fontSize: '0.75rem',
    color: DS.textPrimary,
    backgroundColor: DS.bgElevated,
    padding: '0.5rem 0.75rem',
    borderRadius: '6px',
    border: `1px solid ${DS.borderSubtle}`,
  },
  json: {
    fontFamily: "'SF Mono', 'Monaco', 'Courier New', monospace",
    fontSize: '0.75rem',
    color: DS.textSecondary,
    backgroundColor: DS.bgElevated,
    padding: '0.75rem',
    borderRadius: '6px',
    border: `1px solid ${DS.borderSubtle}`,
    overflowX: 'auto' as const,
    maxHeight: '300px',
    overflowY: 'auto' as const,
    whiteSpace: 'pre-wrap' as const,
  },
} as const;

/**
 * Status badge color mapping — derived from the shared DS STATUS_TONE
 * so metadata pills match the canvas dashboard exactly.
 */
export const STATUS_COLORS: Record<string, { backgroundColor: string; color: string }> =
  Object.fromEntries(
    Object.entries(STATUS_TONE).map(([key, tone]) => [
      key,
      { backgroundColor: tone.bg, color: tone.color },
    ]),
  );
