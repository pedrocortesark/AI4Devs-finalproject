/**
 * Helper Utilities for PartDetailModal
 * T-1007-FRONT: Modal Integration - Error Mapping & Rendering Utilities
 * 
 * @remarks
 * Extracts error message mapping and tab content rendering logic
 * for better testability and DRY principles.
 * 
 * @module PartDetailModal.helpers
 */

import { ERROR_MESSAGES, MODAL_STYLES } from './PartDetailModal.constants';
import { DS } from '@/styles/designTokens';
import type { PartDetail } from '@/types/parts';
import { ModelLoader } from '@/components/ModelLoader';
import { PartMetadataPanel } from './PartMetadataPanel';
import { PartViewerCanvas } from '@/components/PartViewerCanvas';
import { ViewerErrorBoundary } from './ViewerErrorBoundary';

/**
 * Maps Error object to user-friendly error messages
 * 
 * @param error - Error object from fetch failure
 * @returns Object with title and detail message
 * 
 * @example
 * const { title, detail } = getErrorMessages(error);
 */
export function getErrorMessages(error: Error): { title: string; detail: string } {
  const messageMap: Record<string, { title: string; detail: string }> = {
    'Part not found': {
      title: ERROR_MESSAGES.PART_NOT_FOUND,
      detail: ERROR_MESSAGES.PART_NOT_FOUND_DETAIL,
    },
    'Access denied': {
      title: ERROR_MESSAGES.ACCESS_DENIED,
      detail: ERROR_MESSAGES.ACCESS_DENIED_DETAIL,
    },
    [ERROR_MESSAGES.TIMEOUT]: {
      title: ERROR_MESSAGES.TIMEOUT,
      detail: ERROR_MESSAGES.TIMEOUT_DETAIL,
    },
  };

  return messageMap[error.message] || {
    title: ERROR_MESSAGES.FETCH_FAILED,
    detail: ERROR_MESSAGES.FETCH_FAILED_DETAIL,
  };
}

/**
 * Renders error state UI with icon, title, and message
 * 
 * @param error - Error object from fetch failure
 * @param onRetry - Optional callback to retry the failed operation (for timeout errors)
 * @returns JSX element with error UI
 * 
 * @example
 * {error && renderErrorState(error, handleRetry)}
 */
export function renderErrorState(error: Error, onRetry?: () => void): JSX.Element {
  const { title, detail } = getErrorMessages(error);
  const isTimeout = error.message === ERROR_MESSAGES.TIMEOUT;

  return (
    <div style={MODAL_STYLES.errorContainer}>
      <div style={MODAL_STYLES.errorIcon}>⚠️</div>
      <h3 style={MODAL_STYLES.errorTitle}>{title}</h3>
      <p style={MODAL_STYLES.errorMessage}>{detail}</p>
      {isTimeout && onRetry && (
        <button
          onClick={onRetry}
          aria-label="Reintentar"
          style={{
            marginTop: '1rem',
            padding: '0.5rem 1rem',
            backgroundColor: DS.blue,
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '0.9375rem',
            fontWeight: 500,
            fontFamily: DS.font,
          }}
        >
          Reintentar
        </button>
      )}
    </div>
  );
}

/**
 * Renders metadata tab content with formatted JSON
 * 
 * @param partData - Part detail data object
 * @returns JSX element with metadata tab content
 * 
 * @example
 * {activeTab === 'metadata' && renderMetadataTab(partData)}
 */
export function renderMetadataTab(partData: PartDetail): JSX.Element {
  return <PartMetadataPanel part={partData} initialExpandedSection="info" />;
}

/**
 * Renders validation tab content with report or empty state
 * 
 * @param partData - Part detail data object
 * @returns JSX element with validation tab content
 * 
 * @example
 * {activeTab === 'validation' && renderValidationTab(partData)}
 */
export function renderValidationTab(partData: PartDetail): JSX.Element {
  if (partData.validation_report) {
    const report = partData.validation_report;
    const isValid = report.is_valid === true;
    const hasErrors = !isValid && Array.isArray(report.errors) && report.errors.length > 0;
    const tone = isValid ? DS.green : DS.red;

    return (
      <div style={{ fontFamily: DS.font, color: DS.textPrimary }}>
        {/* Status card */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px',
            borderRadius: '12px',
            border: `1px solid ${DS.borderSubtle}`,
            background: DS.bgSurface,
            marginBottom: '16px',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '9999px',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: tone,
              background: isValid ? 'rgba(52,199,89,0.12)' : 'rgba(255,69,58,0.12)',
            }}
          >
            {isValid ? '✓' : '✕'} {isValid ? 'Validación correcta' : 'Validación fallida'}
          </span>
          <span style={{ fontSize: '0.8125rem', color: DS.textSecondary }}>
            {isValid
              ? 'La pieza cumple todas las reglas de validación.'
              : `${hasErrors ? report.errors.length : 0} ${
                  hasErrors && report.errors.length === 1 ? 'error detectado' : 'errores detectados'
                }`}
          </span>
        </div>

        {/* Error list */}
        {hasErrors && (
          <ul
            data-testid="validation-errors-list"
            style={{ listStyle: 'none', margin: '0 0 16px', padding: 0 }}
          >
            {report.errors.map((error, idx) => (
              <li
                key={idx}
                style={{
                  padding: '12px 14px',
                  marginBottom: '8px',
                  borderRadius: '10px',
                  border: `1px solid ${DS.borderSubtle}`,
                  background: DS.bgSurface,
                  borderLeft: `3px solid ${DS.red}`,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    gap: '8px',
                    alignItems: 'baseline',
                    marginBottom: '4px',
                  }}
                >
                  <strong style={{ fontSize: '0.8125rem', color: DS.textPrimary }}>
                    {error.category}
                  </strong>
                  <span style={{ fontSize: '0.75rem', color: DS.textTertiary }}>
                    {error.target}
                  </span>
                </div>
                <div style={{ fontSize: '0.875rem', color: DS.textSecondary }}>
                  {error.message}
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Raw JSON (collapsed) */}
        <details style={{ marginTop: '4px' }}>
          <summary
            style={{
              cursor: 'pointer',
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: DS.textSecondary,
              userSelect: 'none',
            }}
          >
            Ver JSON técnico
          </summary>
          <pre
            style={{
              fontFamily: "'SF Mono', 'Monaco', 'Courier New', monospace",
              fontSize: '0.75rem',
              color: DS.textSecondary,
              background: DS.bgElevated,
              border: `1px solid ${DS.borderSubtle}`,
              borderRadius: '8px',
              padding: '12px',
              overflowX: 'auto',
              marginTop: '8px',
              whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify(report, null, 2)}
          </pre>
        </details>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '3rem',
        color: DS.textTertiary,
        fontFamily: DS.font,
        fontSize: '0.9375rem',
      }}
    >
      <div style={{ fontSize: '2rem', marginBottom: '12px', opacity: 0.5 }}>📋</div>
      Sin reporte de validación disponible
    </div>
  );
}

/**
 * Renders viewer tab content with ModelLoader component
 * 
 * @param partId - UUID of part to load
 * @returns JSX element with 3D viewer
 * 
 * @example
 * {activeTab === 'viewer' && renderViewerTab(currentPartId)}
 */
export function renderViewerTab(partId: string): JSX.Element {
  return (
    <ViewerErrorBoundary>
      <PartViewerCanvas>
        <ModelLoader partId={partId} />
      </PartViewerCanvas>
    </ViewerErrorBoundary>
  );
}
