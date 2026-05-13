/**
 * UploadDrawer Component - T-1807
 * 
 * Slide-in drawer that displays real-time progress of file upload + validation.
 * Shows 8-step StateGraph workflow with ETA estimation.
 * 
 * Triggered after user confirms upload and receives blockId from backend.
 */

import { useEffect } from 'react';
import { useUploadProgressStore } from '../stores/uploadProgress.store';
import { useSupabaseEvents } from '../hooks/useSupabaseEvents';
import { ProgressSteps } from './ProgressSteps';

interface UploadDrawerProps {
  /**
   * Whether the drawer is visible
   */
  isOpen: boolean;
  
  /**
   * Block ID to track (null = no tracking)
   */
  blockId: string | null;
  
  /**
   * Filename being processed
   */
  filename: string | null;
  
  /**
   * Callback when drawer is closed
   */
  onClose: () => void;
}

// ── Design Tokens ─────────────────────────────────────────────────────────────
const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  bgSurface: '#2C2C2E',
  bgCard: '#1C1C1E',
  bgOverlay: 'rgba(0, 0, 0, 0.6)',
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid: 'rgba(255, 255, 255, 0.14)',
  textPrimary: 'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary: 'rgba(255, 255, 255, 0.3)',
  blue: '#007AFF',
  green: '#34C759',
  yellow: '#FF9F0A',
  red: '#FF453A',
} as const;

export function UploadDrawer({ isOpen, blockId, filename, onClose }: UploadDrawerProps) {
  const {
    steps,
    currentStep,
    status,
    eta,
    finalMessage,
    startProgress,
    reset,
  } = useUploadProgressStore();
  
  // Subscribe to Supabase Realtime events
  useSupabaseEvents(blockId);
  
  // Initialize progress when drawer opens with a blockId
  useEffect(() => {
    if (isOpen && blockId && filename) {
      startProgress(blockId, filename);
    }
  }, [isOpen, blockId, filename, startProgress]);
  
  // Reset when drawer closes
  const handleClose = () => {
    reset();
    onClose();
  };
  
  // Auto-close after 5 seconds if completed successfully
  useEffect(() => {
    if (status === 'completed') {
      const timer = setTimeout(() => {
        handleClose();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [status]);
  
  if (!isOpen) return null;
  
  return (
    <>
      {/* Overlay */}
      <div
        onClick={handleClose}
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: DS.bgOverlay,
          backdropFilter: 'blur(4px)',
          zIndex: 999,
          animation: 'fadeIn 0.2s ease',
        }}
      />
      
      {/* Drawer */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '480px',
          maxWidth: '90vw',
          backgroundColor: DS.bgSurface,
          boxShadow: '-4px 0 24px rgba(0, 0, 0, 0.4)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          fontFamily: DS.font,
          animation: 'slideIn 0.3s ease',
        }}
      >
        {/* Keyframes */}
        <style>{`
          @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
        `}</style>
        
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: `1px solid ${DS.borderSubtle}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2
              style={{
                margin: 0,
                fontSize: '20px',
                fontWeight: 700,
                color: DS.textPrimary,
              }}
            >
              Procesando archivo
            </h2>
            {filename && (
              <p
                style={{
                  margin: '4px 0 0 0',
                  fontSize: '14px',
                  color: DS.textSecondary,
                  fontFamily: 'monospace',
                }}
              >
                {filename}
              </p>
            )}
          </div>
          
          {/* Close Button */}
          <button
            onClick={handleClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              color: DS.textSecondary,
              cursor: 'pointer',
              padding: '4px',
              lineHeight: 1,
            }}
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>
        
        {/* Content */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
          }}
        >
          {/* Status Banner */}
          {(status === 'completed' || status === 'error') && (
            <div
              style={{
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '20px',
                backgroundColor: status === 'completed' ? 'rgba(52, 199, 89, 0.12)' : 'rgba(255, 69, 58, 0.12)',
                border: `1px solid ${status === 'completed' ? DS.green : DS.red}40`,
              }}
            >
              <div
                style={{
                  fontSize: '16px',
                  fontWeight: 600,
                  color: status === 'completed' ? DS.green : DS.red,
                  marginBottom: '4px',
                }}
              >
                {status === 'completed' ? '✓ Validación Completada' : '✕ Validación Fallida'}
              </div>
              {finalMessage && (
                <div style={{ fontSize: '14px', color: DS.textSecondary }}>
                  {finalMessage}
                </div>
              )}
            </div>
          )}
          
          {/* ETA Display */}
          {status === 'processing' && eta !== null && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                marginBottom: '20px',
                backgroundColor: 'rgba(0, 122, 255, 0.08)',
                border: `1px solid ${DS.blue}40`,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span style={{ fontSize: '14px', color: DS.textSecondary }}>
                Tiempo estimado restante:
              </span>
              <span
                style={{
                  fontSize: '16px',
                  fontWeight: 700,
                  color: DS.blue,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatETA(eta)}
              </span>
            </div>
          )}
          
          {/* Progress Steps */}
          <ProgressSteps steps={steps} currentStep={currentStep} />
        </div>
        
        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: `1px solid ${DS.borderSubtle}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: '12px', color: DS.textTertiary }}>
            Block ID: <span style={{ fontFamily: 'monospace' }}>{blockId?.substring(0, 8)}...</span>
          </div>
          
          {status === 'completed' && (
            <button
              onClick={handleClose}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                backgroundColor: DS.green,
                color: '#fff',
                border: 'none',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cerrar
            </button>
          )}
        </div>
      </div>
    </>
  );
}

// ── Helper Functions ──────────────────────────────────────────────────────────

function formatETA(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
