/**
 * PartViewer3D Component Tests
 *
 * Three.js/R3F canvas cannot run in jsdom, so we test:
 * - null url → renders "no geometry" fallback (no canvas at all)
 * - valid url → renders the canvas wrapper element
 *
 * @module details/PartViewer3D.test
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PartViewer3D } from './PartViewer3D';

// Mock @react-three/fiber Canvas — jsdom has no WebGL
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="r3f-canvas">{children}</div>
  ),
  useLoader: vi.fn(() => ({ clone: () => ({ traverse: vi.fn() }) })),
  useThree: vi.fn(() => ({
    camera: { position: { set: vi.fn() }, lookAt: vi.fn(), updateProjectionMatrix: vi.fn() },
  })),
}));

vi.mock('@react-three/drei', () => ({
  OrbitControls: () => null,
  Html: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('three/examples/jsm/loaders/OBJLoader.js', () => ({
  OBJLoader: class {},
}));

describe('PartViewer3D', () => {
  it('shows "no geometry" fallback when url is null', () => {
    render(<PartViewer3D url={null} />);
    expect(screen.getByText(/geometría no disponible/i)).toBeInTheDocument();
    expect(screen.queryByTestId('r3f-canvas')).not.toBeInTheDocument();
  });

  it('renders the 3D canvas wrapper when url is provided', () => {
    render(
      <PartViewer3D
        url="https://cdn.example.com/part.obj"
        materialType="Montjuïc"
        bbox={{ min: [0, 0, 0], max: [1, 1, 1] }}
      />
    );
    expect(screen.getByTestId('part-viewer-3d')).toBeInTheDocument();
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();
  });

  it('renders canvas even when materialType is unknown/null', () => {
    render(<PartViewer3D url="https://cdn.example.com/part.obj" materialType={null} />);
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();
  });

  it('renders canvas even when bbox is null', () => {
    render(<PartViewer3D url="https://cdn.example.com/part.obj" bbox={null} />);
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();
  });
});
