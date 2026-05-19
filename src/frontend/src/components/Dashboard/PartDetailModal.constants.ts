/**
 * PartDetailModal Constants
 * T-1007-FRONT: Configuration constants for modal integration
 * 
 * @module components/Dashboard/PartDetailModal.constants
 */

import type { TabId } from '@/types/modal';
import { DS } from '@/styles/designTokens';

/**
 * Modal styling constants (inline styles for Portal rendering)
 * 
 * @remarks
 * Uses inline styles (not Tailwind) to ensure styles work in Portal
 * Portal renders outside main React tree, so Tailwind classes may not apply
 */
export const MODAL_STYLES = {
  backdrop: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: DS.overlay,
    backdropFilter: 'blur(2px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999, // T-1007: High z-index to appear above Dashboard (z-100)
  },
  container: {
    backgroundColor: DS.bgCard,
    color: DS.textPrimary,
    fontFamily: DS.font,
    borderRadius: '14px',
    border: `1px solid ${DS.borderMid}`,
    padding: '0',
    width: '90vw',
    maxWidth: '1200px',
    height: '85vh',
    maxHeight: '900px',
    boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6)',
    position: 'relative' as const,
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 24px',
    borderBottom: `1px solid ${DS.borderSubtle}`,
  },
  headerLeft: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  headerTitle: {
    margin: 0,
    fontSize: '1.4rem',
    fontWeight: 600,
    color: DS.textPrimary,
    letterSpacing: '-0.01em',
  },
  headerSubtitle: {
    fontSize: '0.8125rem',
    color: DS.textSecondary,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  navButton: {
    background: DS.bgSurface,
    border: `1px solid ${DS.borderSubtle}`,
    borderRadius: '8px',
    padding: '8px 12px',
    cursor: 'pointer',
    fontSize: '1.125rem',
    color: DS.textSecondary,
    transition: 'background-color 0.2s, color 0.2s',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '40px',
    height: '40px',
  },
  navButtonDisabled: {
    background: 'rgba(255,255,255,0.04)',
    color: DS.textTertiary,
    cursor: 'not-allowed',
  },
  closeButton: {
    background: 'none',
    border: 'none',
    fontSize: '1.6rem',
    cursor: 'pointer',
    padding: '4px 8px',
    color: DS.textSecondary,
    lineHeight: 1,
  },
  tabBar: {
    display: 'flex',
    borderBottom: `1px solid ${DS.borderSubtle}`,
    paddingLeft: '24px',
    paddingRight: '24px',
    backgroundColor: DS.bgCard,
  },
  tabButton: {
    background: 'none',
    border: 'none',
    padding: '12px 20px',
    cursor: 'pointer',
    fontSize: '0.9375rem',
    fontWeight: 500,
    color: DS.textSecondary,
    borderBottom: '2px solid transparent',
    transition: 'all 0.2s',
  },
  tabButtonActive: {
    color: DS.textPrimary,
    borderBottomColor: DS.blue,
  },
  tabContent: {
    flex: 1,
    overflow: 'auto',
    padding: '24px',
    color: DS.textPrimary,
  },
  loadingSpinner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: DS.textSecondary,
    fontSize: '1rem',
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    padding: '24px',
    textAlign: 'center' as const,
  },
  errorIcon: {
    fontSize: '3rem',
    color: DS.red,
    marginBottom: '16px',
  },
  errorTitle: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: DS.textPrimary,
    marginBottom: '8px',
  },
  errorMessage: {
    fontSize: '0.9375rem',
    color: DS.textSecondary,
  },
} as const;

/**
 * Tab configuration (metadata for tab bar rendering)
 */
export const TAB_CONFIG: Record<TabId, { label: string; icon: string }> = {
  viewer: {
    label: 'Visor 3D',
    icon: '🔲', // Cube icon
  },
  metadata: {
    label: 'Metadatos',
    icon: '📋', // Clipboard icon
  },
  validation: {
    label: 'Validación',
    icon: '✓', // Checkmark icon
  },
} as const;

/**
 * Keyboard shortcuts mapping
 */
export const KEYBOARD_SHORTCUTS = {
  CLOSE: 'Escape',
  PREV: 'ArrowLeft',
  NEXT: 'ArrowRight',
  // Legacy support for old browsers
  CLOSE_LEGACY: 'Esc',
} as const;

/**
 * Error messages (user-facing)
 */
export const ERROR_MESSAGES = {
  PART_NOT_FOUND: 'Pieza no encontrada',
  PART_NOT_FOUND_DETAIL: 'La pieza que intentas visualizar no existe o ha sido eliminada.',
  ACCESS_DENIED: 'Acceso denegado',
  ACCESS_DENIED_DETAIL: 'No tienes permisos para ver esta pieza.',
  FETCH_FAILED: 'Error al cargar la pieza',
  FETCH_FAILED_DETAIL: 'No se pudo cargar la información de la pieza. Por favor, intenta nuevamente.',
  NAVIGATION_FAILED: 'Error al navegar',
  NAVIGATION_FAILED_DETAIL: 'No se pudo cargar la información de navegación.',
  TIMEOUT: 'La carga está tardando demasiado',
  TIMEOUT_DETAIL: 'La conexión está tardando más de lo esperado. Por favor, verifica tu conexión a internet e intenta nuevamente.',
  GENERIC_ERROR: 'Error desconocido',
  GENERIC_ERROR_DETAIL: 'Ocurrió un error inesperado. Por favor, cierra el modal e intenta nuevamente.',
} as const;

/**
 * Timeout configuration
 */
export const TIMEOUT_CONFIG = {
  PART_DETAIL_FETCH_MS: 10000, // 10 seconds (ERR-INT-02)
} as const;

/**
 * Accessibility labels (ARIA)
 */
export const ARIA_LABELS = {
  MODAL: 'Modal de detalles de pieza',
  CLOSE_BUTTON: 'Cerrar modal',
  PREV_BUTTON: 'Pieza anterior',
  NEXT_BUTTON: 'Pieza siguiente',
  TAB_LIST: 'Opciones de visualización',
  TAB_VIEWER: 'Ver modelo 3D',
  TAB_METADATA: 'Ver metadatos',
  TAB_VALIDATION: 'Ver reporte de validación',
  POSITION_INDICATOR: 'Posición en lista filtrada',
} as const;

/**
 * Animation durations (milliseconds)
 */
export const ANIMATION_DURATIONS = {
  FADE_IN: 200,
  FADE_OUT: 150,
  TAB_TRANSITION: 300,
} as const;

/**
 * Default values
 */
export const DEFAULTS = {
  INITIAL_TAB: 'viewer' as TabId,
  // TEMPORARILY DISABLED: Backend endpoint /api/parts/{id}/adjacent was removed in US-015 cleanup
  // Re-enable when navigation endpoint is implemented for elements
  ENABLE_NAVIGATION: false,
  AUTO_CLOSE_ERROR_DELAY: 3000, // 3 seconds
} as const;

/**
 * Data fetch timeouts (milliseconds)
 */
export const FETCH_TIMEOUTS = {
  PART_DETAIL: 10000, // 10 seconds
  NAVIGATION: 5000, // 5 seconds
} as const;
