import '@testing-library/jest-dom';
import { vi } from 'vitest';
import React from 'react';

// ---------------------------------------------------------------------------
// Mock HTMLCanvasElement.getContext to return mock WebGL context by default
// This allows Three.js mocks to work without real WebGL in jsdom
// Individual tests can override this (e.g., ERR-INT-03 sets it to null)
// ---------------------------------------------------------------------------
HTMLCanvasElement.prototype.getContext = vi.fn((contextId: string) => {
 if (contextId === 'webgl' || contextId === 'webgl2') {
    // Return mock WebGL context
    return {} as any;
  }
  // For other contexts (2d, etc.), return mock as well
  return {} as any;
});

// ---------------------------------------------------------------------------
// @react-three/fiber — Canvas cannot use real WebGL in jsdom.
// Replace with a plain <div data-testid="three-canvas"> that can handle click events.
// Also mock three.js primitive elements (group, mesh, etc.) as simple divs.
// ---------------------------------------------------------------------------
vi.mock('@react-three/fiber', () => {
  // Mock Vector3-like object with methods used by CameraController
  const createMockVector3 = (x = 0, y = 0, z = 0) => ({
    x, y, z,
    clone: vi.fn(function(this: any) { return createMockVector3(this.x, this.y, this.z); }),
    sub: vi.fn(function(this: any, v: any) { 
      this.x -= v.x; this.y -= v.y; this.z -= v.z; 
      return this; 
    }),
    add: vi.fn(function(this: any, v: any) { 
      this.x += v.x; this.y += v.y; this.z += v.z; 
      return this; 
    }),
    normalize: vi.fn(function(this: any) { 
      const len = Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z);
      if (len > 0) { this.x /= len; this.y /= len; this.z /= len; }
      return this; 
    }),
    multiplyScalar: vi.fn(function(this: any, s: number) { 
      this.x *= s; this.y *= s; this.z *= s; 
      return this; 
    }),
    length: vi.fn(function(this: any) { 
      return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z); 
    }),
    toArray: vi.fn(function(this: any) { return [this.x, this.y, this.z]; }),
  });

  // Mock OrbitControls-like object
  const mockControls = {
    target: createMockVector3(0, 0, 0),
    update: vi.fn(),
  };

  // Mock useThree state
  const mockState = {
    camera: { 
      position: createMockVector3(5, 8, 12),
      fov: 50,
      aspect: 16/9,
      updateProjectionMatrix: vi.fn(),
    }, 
    scene: {}, 
    gl: {},
    controls: mockControls,
  };

  return {
    Canvas: ({ children, onPointerMissed, ...props }: any) =>
      React.createElement(
        'div',
        {
          'data-testid': 'three-canvas',
          onClick: onPointerMissed, // Simulate onPointerMissed with click for testing
          ...props
        },
        children
      ),
    useFrame: vi.fn(),
    useThree: vi.fn((selector?: (state: any) => any) => {
      // If selector provided, apply it to mock state
      if (selector) {
        return selector(mockState);
      }
      // Otherwise return full state
      return mockState;
    }),
  };
});

// Mock global intrinsic elements from three.js used by React Three Fiber
// These include: group, mesh, primitive, ambientLight, directionalLight, etc.
// @ts-ignore - Adding to global React namespace for test environment
globalThis.React = React;
const mockThreeElement = (type: string) => ({ children, ...props }: any) =>
  React.createElement('div', { ...props, 'data-three-type': type }, children);

// Register common three.js elements as React components
(global as any).group = mockThreeElement('group');
(global as any).mesh = mockThreeElement('mesh');
(global as any).primitive = mockThreeElement('primitive');
(global as any).ambientLight = mockThreeElement('ambientLight');
(global as any).directionalLight = mockThreeElement('directionalLight');

// ---------------------------------------------------------------------------
// @react-three/drei — prevent real asset fetching and WebGL calls in jsdom.
// useGLTF mock checks URL patterns to simulate 404 and parsing errors for tests.
// ---------------------------------------------------------------------------
vi.mock('@react-three/drei', () => {
  const mockComponent = () => null;
  const mockComponentWithChildren = ({ children }: { children?: React.ReactNode }) =>
    React.createElement('div', null, children);
  
  return {
    useGLTF: Object.assign(
      vi.fn((url: string) => {
        // Simulate GLB 404 error from CDN (ERR-INT-04)
        if (url.includes('does-not-exist.glb') || url.includes('invalid-path')) {
          throw new Error('404 - GLB file not found');
        }
        
        // Simulate corrupted GLB parsing error (ERR-INT-05)
        if (url.includes('corrupted')) {
          throw new Error('GLTFLoader: Invalid or unsupported glTF version');
        }
        
        // Default: return mock scene for successful loads
        // Mock scene must support .clone() → object with .traverse() for PartMesh tests
        // Mock scene must have isObject3D: true for ModelLoader validation
        return {
          scene: {
            isObject3D: true, // Required by ModelLoader validation (line 198)
            clone: vi.fn(() => ({
              traverse: vi.fn((callback: (child: any) => void) => {
                // Simulate traversing a mesh with material (needed for color/opacity tests)
                callback({
                  isMesh: true,
                  material: {
                    color: { set: vi.fn() },
                    emissive: { set: vi.fn() },
                    emissiveIntensity: 0,
                    opacity: 1.0,
                    transparent: false,
                    needsUpdate: false,
                  },
                });
              }),
            })),
          },
          nodes: {},
          materials: {},
        };
      }),
      { preload: vi.fn() }
    ),
    // Components that accept refs - return simple mock functions
    OrbitControls: mockComponent,
    PerspectiveCamera: mockComponent,
    // Components with children - wrap in div
    Stage: mockComponentWithChildren,
    GizmoHelper: mockComponentWithChildren,
    Html: mockComponentWithChildren,
    Detailed: ({ children, distances }: { children?: React.ReactNode, distances?: number[] }) =>
      React.createElement('div', { 'data-lod-distances': distances?.join(',') }, children),
    // Simple components without children or refs
    Grid: mockComponent,
    GizmoViewcube: mockComponent,
    Stats: mockComponent,
    // useBounds hook — returns chainable API (refresh/fit used by BoundsRefitter)
    useBounds: vi.fn(() => ({
      refresh: vi.fn().mockReturnThis(),
      fit: vi.fn().mockReturnThis(),
    })),
    // Bounds provider — pass-through wrapper for children
    Bounds: mockComponentWithChildren,
  };
});
