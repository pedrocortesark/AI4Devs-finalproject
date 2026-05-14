/**
 * App Component - Root Component
 * Sagrada Familia Parts Manager
 *
 * Routes (no router library, handled via window.location + Vercel SPA rewrites):
 *   /        → Dashboard3D (landing page with 3D canvas)
 *   /upload  → UploadPage (file upload form)
 */

import { useEffect, useState } from 'react';
import Dashboard3D from './components/Dashboard/Dashboard3D';
import { UploadZone } from './components/UploadZone';
import { FilePreviewPanel } from './components/FilePreviewPanel';
import { BlockIngestionStatus } from './components/BlockIngestionStatus';
import { UploadDrawer } from './components/UploadDrawer';
import { usePartsStore } from './stores/parts.store';
import { previewFile } from './services/preview.service';
import { resetBlocks } from './services/admin.service';
import { getPresignedUrl, uploadToStorage, confirmUpload } from './services/upload.service';
import { getSupabaseClient } from './services/supabase.client';
import type { FilePreviewResponse } from './types/preview';
import type { UploadProgress } from './types/upload';

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

// ── Upload Page — 3-phase state machine ─────────────────────────────────────
//
//  Phase 0 (idle):      UploadZone (file drop)
//  Phase 1 (preview):   FilePreviewPanel (analysis table + Subir/Cancelar)
//  Phase 2 (ingesting): progress bar → BlockIngestionStatus (real-time)

type UploadPhase = 0 | 1 | 2;

function UploadPage() {
  const { fetchParts } = usePartsStore();

  // ── State ──────────────────────────────────────────────────────────────────
  const [phase, setPhase] = useState<UploadPhase>(0);

  // Phase 1
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<FilePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Phase 2
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileKey, setFileKey] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadErrorDetails, setUploadErrorDetails] = useState<{ code?: string; message: string } | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [uploadAttempts, setUploadAttempts] = useState(0);

  // T-1807: Progress Drawer
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [trackingBlockId, setTrackingBlockId] = useState<string | null>(null);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function resetToPhase0() {
    setPhase(0);
    setSelectedFile(null);
    setPreviewData(null);
    setPreviewLoading(false);
    setPreviewError(null);
    setUploadProgress(0);
    setFileKey(null);
    setUploadError(null);
    setUploadErrorDetails(null);
    setIsConfirming(false);
    setUploadAttempts(0);
    setIsDrawerOpen(false);
    setTrackingBlockId(null);
  }

  // ── Phase 0 → 1: file selected ────────────────────────────────────────────

  async function handleFilesAccepted(files: File[]) {
    const file = files[0];
    if (!file) return;
    setSelectedFile(file);
    setPreviewLoading(true);
    setPreviewError(null);
    setPhase(1);
    try {
      const data = await previewFile(file);
      setPreviewData(data);
    } catch (e: any) {
      setPreviewError(e.message ?? 'Error al analizar el archivo');
    } finally {
      setPreviewLoading(false);
    }
  }

  // ── Phase 1 → 2: user confirms upload ────────────────────────────────────

  async function handleConfirm() {
    if (!selectedFile || !previewData) return;
    setIsConfirming(true);
    setUploadError(null);
    setUploadErrorDetails(null);
    setUploadAttempts(prev => prev + 1);
    
    try {
      const { upload_url, file_id, file_key } = await getPresignedUrl(
        selectedFile.name,
        selectedFile.size
      );
      setPhase(2);

      await uploadToStorage(upload_url, selectedFile, (p: UploadProgress) => {
        setUploadProgress(p.percentage);
      });

      await confirmUpload(file_id, file_key);
      setFileKey(file_key);
      fetchParts();

      // T-1807: Query blocks table to get first block_id for progress tracking
      try {
        const supabase = getSupabaseClient();
        const { data: blocks, error: blocksError } = await supabase
          .from('blocks')
          .select('id')
          .eq('url_original', file_key)
          .limit(1);
        
        if (!blocksError && blocks && blocks.length > 0) {
          const blockId = blocks[0].id;
          setTrackingBlockId(blockId);
          setIsDrawerOpen(true);
        }
      } catch (drawerError) {
        console.warn('[UploadPage] Failed to fetch block ID for drawer:', drawerError);
        // Non-critical error, drawer won't open but upload continues
      }
    } catch (e: any) {
      const errorMessage = e.message ?? 'Error al subir el archivo';
      const errorCode = e.response?.status ? `HTTP ${e.response.status}` : e.code;
      
      setUploadError(errorMessage);
      setUploadErrorDetails({
        code: errorCode,
        message: e.response?.data?.detail || errorMessage
      });
      setIsConfirming(false);
      setPhase(1); // Return to preview phase to allow retry
    }
  }

  // ── Dev: reset all blocks ─────────────────────────────────────────────────

  async function handleReset() {
    if (isResetting) return;
    setIsResetting(true);
    try {
      await resetBlocks();
      resetToPhase0();
    } catch (e: any) {
      alert(`Error al limpiar BD: ${e.message}`);
    } finally {
      setIsResetting(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

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
            {phase === 0 && 'Importar archivo .3dm'}
            {phase === 1 && 'Análisis previo'}
            {phase === 2 && 'Ingesta en progreso'}
          </h1>
          <p style={{
            margin: 0,
            fontSize: '15px',
            color: DS.textSecondary,
            lineHeight: 1.6,
          }}>
            {phase === 0 && 'Sube tu modelo de Rhino para procesar las piezas y visualizarlas en el dashboard 3D.'}
            {phase === 1 && (previewData
              ? `${previewData.filename} — ${previewData.total_blocks} bloques encontrados`
              : 'Analizando archivo…'
            )}
            {phase === 2 && 'Los bloques se están registrando y validando en tiempo real.'}
          </p>
        </div>

        {/* Card — width expands on phase 1/2 to show table */}
        <div style={{
          width: '100%',
          maxWidth: phase === 0 ? '560px' : '760px',
          backgroundColor: DS.bgCard,
          borderRadius: '16px',
          border: `1px solid ${DS.borderMid}`,
          padding: '32px',
          boxShadow: '0 8px 48px rgba(0, 0, 0, 0.5)',
          transition: 'max-width 0.3s ease',
        }}>

          {/* ── Phase 0: drop zone ── */}
          {phase === 0 && (
            <UploadZone
              onFilesAccepted={handleFilesAccepted}
              onFilesRejected={(rejections) => {
                const msg = rejections[0]?.errors[0]?.message ?? 'Archivo rechazado';
                setPreviewError(msg);
              }}
            />
          )}

          {/* ── Phase 1: preview ── */}
          {phase === 1 && (
            <>
              {previewLoading && (
                <p style={{ color: DS.textSecondary, fontSize: '14px', textAlign: 'center', padding: '24px 0' }}>
                  Analizando archivo…
                </p>
              )}
              {previewError && (
                <div style={{
                  padding: '14px 16px',
                  backgroundColor: 'rgba(255, 59, 48, 0.08)',
                  border: '1px solid rgba(255, 59, 48, 0.3)',
                  borderRadius: '10px',
                  fontSize: '14px',
                  color: '#FF6B60',
                  marginBottom: '16px',
                }}>
                  {previewError}
                </div>
              )}
              {/* Upload error with retry button */}
              {uploadError && (
                <div style={{
                  padding: '16px',
                  backgroundColor: 'rgba(255, 59, 48, 0.08)',
                  border: '1px solid rgba(255, 59, 48, 0.3)',
                  borderRadius: '10px',
                  marginBottom: '16px',
                }}>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '10px',
                    marginBottom: '12px'
                  }}>
                    <span style={{ flexShrink: 0, fontSize: '16px' }}>⚠</span>
                    <div style={{ flex: 1 }}>
                      <p style={{ 
                        margin: '0 0 6px', 
                        fontSize: '14px', 
                        fontWeight: 600, 
                        color: '#FF6B60' 
                      }}>
                        Error al subir el archivo (Intento {uploadAttempts})
                      </p>
                      <p style={{ 
                        margin: '0 0 6px', 
                        fontSize: '13px', 
                        color: '#FF6B60',
                        opacity: 0.9 
                      }}>
                        {uploadError}
                      </p>
                      {uploadErrorDetails && (
                        <p style={{ 
                          margin: 0, 
                          fontSize: '12px', 
                          color: 'rgba(255, 107, 96, 0.7)',
                          fontFamily: 'monospace'
                        }}>
                          {uploadErrorDetails.code && `[${uploadErrorDetails.code}] `}
                          {uploadErrorDetails.message !== uploadError && uploadErrorDetails.message}
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={handleConfirm}
                    disabled={isConfirming || uploadAttempts >= 3}
                    style={{
                      width: '100%',
                      padding: '8px 16px',
                      backgroundColor: uploadAttempts >= 3 ? DS.bgSurface : DS.blue,
                      color: DS.textPrimary,
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: uploadAttempts >= 3 ? 'not-allowed' : 'pointer',
                      opacity: isConfirming ? 0.5 : 1,
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {isConfirming 
                      ? 'Reintentando...' 
                      : uploadAttempts >= 3 
                        ? 'Máximo de reintentos alcanzado' 
                        : `Reintentar subida (${uploadAttempts}/3)`}
                  </button>
                  {uploadAttempts >= 3 && (
                    <button
                      onClick={resetToPhase0}
                      style={{
                        width: '100%',
                        padding: '8px 16px',
                        backgroundColor: 'transparent',
                        color: DS.textSecondary,
                        border: `1px solid ${DS.borderMid}`,
                        borderRadius: '8px',
                        fontSize: '13px',
                        fontWeight: 500,
                        cursor: 'pointer',
                        marginTop: '8px',
                      }}
                    >
                      Cancelar e intentar con otro archivo
                    </button>
                  )}
                </div>
              )}
              {previewData && !previewLoading && (
                <FilePreviewPanel
                  preview={previewData}
                  onConfirm={handleConfirm}
                  onCancel={resetToPhase0}
                  isUploading={isConfirming}
                />
              )}
            </>
          )}

          {/* ── Phase 2: upload progress + ingestion status ── */}
          {phase === 2 && (
            <>
              {/* Progress bar while uploading to storage */}
              {uploadProgress < 100 && !fileKey && (
                <div style={{ marginBottom: '24px' }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '8px',
                  }}>
                    <span style={{ fontSize: '13px', color: DS.textSecondary }}>Subiendo a Storage…</span>
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

              {/* Upload error */}
              {uploadError && (
                <div style={{
                  padding: '14px 16px',
                  backgroundColor: 'rgba(255, 59, 48, 0.08)',
                  border: '1px solid rgba(255, 59, 48, 0.3)',
                  borderRadius: '10px',
                  fontSize: '14px',
                  color: '#FF6B60',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  marginBottom: '16px',
                }}>
                  <span style={{ flexShrink: 0 }}>✕</span>
                  <span>{uploadError}</span>
                </div>
              )}

              {/* Real-time ingestion status (shown after confirm completes) */}
              {fileKey && (
                <BlockIngestionStatus
                  fileKey={fileKey}
                  onNewUpload={resetToPhase0}
                />
              )}
            </>
          )}

          {/* ── Error from phase 0 (file rejection) ── */}
          {phase === 0 && previewError && (
            <div style={{
              marginTop: '16px',
              padding: '14px 16px',
              backgroundColor: 'rgba(255, 59, 48, 0.08)',
              border: '1px solid rgba(255, 59, 48, 0.3)',
              borderRadius: '10px',
              fontSize: '14px',
              color: '#FF6B60',
            }}>
              {previewError}
            </div>
          )}
        </div>

        {/* ── Footer text ── */}
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

        {/* ── Dev-only: Limpiar BD button ── */}
        {import.meta.env.VITE_ENV !== 'production' && (
          <button
            onClick={handleReset}
            disabled={isResetting}
            style={{
              marginTop: '16px',
              padding: '6px 14px',
              backgroundColor: 'transparent',
              border: '1px solid rgba(255, 59, 48, 0.3)',
              color: 'rgba(255, 59, 48, 0.6)',
              borderRadius: '6px',
              cursor: isResetting ? 'not-allowed' : 'pointer',
              fontSize: '11px',
              fontWeight: 500,
              opacity: isResetting ? 0.5 : 1,
              fontFamily: DS.font,
            }}
          >
            {isResetting ? 'Limpiando…' : 'Limpiar BD (dev)'}
          </button>
        )}
      </main>

      {/* T-1807: Upload Progress Drawer */}
      <UploadDrawer
        isOpen={isDrawerOpen}
        blockId={trackingBlockId}
        filename={selectedFile?.name ?? null}
        onClose={() => setIsDrawerOpen(false)}
      />
    </div>
  );
}

// ── Dashboard Page ───────────────────────────────────────────────────────────

function DashboardPage() {
  const fetchParts = usePartsStore((state) => state.fetchParts);

  useEffect(() => {
    fetchParts();
    // Poll every 30s so newly processed parts appear without manual refresh.
    // silent=true skips the loading indicator so the 3D view doesn't flash.
    const interval = setInterval(() => fetchParts(true), 30_000);
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
