/**
 * App Component - Root Component
 * Sagrada Familia Parts Manager
 *
 * Routes (no router library, handled via window.location + Vercel SPA rewrites):
 *   /        → Dashboard3D (landing page with 3D canvas)
 *   /upload  → UploadPage (file upload form)
 */

import { useEffect, useState } from 'react';
import FileUploader from './components/FileUploader';
import Dashboard3D from './components/Dashboard/Dashboard3D';
import { usePartsStore } from './stores/parts.store';
import type { UploadError, UploadProgress } from './types/upload';

// ── Design tokens ─────────────────────────────────────────────────────────────
const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  bgPage:    '#000000',
  bgCard:    '#1C1C1E',
  bgSurface: '#2C2C2E',
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid:    'rgba(255, 255, 255, 0.14)',
  textPrimary:   'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary:  'rgba(255, 255, 255, 0.3)',
  blue:  '#007AFF',
  green: '#34C759',
} as const;

// ── Upload Page ──────────────────────────────────────────────────────────────

function UploadPage() {
  const { fetchParts } = usePartsStore();
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUploadComplete = (fileId: string) => {
    setUploadedFileId(fileId);
    setUploadProgress(0);
    setUploadError(null);
    fetchParts();
  };

  const handleUploadError = (error: UploadError) => {
    console.error('Upload error:', error);
    setUploadError(error.message);
    setUploadProgress(0);
  };

  const handleProgress = (progress: UploadProgress) => {
    setUploadProgress(progress.percentage);
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: DS.bgPage,
      fontFamily: DS.font,
      color: DS.textPrimary,
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* ── Nav bar ── */}
      <nav style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        height: '52px',
        borderBottom: `1px solid ${DS.borderSubtle}`,
        flexShrink: 0,
      }}>
        <a href="/" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          textDecoration: 'none',
          color: DS.blue,
          fontSize: '14px',
          fontWeight: 500,
        }}>
          <span style={{ fontSize: '18px', lineHeight: 1 }}>‹</span>
          Dashboard
        </a>

        <span style={{
          fontSize: '13px',
          fontWeight: 600,
          letterSpacing: '0.08em',
          color: DS.textSecondary,
          textTransform: 'uppercase',
        }}>
          SF-PM
        </span>

        <span style={{ width: '80px' }} />
      </nav>

      {/* ── Main content ── */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '56px 24px 80px',
      }}>
        {/* Page heading */}
        <div style={{ textAlign: 'center', marginBottom: '40px', maxWidth: '480px' }}>
          <h1 style={{
            margin: '0 0 10px',
            fontSize: '28px',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: DS.textPrimary,
          }}>
            Importar archivo .3dm
          </h1>
          <p style={{
            margin: 0,
            fontSize: '15px',
            color: DS.textSecondary,
            lineHeight: 1.6,
          }}>
            Sube tu modelo de Rhino para procesar las piezas y visualizarlas en el dashboard 3D.
          </p>
        </div>

        {/* Upload card */}
        <div style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: DS.bgCard,
          borderRadius: '16px',
          border: `1px solid ${DS.borderMid}`,
          padding: '32px',
          boxShadow: '0 8px 48px rgba(0, 0, 0, 0.5)',
        }}>
          <FileUploader
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
            onProgress={handleProgress}
          />

          {/* Progress bar */}
          {uploadProgress > 0 && uploadProgress < 100 && (
            <div style={{ marginTop: '20px' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '8px',
              }}>
                <span style={{ fontSize: '13px', color: DS.textSecondary }}>Subiendo…</span>
                <span style={{
                  fontSize: '13px',
                  color: DS.textSecondary,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {uploadProgress.toFixed(0)}%
                </span>
              </div>
              <div style={{
                width: '100%',
                height: '4px',
                backgroundColor: DS.bgSurface,
                borderRadius: '2px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${uploadProgress}%`,
                  height: '100%',
                  backgroundColor: DS.blue,
                  borderRadius: '2px',
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </div>
          )}

          {/* Error state */}
          {uploadError && (
            <div style={{
              marginTop: '20px',
              padding: '14px 16px',
              backgroundColor: 'rgba(255, 59, 48, 0.08)',
              border: '1px solid rgba(255, 59, 48, 0.3)',
              borderRadius: '10px',
              fontSize: '14px',
              color: '#FF6B60',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}>
              <span style={{ flexShrink: 0 }}>✕</span>
              <span>{uploadError}</span>
            </div>
          )}

          {/* Success state */}
          {uploadedFileId && (
            <div style={{
              marginTop: '20px',
              padding: '20px',
              backgroundColor: 'rgba(52, 199, 89, 0.07)',
              border: '1px solid rgba(52, 199, 89, 0.22)',
              borderRadius: '12px',
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                marginBottom: '14px',
              }}>
                <span style={{ fontSize: '18px', color: DS.green }}>✓</span>
                <span style={{ fontSize: '15px', fontWeight: 600, color: DS.green }}>
                  Archivo subido correctamente
                </span>
              </div>
              <p style={{
                margin: '0 0 16px',
                fontSize: '11px',
                color: DS.textTertiary,
                fontFamily: 'monospace',
                wordBreak: 'break-all',
              }}>
                {uploadedFileId}
              </p>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <a
                  href="/"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '8px 18px',
                    backgroundColor: DS.blue,
                    color: 'white',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                >
                  Ver en Dashboard
                </a>
                <button
                  onClick={() => { setUploadedFileId(null); setUploadError(null); }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '8px 18px',
                    backgroundColor: 'transparent',
                    border: `1px solid ${DS.borderMid}`,
                    color: DS.textSecondary,
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 500,
                    fontFamily: DS.font,
                  }}
                >
                  Subir otro archivo
                </button>
              </div>
            </div>
          )}
        </div>

        <p style={{
          marginTop: '24px',
          fontSize: '12px',
          color: DS.textTertiary,
          textAlign: 'center',
          maxWidth: '400px',
          lineHeight: 1.7,
        }}>
          El archivo será procesado automáticamente. Las piezas aparecerán en el dashboard una vez completado el análisis geométrico.
        </p>
      </main>
    </div>
  );
}

// ── Dashboard Page ───────────────────────────────────────────────────────────

function DashboardPage() {
  const fetchParts = usePartsStore((state) => state.fetchParts);

  useEffect(() => {
    fetchParts();
    // Poll every 30s so newly processed parts appear without manual refresh
    const interval = setInterval(fetchParts, 30_000);
    return () => clearInterval(interval);
  }, [fetchParts]);

  return <Dashboard3D />;
}

// ── Root Router ──────────────────────────────────────────────────────────────

function App() {
  const path = window.location.pathname;

  if (path === '/upload') {
    return <UploadPage />;
  }

  return <DashboardPage />;
}

export default App;
