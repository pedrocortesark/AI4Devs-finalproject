/**
 * DetailsPanel Component
 *
 * Non-blocking sliding side panel for part detail inspection.
 * Opened by pressing "D" with a part selected; closed with "D" toggle or "Escape".
 *
 * Architecture:
 * - Fixed right side panel (400px), no backdrop → user can still interact with main canvas
 * - Slide-in/out animation via CSS module classes (.panelOpen / .panelClosed)
 * - 4 tabs: General | Geometría | Metadata | JSON Raw
 * - 3D viewer using PartViewer3D (OBJ + material color, no GLB)
 * - Data fetching via usePartDetail hook (shared with PartDetailModal)
 *
 * Design decisions (see docs/plans/details-panel-redesign.md):
 * - D1: Replaces PartDetailModal completely
 * - D2: isOpen state stays in Dashboard3D (local), not in Zustand store
 * - D3: Solid material color from MATERIAL_COLORS (not Rhino materials)
 * - D4: rhino_metadata tree if available; PartMetadataPanel fallback otherwise
 *
 * @module details/DetailsPanel
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './DetailsPanel.module.css';
import {
  TAB_CONFIG,
  TAB_ORDER,
  STATUS_BADGE_STYLES,
  DEFAULT_STATUS_STYLE,
  COLORS,
  RHINO_HIGHLIGHT_KEYS,
  ARIA,
  type TabId,
} from './DetailsPanel.constants';
import { PartViewer3D } from './PartViewer3D';
import { usePartDetail } from '@/components/Dashboard/PartDetailModal.hooks';
import { usePartsStore } from '@/stores/parts.store';
import { formatDate } from '@/utils/formatters';
import { MATERIAL_COLORS, getMaterialColorHex } from '@/constants/materials';
import { PartMetadataPanel } from '@/components/Dashboard/PartMetadataPanel';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DetailsPanelProps {
  /** UUID of the selected part. null → shows "no selection" state. */
  partId: string | null;
  /** Whether the panel is visible */
  isOpen: boolean;
  /** Called when user closes the panel */
  onClose: () => void;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function NoSelectionState() {
  return (
    <div className={styles.noSelection}>
      <span className={styles.noSelectionIcon}>⬡</span>
      <p className={styles.noSelectionText}>
        Selecciona una pieza en el visor principal<br />
        para ver sus detalles aquí.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className={styles.loading}>
      <span>Cargando pieza…</span>
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className={styles.errorState}>
      <p className={styles.errorTitle}>No se pudieron cargar los datos</p>
      <p className={styles.errorDetail}>{error.message}</p>
      <button
        onClick={onRetry}
        style={{
          padding: '6px 16px',
          background: COLORS.primary,
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '13px',
        }}
      >
        Reintentar
      </button>
    </div>
  );
}

// ─── Tab: General ─────────────────────────────────────────────────────────────

function TabGeneral({ part }: { part: NonNullable<ReturnType<typeof usePartDetail>['partData']> }) {
  const statusStyle = STATUS_BADGE_STYLES[part.status] ?? DEFAULT_STATUS_STYLE;

  const materialColorHex: string | null =
    part.material_type && part.material_type in MATERIAL_COLORS
      ? getMaterialColorHex(part.material_type as keyof typeof MATERIAL_COLORS)
      : null;

  return (
    <div>
      <p className={styles.isoCode}>{part.iso_code}</p>
      <div className={styles.fieldList}>
        {/* Status */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Estado</span>
          <span
            className={styles.badge}
            style={{
              background: statusStyle.background,
              color: statusStyle.color,
              borderColor: statusStyle.border,
            }}
          >
            {part.status}
          </span>
        </div>

        {/* Material */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Material</span>
          {part.material_type ? (
            <div className={styles.materialRow}>
              {materialColorHex && (
                <span
                  className={styles.materialDot}
                  style={{ background: materialColorHex }}
                  title={part.material_type}
                />
              )}
              <span className={styles.fieldValue}>{part.material_type}</span>
            </div>
          ) : (
            <span className={styles.fieldValueMuted}>No especificado</span>
          )}
        </div>

        {/* Tipología */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Tipología</span>
          <span className={styles.fieldValue}>{part.tipologia}</span>
        </div>

        {/* Created At */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Creado</span>
          <span className={styles.fieldValue}>{formatDate(part.created_at)}</span>
        </div>

        {/* Workshop */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Taller</span>
          {part.workshop_name ? (
            <span className={styles.fieldValue}>{part.workshop_name}</span>
          ) : (
            <span className={styles.fieldValueMuted}>Sin asignar</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Tab: Geometría ───────────────────────────────────────────────────────────

function TabGeometry({ part }: { part: NonNullable<ReturnType<typeof usePartDetail>['partData']> }) {
  const bbox = part.bbox;

  const dims = bbox
    ? {
        w: Math.abs(bbox.max[0] - bbox.min[0]).toFixed(2),
        h: Math.abs(bbox.max[1] - bbox.min[1]).toFixed(2),
        d: Math.abs(bbox.max[2] - bbox.min[2]).toFixed(2),
      }
    : null;

  const fmt = (v: number) => v.toFixed(2);

  return (
    <div>
      {/* Bounding Box */}
      <p className={styles.sectionTitle}>Bounding Box</p>
      {bbox ? (
        <>
          <div className={styles.bboxGrid}>
            <span className={styles.bboxLabel}>Min</span>
            <span className={styles.bboxValue}>
              [{fmt(bbox.min[0])}, {fmt(bbox.min[1])}, {fmt(bbox.min[2])}] mm
            </span>
            <span className={styles.bboxLabel}>Max</span>
            <span className={styles.bboxValue}>
              [{fmt(bbox.max[0])}, {fmt(bbox.max[1])}, {fmt(bbox.max[2])}] mm
            </span>
          </div>
          {dims && (
            <div className={styles.dimensions}>
              <p className={styles.dimensionsLabel}>Dimensiones</p>
              {dims.w} × {dims.h} × {dims.d} mm
            </div>
          )}
        </>
      ) : (
        <p className={styles.fieldValueMuted} style={{ marginBottom: '16px' }}>No disponible</p>
      )}

      <hr className={styles.divider} />

      {/* LOD URLs */}
      <p className={styles.sectionTitle}>LOD URLs</p>
      <div className={styles.lodList}>
        {(
          [
            { label: 'High Poly', url: part.high_poly_url },
            { label: 'Mid Poly',  url: part.mid_poly_url },
            { label: 'Low Poly',  url: part.low_poly_url },
          ] as const
        ).map(({ label, url }) => (
          <div key={label} className={styles.lodItem}>
            <span className={styles.lodItemLabel}>{label}</span>
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.lodLink}
                title={url}
              >
                {url}
              </a>
            ) : (
              <span className={styles.lodNull}>No disponible</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Tab: Metadata ────────────────────────────────────────────────────────────

function TabMetadata({ part }: { part: NonNullable<ReturnType<typeof usePartDetail>['partData']> }) {
  const [showOther, setShowOther] = useState(false);
  const meta = part.rhino_metadata;

  // No rhino_metadata from backend yet → show PartMetadataPanel as fallback
  // (shows validation, workshop, geometry info from the PartDetail response)
  if (!meta || Object.keys(meta).length === 0) {
    return (
      <div>
        <p className={styles.sectionTitle} style={{ marginBottom: '12px' }}>
          Información de pieza
        </p>
        <PartMetadataPanel part={part} initialExpandedSection="info" />
      </div>
    );
  }

  const highlightKeys = RHINO_HIGHLIGHT_KEYS.filter((k) => k in meta);
  const otherKeys = Object.keys(meta).filter(
    (k) => !(RHINO_HIGHLIGHT_KEYS as readonly string[]).includes(k)
  );

  return (
    <div>
      {/* Highlighted keys */}
      {highlightKeys.length > 0 && (
        <div className={styles.metaHighlightList}>
          {highlightKeys.map((k) => (
            <div key={k} className={styles.metaHighlightRow}>
              <p className={styles.metaKey}>{k}</p>
              <p className={styles.metaValue}>{String(meta[k] ?? '—')}</p>
            </div>
          ))}
        </div>
      )}

      {/* Other keys (collapsible) */}
      {otherKeys.length > 0 && (
        <>
          <button
            className={styles.metaOtherToggle}
            onClick={() => setShowOther((v) => !v)}
          >
            <span>{showOther ? '▾' : '▸'}</span>
            <span>{showOther ? 'Ocultar' : `Ver ${otherKeys.length} campos más`}</span>
          </button>
          {showOther && (
            <div className={styles.metaOtherList}>
              {otherKeys.map((k) => (
                <div key={k} className={styles.metaOtherRow}>
                  <span className={styles.metaOtherKey}>{k}</span>
                  <span className={styles.metaOtherValue}>{String(meta[k] ?? '—')}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Tab: JSON Raw ────────────────────────────────────────────────────────────

function TabRaw({ part }: { part: NonNullable<ReturnType<typeof usePartDetail>['partData']> }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(part, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API not available (e.g. non-HTTPS) — silent fail
    }
  };

  return (
    <div>
      <div className={styles.jsonToolbar}>
        <button
          onClick={handleCopy}
          aria-label={ARIA.COPY_JSON}
          className={`${styles.copyButton} ${copied ? styles.copyButtonSuccess : ''}`}
        >
          <span>{copied ? '✓' : '⎘'}</span>
          <span>{copied ? '¡Copiado!' : 'Copiar JSON'}</span>
        </button>
      </div>
      <pre className={styles.jsonBlock}>
        {JSON.stringify(part, null, 2)}
      </pre>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

/**
 * DetailsPanel — sliding side panel with part details and 3D viewer.
 *
 * @example
 * <DetailsPanel
 *   partId={selectedId}
 *   isOpen={showDetails}
 *   onClose={() => setShowDetails(false)}
 * />
 */
export function DetailsPanel({ partId, isOpen, onClose }: DetailsPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('general');

  // Fetch part detail (metadata, validation report, etc.)
  const { partData, loading, error, retry } = usePartDetail(partId ?? '', isOpen && !!partId);

  // Get the OBJ URL directly from the parts store — the list endpoint returns OBJ URLs
  // which are guaranteed to work with OBJLoader (PartDetail.low_poly_url may be GLB).
  const storeUrl = usePartsStore(
    (state) => state.parts.find((p) => p.id === partId)?.low_poly_url ?? null
  );
  // Viewer uses the store OBJ URL; falls back to partData URL if part not in store yet
  const viewerUrl = storeUrl ?? partData?.low_poly_url ?? null;

  // Reset to first tab when part changes
  useEffect(() => {
    setActiveTab('general');
  }, [partId]);

  // Close on Escape key
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isOpen) onClose();
  }, [isOpen, onClose]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const panelClass = `${styles.panel} ${isOpen ? styles.panelOpen : styles.panelClosed}`;

  const headerTitle = partData?.iso_code
    ?? (loading ? 'Cargando…' : partId ? '—' : 'Detalles de pieza');

  return (
    <div
      role="complementary"
      aria-label={ARIA.PANEL}
      className={panelClass}
      data-testid="details-panel"
    >
      {/* ── Header ── */}
      <div className={styles.header}>
        <h2 className={styles.headerTitle}>{headerTitle}</h2>
        <button
          onClick={onClose}
          aria-label={ARIA.CLOSE_BUTTON}
          className={styles.closeButton}
        >
          ×
        </button>
      </div>

      {/* ── No selection ── */}
      {!partId && <NoSelectionState />}

      {/* ── Part loaded ── */}
      {partId && (
        <>
          {/* 3D Viewer — uses OBJ URL from store (list endpoint) */}
          <div className={styles.viewer3d}>
            <PartViewer3D
              url={viewerUrl}
              materialType={partData?.material_type}
              bbox={partData?.bbox}
            />
          </div>

          {/* Tab Bar */}
          <div role="tablist" aria-label={ARIA.TAB_LIST} className={styles.tabBar}>
            {TAB_ORDER.map((tabId) => (
              <button
                key={tabId}
                role="tab"
                aria-selected={activeTab === tabId}
                onClick={() => setActiveTab(tabId)}
                className={`${styles.tab} ${activeTab === tabId ? styles.tabActive : ''}`}
              >
                <span className={styles.tabIcon}>{TAB_CONFIG[tabId].icon}</span>
                {TAB_CONFIG[tabId].label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div role="tabpanel" className={styles.content}>
            {loading && <LoadingState />}
            {error && !loading && <ErrorState error={error} onRetry={retry} />}
            {!loading && !error && partData && (
              <>
                {activeTab === 'general'  && <TabGeneral  part={partData} />}
                {activeTab === 'geometry' && <TabGeometry part={partData} />}
                {activeTab === 'metadata' && <TabMetadata part={partData} />}
                {activeTab === 'raw'      && <TabRaw      part={partData} />}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default DetailsPanel;
