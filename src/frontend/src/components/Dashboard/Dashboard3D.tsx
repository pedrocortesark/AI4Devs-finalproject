/**
 * Dashboard3D Component
 * T-0504-FRONT: Main dashboard with 3D canvas
 * T-0508-FRONT: Part selection and details panel integration
 *
 * Orchestrates:
 * - Canvas3D for 3D visualization
 * - FilterBar for persistent bottom filter + selection hints
 * - DetailsPanel for selected part details (non-blocking side panel)
 * - EmptyState when no parts loaded
 * - LoadingOverlay during data fetch
 */

import React, { useState, useEffect } from 'react';
import type { Dashboard3DProps } from './Dashboard3D.types';
import { CAMERA_CONFIG, MESSAGES } from './Dashboard3D.constants';
import Canvas3D from './Canvas3D';
import EmptyState from './EmptyState';
import LoadingOverlay from './LoadingOverlay';
import { DetailsPanel } from '@/components/details/DetailsPanel';
import { FilterBar } from './FilterBar';
import ColorLegend from './ColorLegend';
import { usePartsStore } from '@/stores/parts.store';

const Dashboard3D: React.FC<Dashboard3DProps> = ({
  initialCameraPosition = CAMERA_CONFIG.POSITION,
  showStats = false,
  emptyMessage,
}) => {
  const parts = usePartsStore((state) => state.parts);
  const isLoading = usePartsStore((state) => state.isLoading);
  const error = usePartsStore((state) => state.error);
  const selectedId = usePartsStore((state) => state.selectedId);
  const colorMode = usePartsStore((state) => state.colorMode);
  const setColorMode = usePartsStore((state) => state.setColorMode);

  // CAD-style panel control: separate from selection state
  // Click on part → selects visually, Press 'D' → toggles details panel
  const [showDetailsPanel, setShowDetailsPanel] = useState(false);

  // Toggle details panel with 'D' key (CAD-style)
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingTarget = !!target && (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      );

      if (isTypingTarget) {
        return;
      }

      if (event.key === 'd' || event.key === 'D') {
        setShowDetailsPanel((prev) => (selectedId ? !prev : false));
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [selectedId]);

  // Close panel when selection cleared
  useEffect(() => {
    if (!selectedId) {
      setShowDetailsPanel(false);
    }
  }, [selectedId]);

  const isEmpty = parts.length === 0 && !isLoading;

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100vh',
        display: 'flex',
        overflow: 'hidden',
      }}
    >
      {/* Canvas Area */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          height: '100%',
        }}
      >
        {/* Render Canvas only when parts exist */}
        {!isEmpty && (
          <Canvas3D
            showStats={showStats}
            cameraConfig={{
              position: initialCameraPosition,
              fov: CAMERA_CONFIG.FOV,
              near: CAMERA_CONFIG.NEAR,
              far: CAMERA_CONFIG.FAR,
            }}
          />
        )}

        {/* Empty State (when no parts loaded) */}
        {isEmpty && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <EmptyState
              message={emptyMessage || MESSAGES.EMPTY_STATE}
              error={error}
              actionLabel="Subir Primera Pieza"
              actionHref="/upload"
            />
          </div>
        )}

        {/* Error Banner (shown even when parts exist) */}
        {error && !isEmpty && (
          <div
            role="alert"
            style={{
              position: 'absolute',
              top: '20px',
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '1rem 1.5rem',
              backgroundColor: '#FEE2E2',
              border: '1px solid #FCA5A5',
              borderRadius: '6px',
              color: '#991B1B',
              fontSize: '0.875rem',
              zIndex: 100,
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            }}
          >
            {error}
          </div>
        )}

        {/* Loading Overlay — only shown on initial load, not on background polls */}
        {isLoading && parts.length === 0 && <LoadingOverlay message={MESSAGES.LOADING} />}
        
        {/* Color mode toggle — top-left pill */}
        {!isEmpty && (
          <div
            style={{
              position: 'absolute',
              top: '16px',
              left: '16px',
              display: 'flex',
              background: 'rgba(0,0,0,0.65)',
              borderRadius: '20px',
              padding: '3px',
              gap: '2px',
              zIndex: 50,
              backdropFilter: 'blur(4px)',
            }}
          >
            {(['material', 'layer'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setColorMode(mode)}
                title={mode === 'material' ? 'Color por tipo de piedra (tipología)' : 'Color por layer de Rhino'}
                style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 500,
                  transition: 'background 0.15s, color 0.15s',
                  background: colorMode === mode ? '#ffffff' : 'transparent',
                  color: colorMode === mode ? '#111' : 'rgba(255,255,255,0.7)',
                }}
              >
                {mode === 'material' ? 'Material' : 'Textura'}
              </button>
            ))}
          </div>
        )}

        {/* Color legend — contextual meaning for the active color mode */}
        {!isEmpty && <ColorLegend />}

        {/* Persistent filter + selection hint bar */}
        <FilterBar
          selectedId={selectedId}
          showDetailsPanel={showDetailsPanel}
          onShowDetails={() => setShowDetailsPanel(true)}
        />
      </div>

      {/* Details Panel - Non-blocking side panel, toggles with 'D' key */}
      <DetailsPanel
        partId={selectedId}
        isOpen={showDetailsPanel}
        onClose={() => setShowDetailsPanel(false)}
      />

    </div>
  );
};

export default Dashboard3D;
