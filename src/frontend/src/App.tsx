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

// ── Upload Page ──────────────────────────────────────────────────────────────

function UploadPage() {
  const { fetchParts } = usePartsStore();
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  const handleUploadComplete = (fileId: string) => {
    setUploadedFileId(fileId);
    setUploadProgress(0);
    // Refresh parts store so dashboard picks up the new piece
    fetchParts();
  };

  const handleUploadError = (error: UploadError) => {
    console.error('Upload error:', error);
    alert(`Upload failed: ${error.message}`);
    setUploadProgress(0);
  };

  const handleProgress = (progress: UploadProgress) => {
    setUploadProgress(progress.percentage);
  };

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      padding: '2rem',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <header style={{ marginBottom: '2rem' }}>
        <a href="/" style={{ textDecoration: 'none', color: 'inherit' }}>
          <h1>Sagrada Familia Parts Manager</h1>
        </a>
        <p style={{ color: '#666' }}>
          Upload and manage .3dm files for the Sagrada Familia project
        </p>
      </header>

      <main>
        <FileUploader
          onUploadComplete={handleUploadComplete}
          onUploadError={handleUploadError}
          onProgress={handleProgress}
        />

        {uploadProgress > 0 && uploadProgress < 100 && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: '#e0e0e0',
              borderRadius: '4px',
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${uploadProgress}%`,
                height: '100%',
                backgroundColor: '#4caf50',
                transition: 'width 0.3s ease',
              }} />
            </div>
            <p style={{ textAlign: 'center', marginTop: '0.5rem', color: '#666' }}>
              {uploadProgress.toFixed(0)}%
            </p>
          </div>
        )}

        {uploadedFileId && (
          <div style={{
            marginTop: '2rem',
            padding: '1rem',
            backgroundColor: '#e8f5e9',
            borderRadius: '4px',
            border: '1px solid #4caf50',
          }}>
            <h3 style={{ marginTop: 0 }}>✅ Upload Successful</h3>
            <p><strong>File ID:</strong> {uploadedFileId}</p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <a
                href="/"
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#4caf50',
                  color: 'white',
                  borderRadius: '4px',
                  textDecoration: 'none',
                  fontSize: '0.875rem',
                }}
              >
                Ver en Dashboard
              </a>
              <button
                onClick={() => setUploadedFileId(null)}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#fff',
                  border: '1px solid #4caf50',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                Upload Another File
              </button>
            </div>
          </div>
        )}
      </main>

      <footer style={{
        marginTop: '4rem',
        paddingTop: '2rem',
        borderTop: '1px solid #e0e0e0',
        color: '#999',
        fontSize: '0.875rem',
      }}>
        <p>AI4Devs - Technical Master's Final Project</p>
      </footer>
    </div>
  );
}

// ── Dashboard Page ───────────────────────────────────────────────────────────

function DashboardPage() {
  const { fetchParts } = usePartsStore();

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
