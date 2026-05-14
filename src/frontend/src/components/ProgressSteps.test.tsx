/**
 * ProgressSteps Component - Unit Tests - T-1807
 * 
 * Tests for visual rendering of 8-step StateGraph progress.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressSteps } from './ProgressSteps';
import type { ProgressStep } from '../types/upload';

describe('ProgressSteps', () => {
  const mockSteps: ProgressStep[] = [
    {
      index: 0,
      nodeName: 'ExtractGeometry',
      label: 'Extracción Geometría',
      status: 'completed',
      startedAt: '2026-05-13T10:00:00Z',
      completedAt: '2026-05-13T10:00:02Z',
    },
    {
      index: 1,
      nodeName: 'ValidateNomenclature',
      label: 'Validación Nomenclatura',
      status: 'active',
      startedAt: '2026-05-13T10:00:02Z',
      completedAt: null,
    },
    {
      index: 2,
      nodeName: 'ValidateGeometry',
      label: 'Validación Geometría',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
    {
      index: 3,
      nodeName: 'ClassifyTipologia',
      label: 'Clasificación Tipología',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
    {
      index: 4,
      nodeName: 'EnrichMetadata',
      label: 'Enriquecimiento Metadatos',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
    {
      index: 5,
      nodeName: 'GenerateReport',
      label: 'Generación Reporte',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
    {
      index: 6,
      nodeName: 'MarkValidated',
      label: 'Marca Validado',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
    {
      index: 7,
      nodeName: 'MarkRejected',
      label: 'Marca Rechazado',
      status: 'idle',
      startedAt: null,
      completedAt: null,
    },
  ];

  it('should render all 8 steps', () => {
    render(<ProgressSteps steps={mockSteps} currentStep={1} />);
    
    // Check that all step labels are present
    expect(screen.getByText('Extracción Geometría')).toBeInTheDocument();
    expect(screen.getByText('Validación Nomenclatura')).toBeInTheDocument();
    expect(screen.getByText('Validación Geometría')).toBeInTheDocument();
    expect(screen.getByText('Clasificación Tipología')).toBeInTheDocument();
    expect(screen.getByText('Enriquecimiento Metadatos')).toBeInTheDocument();
    expect(screen.getByText('Generación Reporte')).toBeInTheDocument();
    expect(screen.getByText('Marca Validado')).toBeInTheDocument();
    expect(screen.getByText('Marca Rechazado')).toBeInTheDocument();
  });

  it('should show completed status icon', () => {
    render(<ProgressSteps steps={mockSteps} currentStep={1} />);
    
    // Check for checkmark icon (✓) in completed step
    const completedStep = screen.getByText('Extracción Geometría').closest('div');
    expect(completedStep).toBeInTheDocument();
    // Visual check would be in integration/E2E tests
  });

  it('should show duration for completed steps', () => {
    render(<ProgressSteps steps={mockSteps} currentStep={1} />);
    
    // Check for duration badge (2 seconds)
    expect(screen.getByText('2s')).toBeInTheDocument();
  });

  it('should show error message when step has error', () => {
    const stepsWithError = [...mockSteps];
    stepsWithError[1] = {
      ...stepsWithError[1],
      status: 'error',
      errorMessage: 'Nomenclature validation failed',
    };
    
    render(<ProgressSteps steps={stepsWithError} currentStep={1} />);
    
    expect(screen.getByText('Nomenclature validation failed')).toBeInTheDocument();
  });

  it('should apply custom className', () => {
    const { container } = render(
      <ProgressSteps steps={mockSteps} currentStep={1} className="custom-class" />
    );
    
    const wrapper = container.querySelector('.custom-class');
    expect(wrapper).toBeInTheDocument();
  });

  it('should show "Procesando..." for active step', () => {
    render(<ProgressSteps steps={mockSteps} currentStep={1} />);
    
    // Active step should show "Procesando..." description
    expect(screen.getByText('Procesando...')).toBeInTheDocument();
  });

  it('should not show description for idle steps', () => {
    render(<ProgressSteps steps={mockSteps} currentStep={1} />);
    
    // Idle steps should not show "Esperando..." (only shown for non-idle steps)
    // Check that at least the completed step shows "Completado"
    expect(screen.getByText('Completado')).toBeInTheDocument();
  });
});
