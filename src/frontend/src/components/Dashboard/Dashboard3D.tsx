/**
 * Dashboard3D Component
 * T-0504-FRONT: Main dashboard with 3D canvas and dockable sidebar
 * T-0508-FRONT: Part selection and modal integration
 * 
 * Orchestrates:
 * - Canvas3D for 3D visualization
 * - DraggableFiltersSidebar for filters UI
 * - PartDetailModal for selected part details (T-0508)
 * - EmptyState when no parts loaded
 * - LoadingOverlay during data fetch
 */

import React, { useState, useEffect } from 'react';
import type { Dashboard3DProps, DockPosition } from './Dashboard3D.types';
import { CAMERA_CONFIG, STORAGE_KEYS, MESSAGES } from './Dashboard3D.constants';
import Canvas3D from './Canvas3D';
import DraggableFiltersSidebar from './DraggableFiltersSidebar';
import FiltersSidebar from './FiltersSidebar';
import EmptyState from './EmptyState';
import LoadingOverlay from './LoadingOverlay';
import { PartDetailModal } from './PartDetailModal';
import { usePartsStore } from '@/stores/parts.store';
import { useLocalStorage } from '@/hooks/useLocalStorage';

const Dashboard3D: React.FC<Dashboard3DProps> = ({
  initialCameraPosition = CAMERA_CONFIG.POSITION,
  showStats = false,
  emptyMessage,
  initialSidebarDock = 'right',
}) => {
  const { parts, isLoading, error, selectedId, clearSelection } = usePartsStore();
  const [sidebarDock, setSidebarDock] = useLocalStorage<DockPosition>(
    STORAGE_KEYS.SIDEBAR_DOCK,
    initialSidebarDock
  );
  const [floatingPosition, setFloatingPosition] = useState({ x: 100, y: 100 });
  
  // CAD-style modal control: separate from selection state
  // Click on part → selects visually, Press 'D' → opens details modal
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  // Open details modal with 'D' key (CAD-style)
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'd' || event.key === 'D') {
        if (selectedId) {
          setShowDetailsModal(true);
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [selectedId]);
  
  // Close modal when selection cleared
  useEffect(() => {
    if (!selectedId) {
      setShowDetailsModal(false);
    }
  }, [selectedId]);

  const handleDockChange = (newDock: DockPosition) => {
    setSidebarDock(newDock);
  };

  const handlePositionChange = (newPosition: { x: number; y: number }) => {
    setFloatingPosition(newPosition);
  };

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

        {/* Loading Overlay */}
        {isLoading && <LoadingOverlay message={MESSAGES.LOADING} />}
        
        {/* CAD-style Selection Hint (when part selected but modal not open) */}
        {selectedId && !showDetailsModal && (
          <div
            style={{
              position: 'absolute',
              bottom: '30px',
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '12px 20px',
              backgroundColor: 'rgba(0, 0, 0, 0.85)',
              border: '1px solid rgba(59, 130, 246, 0.5)',
              borderRadius: '8px',
              color: 'white',
              fontSize: '14px',
              zIndex: 100,
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              display: 'flex',
              gap: '16px',
              alignItems: 'center',
            }}
          >
            <span>Pieza seleccionada</span>
            <span style={{ opacity: 0.6 }}>|</span>
            <span><kbd style={{ 
              padding: '2px 6px', 
              backgroundColor: 'rgba(255,255,255,0.1)',
              borderRadius: '4px',
              fontWeight: 'bold'
            }}>F</kbd> Zoom</span>
            <span style={{ opacity: 0.6 }}>|</span>
            <button
              onClick={() => setShowDetailsModal(true)}
              style={{
                padding: '4px 12px',
                backgroundColor: '#3B82F6',
                border: 'none',
                borderRadius: '4px',
                color: 'white',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
              }}
            >
              Ver Detalles (D)
            </button>
            <span style={{ opacity: 0.6 }}>|</span>
            <span><kbd style={{ 
              padding: '2px 6px', 
              backgroundColor: 'rgba(255,255,255,0.1)',
              borderRadius: '4px',
              fontWeight: 'bold'
            }}>ESC</kbd> Deseleccionar</span>
          </div>
        )}
      </div>

      {/* Part Detail Modal - Only opens with 'D' key or button (CAD-style) */}
      {selectedId && showDetailsModal && (
        <PartDetailModal
          isOpen={showDetailsModal}
          partId={selectedId}
          onClose={() => {
            setShowDetailsModal(false);
            clearSelection();
          }}
          enableNavigation={false}
          filters={null}
        />
      )}

      {/* Sidebar with Filters */}
      <DraggableFiltersSidebar
        dockPosition={sidebarDock}
        onDockChange={handleDockChange}
        floatingPosition={floatingPosition}
        onPositionChange={handlePositionChange}
      >
        <FiltersSidebar />
      </DraggableFiltersSidebar>
    </div>
  );
};

export default Dashboard3D;
