/**
 * FilePreviewPanel — US-020 Phase 1
 *
 * Displays per-InstanceDefinition analysis of a .3dm file before upload.
 * Badge colors follow the project design system (dark theme, macOS-style).
 */

import type { FilePreviewResponse, BlockPreview } from '../types/preview';

// ── Design tokens (mirrors App.tsx DS object) ─────────────────────────────────
const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  bgCard:    '#1C1C1E',
  bgSurface: '#2C2C2E',
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid:    'rgba(255, 255, 255, 0.14)',
  textPrimary:   'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary:  'rgba(255, 255, 255, 0.3)',
  blue:  '#007AFF',
  green: '#34C759',
  // Non-DS literals used only within this component:
  yellow: '#FF9F0A',
  red:    '#FF453A',
} as const;

// ── Badge logic ───────────────────────────────────────────────────────────────

type BadgeVariant = 'green' | 'yellow' | 'gray';

function getBadgeVariant(block: BlockPreview): BadgeVariant {
  if (block.already_exists) return 'gray';
  if (!block.codi) return 'yellow';   // no Codi = won't register
  return 'green';
}

const BADGE_STYLES: Record<BadgeVariant, { color: string; bg: string; label: string }> = {
  green:  { color: DS.green,         bg: 'rgba(52,199,89,0.12)',   label: 'Válido'      },
  yellow: { color: DS.yellow,        bg: 'rgba(255,159,10,0.12)',  label: 'Sin Codi'    },
  gray:   { color: DS.textSecondary, bg: 'rgba(255,255,255,0.06)', label: 'Ya existía'  },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function Badge({ variant }: { variant: BadgeVariant }) {
  const s = BADGE_STYLES[variant];
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: 600,
      letterSpacing: '0.02em',
      color: s.color,
      backgroundColor: s.bg,
      whiteSpace: 'nowrap',
    }}>
      {s.label}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export interface FilePreviewPanelProps {
  preview: FilePreviewResponse;
  onConfirm: () => void;
  onCancel: () => void;
  isUploading?: boolean;
}

export function FilePreviewPanel({
  preview,
  onConfirm,
  onCancel,
  isUploading = false,
}: FilePreviewPanelProps) {
  const canUpload = preview.valid_blocks > 0 && !isUploading;

  return (
    <div style={{ fontFamily: DS.font, color: DS.textPrimary }}>
      {/* ── Summary bar ── */}
      <div style={{
        display: 'flex',
        gap: '16px',
        flexWrap: 'wrap',
        padding: '12px 16px',
        backgroundColor: DS.bgSurface,
        borderRadius: '10px',
        marginBottom: '16px',
        fontSize: '13px',
      }}>
        <span style={{ color: DS.textPrimary, fontWeight: 600 }}>
          {preview.total_blocks} bloque{preview.total_blocks !== 1 ? 's' : ''}
        </span>
        <span style={{ color: DS.textSecondary }}>
          <span style={{ color: DS.green }}>{preview.valid_blocks}</span> válido{preview.valid_blocks !== 1 ? 's' : ''}
        </span>
        {preview.duplicate_blocks > 0 && (
          <span style={{ color: DS.textSecondary }}>
            <span style={{ color: DS.textTertiary }}>{preview.duplicate_blocks}</span> duplicado{preview.duplicate_blocks !== 1 ? 's' : ''}
          </span>
        )}
        {preview.invalid_blocks > 0 && (
          <span style={{ color: DS.textSecondary }}>
            <span style={{ color: '#FF453A' }}>{preview.invalid_blocks}</span> con errores
          </span>
        )}
        <span style={{ color: DS.textTertiary, marginLeft: 'auto', fontSize: '12px' }}>
          {preview.filename}
        </span>
      </div>

      {/* ── Table ── */}
      <div style={{
        overflowX: 'auto',
        borderRadius: '10px',
        border: `1px solid ${DS.borderMid}`,
        marginBottom: '20px',
      }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '13px',
        }}>
          <thead>
            <tr style={{
              borderBottom: `1px solid ${DS.borderSubtle}`,
              backgroundColor: DS.bgSurface,
            }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: DS.textSecondary, fontWeight: 500 }}>Nombre</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: DS.textSecondary, fontWeight: 500 }}>Codi</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', color: DS.textSecondary, fontWeight: 500 }}>Material</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', color: DS.textSecondary, fontWeight: 500 }}>ISO</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', color: DS.textSecondary, fontWeight: 500 }}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {preview.blocks.map((block, i) => (
              <tr
                key={block.name}
                style={{
                  borderBottom: i < preview.blocks.length - 1
                    ? `1px solid ${DS.borderSubtle}`
                    : undefined,
                  backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                }}
              >
                {/* Name (idef.Name from Rhino) */}
                <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                  <div style={{ fontSize: '12px', color: DS.textPrimary, fontFamily: 'monospace' }}>
                    {block.name}
                  </div>
                </td>
                {/* Codi (UserString) */}
                <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                  {block.codi
                    ? <span style={{ fontSize: '12px', color: DS.textPrimary, fontFamily: 'monospace' }}>{block.codi}</span>
                    : <span style={{ fontSize: '11px', color: DS.red }}>—</span>
                  }
                </td>
                {/* Material (UserString) */}
                <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                  {block.material
                    ? <span style={{ fontSize: '12px', color: DS.textSecondary }}>{block.material}</span>
                    : <span style={{ fontSize: '11px', color: DS.textTertiary }}>—</span>
                  }
                </td>
                {/* ISO — informational only, not blocking */}
                <td style={{ padding: '10px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
                  <span
                    title={block.iso_issues[0] ?? ''}
                    style={{
                      fontSize: '11px',
                      color: block.iso_valid ? DS.green : DS.yellow,
                    }}
                  >
                    {block.iso_valid ? '✓' : '⚠'}
                  </span>
                </td>
                {/* Badge */}
                <td style={{ padding: '10px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
                  <Badge variant={getBadgeVariant(block)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Actions ── */}
      <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
        <button
          onClick={onCancel}
          disabled={isUploading}
          style={{
            padding: '9px 20px',
            backgroundColor: 'transparent',
            border: `1px solid ${DS.borderMid}`,
            color: DS.textSecondary,
            borderRadius: '8px',
            cursor: isUploading ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            opacity: isUploading ? 0.5 : 1,
          }}
        >
          Cancelar
        </button>
        <button
          onClick={onConfirm}
          disabled={!canUpload}
          style={{
            padding: '9px 20px',
            backgroundColor: canUpload ? DS.blue : 'rgba(0, 122, 255, 0.3)',
            border: 'none',
            color: canUpload ? 'white' : 'rgba(255,255,255,0.4)',
            borderRadius: '8px',
            cursor: canUpload ? 'pointer' : 'not-allowed',
            fontSize: '14px',
            fontWeight: 600,
          }}
        >
          {isUploading ? 'Subiendo…' : 'Subir archivo'}
        </button>
      </div>

      {/* ── No valid blocks warning ── */}
      {preview.valid_blocks === 0 && (
        <p style={{
          marginTop: '14px',
          fontSize: '13px',
          color: '#FF453A',
          textAlign: 'right',
        }}>
          No hay bloques válidos para subir.
          {preview.duplicate_blocks > 0 && ' Todos los bloques ya existen en la BD.'}
        </p>
      )}
    </div>
  );
}

export default FilePreviewPanel;
