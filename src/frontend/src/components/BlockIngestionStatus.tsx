/**
 * BlockIngestionStatus — US-020 Phase 2
 *
 * Shows real-time ingestion + geometry pipeline state for each block.
 * Subscribes to Supabase Realtime postgres_changes filtered by url_original.
 *
 * Pipeline visible per block:
 *   1. Registro       → block row created in DB
 *   2. Validación     → validate_file task (metadata + nomenclatura)
 *   3. High Poly GLB  → geometry_processing (full resolution)
 *   4. Mid Poly GLB   → geometry_processing (medium resolution)
 *   5. Low Poly GLB   → geometry_processing (web viewer resolution)
 *
 * Note: The Realtime filter `url_original=eq.${fileKey}` requires the
 * `url_original` column to be in the Supabase Realtime publication.
 */

import { useEffect, useRef, useState } from 'react';
import { getSupabaseClient } from '../services/supabase.client';
import type { BlockIngestionRow, BlockIngestionState, IngestionSummary } from '../types/preview';

// ── Design tokens ─────────────────────────────────────────────────────────────
const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  bgSurface: '#2C2C2E',
  bgCard:    '#1C1C1E',
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid:    'rgba(255, 255, 255, 0.14)',
  textPrimary:   'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary:  'rgba(255, 255, 255, 0.3)',
  blue:   '#007AFF',
  green:  '#34C759',
  yellow: '#FF9F0A',
  red:    '#FF453A',
} as const;

// ── Status badge ──────────────────────────────────────────────────────────────

type BadgeConfig = { color: string; bg: string; label: string; spinning?: boolean };

const STATE_BADGE: Record<BlockIngestionState, BadgeConfig> = {
  pending:          { color: DS.textTertiary,  bg: 'rgba(255,255,255,0.06)', label: 'Pendiente'   },
  uploaded:         { color: DS.blue,          bg: 'rgba(0,122,255,0.12)',   label: 'Subido'      },
  processing:       { color: DS.yellow,        bg: 'rgba(255,159,10,0.12)',  label: 'Procesando', spinning: true },
  validated:        { color: DS.green,         bg: 'rgba(52,199,89,0.12)',   label: 'Validado'    },
  error_processing: { color: DS.red,           bg: 'rgba(255,69,58,0.12)',   label: 'Error'       },
  rejected:         { color: DS.red,           bg: 'rgba(255,69,58,0.12)',   label: 'Rechazado'   },
  skipped:          { color: DS.textSecondary, bg: 'rgba(255,255,255,0.06)', label: 'Ya existía'  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const SPINNER: React.CSSProperties = {
  display: 'inline-block',
  width: '9px',
  height: '9px',
  borderRadius: '50%',
  border: `1.5px solid currentColor`,
  borderTopColor: 'transparent',
  animation: 'spin 0.8s linear infinite',
  verticalAlign: 'middle',
  marginLeft: '4px',
};

function dbStatusToState(status: string): BlockIngestionState {
  const valid: BlockIngestionState[] = [
    'uploaded', 'processing', 'validated', 'error_processing', 'rejected',
  ];
  return valid.includes(status as BlockIngestionState)
    ? (status as BlockIngestionState)
    : 'pending';
}

function buildSummary(rows: BlockIngestionRow[]): IngestionSummary {
  return {
    total: rows.length,
    completed: rows.filter((r) => r.state === 'validated').length,
    processing: rows.filter((r) => r.state === 'processing' || r.state === 'uploaded').length,
    failed: rows.filter((r) => r.state === 'error_processing' || r.state === 'rejected').length,
    skipped: rows.filter((r) => r.state === 'skipped').length,
    rows,
  };
}

function rowFromRecord(rec: any): BlockIngestionRow {
  return {
    id: rec.id,
    iso_code: rec.iso_code,
    state: dbStatusToState(rec.status),
    skipped: false,
    error_reason: rec.validation_report?.errors?.[0]?.message,
    validation_report: rec.validation_report ?? null,
    high_poly_url: rec.high_poly_url ?? null,
    mid_poly_url: rec.mid_poly_url ?? null,
    low_poly_url: rec.low_poly_url ?? null,
    created_at: rec.created_at,
    updated_at: rec.updated_at,
  };
}

// ── Pipeline step indicator ───────────────────────────────────────────────────

type PipelineStepStatus = 'done' | 'error' | 'pending' | 'running';

interface PipelineStep {
  label: string;
  status: PipelineStepStatus;
  detail?: string;
  url?: string | null;
}

function getPipelineSteps(row: BlockIngestionRow): PipelineStep[] {
  const blockState = row.state;
  const isProcessing = blockState === 'processing';
  const isValidated = blockState === 'validated';
  const hasError = blockState === 'error_processing' || blockState === 'rejected';

  return [
    {
      label: 'Registro',
      status: 'done', // if the row exists, it was registered
      detail: row.created_at ? new Date(row.created_at).toLocaleTimeString('es-ES') : undefined,
    },
    {
      label: 'Validación',
      status: hasError
        ? 'error'
        : isValidated || row.validation_report?.is_valid
        ? 'done'
        : isProcessing
        ? 'running'
        : 'pending',
      detail: row.validation_report?.validated_at
        ? new Date(row.validation_report.validated_at).toLocaleTimeString('es-ES')
        : row.error_reason,
    },
    {
      label: 'High Poly',
      status: row.high_poly_url ? 'done' : isValidated ? 'running' : 'pending',
      url: row.high_poly_url,
    },
    {
      label: 'Mid Poly',
      status: row.mid_poly_url ? 'done' : row.high_poly_url ? 'running' : 'pending',
      url: row.mid_poly_url,
    },
    {
      label: 'Low Poly',
      status: row.low_poly_url ? 'done' : row.mid_poly_url ? 'running' : 'pending',
      url: row.low_poly_url,
    },
  ];
}

const STEP_COLORS: Record<PipelineStepStatus, string> = {
  done:    DS.green,
  error:   DS.red,
  running: DS.yellow,
  pending: DS.textTertiary,
};

const STEP_ICONS: Record<PipelineStepStatus, string> = {
  done:    '✓',
  error:   '✕',
  running: '◌',
  pending: '·',
};

function PipelineSteps({ row }: { row: BlockIngestionRow }) {
  const steps = getPipelineSteps(row);
  return (
    <div style={{
      display: 'flex',
      gap: '0',
      marginTop: '8px',
      flexWrap: 'wrap',
    }}>
      {steps.map((step, i) => (
        <div key={step.label} style={{ display: 'flex', alignItems: 'center' }}>
          {/* Step pill */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
            borderRadius: '4px',
            backgroundColor: `${STEP_COLORS[step.status]}18`,
            border: `1px solid ${STEP_COLORS[step.status]}40`,
          }}>
            <span style={{
              fontSize: '10px',
              color: STEP_COLORS[step.status],
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
            }}>
              {step.status === 'running'
                ? <span style={{ ...SPINNER, width: '8px', height: '8px', marginLeft: 0 }} />
                : STEP_ICONS[step.status]
              }
            </span>
            {step.url
              ? (
                <a
                  href={step.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '10px', color: DS.blue, textDecoration: 'none', fontWeight: 500 }}
                >
                  {step.label}
                </a>
              )
              : (
                <span style={{
                  fontSize: '10px',
                  color: step.status === 'pending' ? DS.textTertiary : DS.textSecondary,
                  fontWeight: 500,
                }}>
                  {step.label}
                </span>
              )
            }
            {step.detail && step.status !== 'running' && (
              <span style={{ fontSize: '10px', color: DS.textTertiary }}>
                {step.status === 'error' ? `· ${step.detail}` : step.detail}
              </span>
            )}
          </div>
          {/* Arrow between steps */}
          {i < steps.length - 1 && (
            <span style={{ fontSize: '10px', color: DS.textTertiary, margin: '0 3px' }}>›</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── DB query fields ───────────────────────────────────────────────────────────

const BLOCK_SELECT_FIELDS = [
  'id', 'iso_code', 'status',
  'validation_report',
  'high_poly_url', 'mid_poly_url', 'low_poly_url',
  'created_at', 'updated_at',
].join(', ');

// ── Main component ────────────────────────────────────────────────────────────

export interface BlockIngestionStatusProps {
  fileKey: string;
  onNewUpload?: () => void;
}

export function BlockIngestionStatus({ fileKey, onNewUpload }: BlockIngestionStatusProps) {
  const [rows, setRows] = useState<BlockIngestionRow[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const channelRef = useRef<any>(null);

  const summary = buildSummary(rows);
  // All done = no blocks in 'uploaded' or 'processing', and all poly URLs present where expected
  const allValidated = summary.total > 0 && summary.processing === 0 && summary.failed === 0;
  const allDone = allValidated && rows.every((r) => r.low_poly_url || r.state === 'error_processing' || r.state === 'rejected');

  // ── Initial fetch ─────────────────────────────────────────────────────────
  useEffect(() => {
    const supabase = getSupabaseClient();

    async function fetchInitial() {
      try {
        const { data, error: fetchError } = await supabase
          .from('blocks')
          .select(BLOCK_SELECT_FIELDS)
          .eq('url_original', fileKey);

        if (fetchError) throw fetchError;
        setRows((data ?? []).map(rowFromRecord));
      } catch (e: any) {
        setError(e.message ?? 'Error al cargar el estado');
      }
    }

    fetchInitial();
  }, [fileKey]);

  // ── Realtime subscription ─────────────────────────────────────────────────
  useEffect(() => {
    const supabase = getSupabaseClient();
    const channelName = `ingestion-${fileKey.replace(/[^a-zA-Z0-9-]/g, '-')}`;

    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes' as any,
        {
          event: '*',
          schema: 'public',
          table: 'blocks',
          filter: `url_original=eq.${fileKey}`,
        },
        (payload: any) => {
          const record = payload.new ?? payload.old;
          if (!record) return;

          setRows((prev) => {
            const idx = prev.findIndex((r) => r.id === record.id);
            const updated = rowFromRecord(record);
            if (idx === -1) return [...prev, updated];
            // Realtime UPDATE payloads can omit validation_report (depends on
            // the table REPLICA IDENTITY), which would blank the rejection
            // reason the initial fetch already loaded. Preserve it.
            if (record.validation_report == null && prev[idx].validation_report) {
              updated.validation_report = prev[idx].validation_report;
              updated.error_reason = prev[idx].validation_report?.errors?.[0]?.message;
            }
            const next = [...prev];
            next[idx] = updated;
            return next;
          });
        }
      )
      .subscribe((status: string) => {
        if (status === 'SUBSCRIBED') setConnected(true);
        if (status === 'CHANNEL_ERROR') setError('No se pudo conectar al canal Realtime');
      });

    channelRef.current = channel;
    return () => { channel.unsubscribe(); };
  }, [fileKey]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div style={{ fontFamily: DS.font, color: DS.textPrimary }}>

        {/* ── Summary bar ── */}
        <div style={{
          display: 'flex',
          gap: '16px',
          flexWrap: 'wrap',
          alignItems: 'center',
          padding: '12px 16px',
          backgroundColor: DS.bgSurface,
          borderRadius: '10px',
          marginBottom: '16px',
          fontSize: '13px',
        }}>
          <span style={{ fontWeight: 600 }}>{summary.total} bloque{summary.total !== 1 ? 's' : ''}</span>
          {summary.completed > 0 && (
            <span><span style={{ color: DS.green }}>{summary.completed}</span> validado{summary.completed !== 1 ? 's' : ''}</span>
          )}
          {summary.processing > 0 && (
            <span>
              <span style={{ color: DS.yellow }}>{summary.processing}</span> en proceso
              <span style={{ ...SPINNER }} />
            </span>
          )}
          {summary.failed > 0 && (
            <span><span style={{ color: DS.red }}>{summary.failed}</span> error{summary.failed !== 1 ? 'es' : ''}</span>
          )}
          {summary.skipped > 0 && (
            <span style={{ color: DS.textTertiary }}>{summary.skipped} omitido{summary.skipped !== 1 ? 's' : ''}</span>
          )}

          {/* Realtime indicator */}
          <span style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            fontSize: '11px',
            color: connected ? DS.green : DS.textTertiary,
          }}>
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%',
              backgroundColor: connected ? DS.green : DS.textTertiary,
              flexShrink: 0,
            }} />
            {connected ? 'Realtime activo' : 'Conectando…'}
          </span>
        </div>

        {/* ── Error notice ── */}
        {error && (
          <div style={{
            padding: '10px 14px', marginBottom: '12px',
            backgroundColor: 'rgba(255,69,58,0.08)',
            border: '1px solid rgba(255,69,58,0.3)',
            borderRadius: '8px', fontSize: '13px', color: '#FF6B60',
          }}>
            {error}
          </div>
        )}

        {/* ── Rejection reasons (readable) ── */}
        {summary.failed > 0 && (
          <div style={{
            padding: '12px 14px', marginBottom: '16px',
            backgroundColor: 'rgba(255,69,58,0.08)',
            border: '1px solid rgba(255,69,58,0.3)',
            borderRadius: '8px',
          }}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#FF6B60', marginBottom: '8px' }}>
              Motivo del rechazo ({summary.failed})
            </div>
            {rows
              .filter((r) => r.state === 'error_processing' || r.state === 'rejected')
              .map((r) => {
                const errs = r.validation_report?.errors;
                return (
                  <div key={r.id} style={{ fontSize: '12px', color: DS.textSecondary, marginBottom: '6px', lineHeight: 1.5 }}>
                    <span style={{ fontWeight: 600, color: DS.textPrimary }}>{r.iso_code}</span>
                    {Array.isArray(errs) && errs.length > 0 ? (
                      <ul style={{ margin: '2px 0 0', paddingLeft: '18px' }}>
                        {errs.map((e: any, k: number) => (
                          <li key={k}>
                            <span style={{ color: DS.textTertiary }}>{e.category}:</span> {e.message}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span> — {r.error_reason ?? 'Sin detalle disponible'}</span>
                    )}
                  </div>
                );
              })}
          </div>
        )}

        {/* ── Block list ── */}
        {rows.length === 0 ? (
          <p style={{ color: DS.textTertiary, fontSize: '13px', textAlign: 'center', padding: '24px 0' }}>
            Esperando bloques…
          </p>
        ) : (
          <div style={{
            borderRadius: '10px',
            border: `1px solid ${DS.borderMid}`,
            overflow: 'hidden',
            marginBottom: '20px',
          }}>
            {rows.map((row, i) => {
              const badge = STATE_BADGE[row.state];
              return (
                <div
                  key={row.id}
                  style={{
                    padding: '12px 14px',
                    borderBottom: i < rows.length - 1 ? `1px solid ${DS.borderSubtle}` : undefined,
                    backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                  }}
                >
                  {/* Row header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {/* ISO code */}
                    <span style={{
                      flex: 1,
                      fontSize: '13px',
                      fontFamily: 'monospace',
                      color: DS.textPrimary,
                    }}>
                      {row.iso_code}
                    </span>

                    {/* Status badge */}
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: badge.color,
                      backgroundColor: badge.bg,
                      flexShrink: 0,
                      gap: '4px',
                    }}>
                      {badge.label}
                      {badge.spinning && <span style={SPINNER} />}
                    </span>

                    {/* Updated timestamp */}
                    {row.updated_at && (
                      <span style={{ fontSize: '10px', color: DS.textTertiary, flexShrink: 0 }}>
                        {new Date(row.updated_at).toLocaleTimeString('es-ES')}
                      </span>
                    )}
                  </div>

                  {/* Pipeline steps */}
                  <PipelineSteps row={row} />

                  {/* Error detail */}
                  {row.error_reason && (
                    <div style={{
                      marginTop: '6px',
                      fontSize: '11px',
                      color: DS.red,
                      lineHeight: 1.4,
                      paddingLeft: '2px',
                    }}>
                      {row.error_reason}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Actions ── */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          {allDone && onNewUpload && (
            <button
              onClick={onNewUpload}
              style={{
                padding: '9px 20px',
                backgroundColor: 'transparent',
                border: `1px solid ${DS.borderMid}`,
                color: DS.textSecondary,
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              Nueva subida
            </button>
          )}
        </div>
      </div>
    </>
  );
}

export default BlockIngestionStatus;
