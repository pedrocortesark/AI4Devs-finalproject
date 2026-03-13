/**
 * Constants for Dashboard 3D components
 * T-0504-FRONT: Dashboard 3D Canvas Layout
 *
 * Following constants extraction pattern from US-001 (FileUploader)
 *
 * UNIT SYSTEM: all Three.js distances are in metres (1 scene unit = 1 m).
 * Rhino .3dm files use metres for Sagrada Família coordinates; GLBs are exported
 * in Rhino coordinates, so the canvas matches the source data directly.
 */

import type { DockPosition } from './Dashboard3D.types';

/**
 * Camera configuration defaults — all distances in metres.
 * 
 * US-015 Update: Elements are GLPER pieces (30-90cm sized) centered at:
 * - X: -8.80m
 * - Y: -53.00m (note: negative Y, not positive!)
 * - Z: 74.07m
 * 
 * Camera positioned 5m away (diagonal offset) for comfortable viewing of small objects.
 */
export const CAMERA_CONFIG = {
  FOV: 55,
  // Position camera 5m away from element center at [-8.80, -53.00, 74.07]
  // Using diagonal offset for good viewing angle: [+2, +3, +4] → Camera at [-6.80, -50.00, 78.07]
  POSITION: [-6.80, -50.00, 78.07] as [number, number, number],
  // OrbitControls target: point camera at element center
  TARGET: [-8.80, -53.00, 74.07] as [number, number, number],
  NEAR: 0.001,    // 1 mm minimum render distance
  FAR: 10000,     // 10 km maximum render distance
} as const;

/**
 * Grid configuration for Three.js scene — all distances in metres.
 * US-015: Reduced to 0.5m cells for small GLPER pieces (30-90cm size)
 */
export const GRID_CONFIG = {
  SIZE: [200, 200] as [number, number],       // 200 m total grid (but fades before reaching edge)
  CELL_SIZE: 0.5,                             // 0.5 m (50 cm) between minor grid lines
  SECTION_SIZE: 5,                            // 5 m between major grid lines  
  CELL_THICKNESS: 0.5,
  SECTION_THICKNESS: 1,
  CELL_COLOR: '#6e6e6e',
  SECTION_COLOR: '#9d4b4b',
  FADE_DISTANCE: 100,                         // 100 m fade-out distance (reduced)
  FADE_STRENGTH: 1,
} as const;

/**
 * Responsive breakpoints (px)
 */
export const BREAKPOINTS = {
  MOBILE: 768,
  TABLET: 1024,
  DESKTOP: 1440,
} as const;

/**
 * Dock position constants
 */
export const DOCK_POSITIONS: Record<string, DockPosition> = {
  LEFT: 'left',
  RIGHT: 'right',
  FLOATING: 'floating',
} as const;

/**
 * Sidebar dimensions and behavior
 */
export const SIDEBAR_CONFIG = {
  WIDTH: 300, // px
  DRAG_HANDLE_HEIGHT: 40, // px
  SNAP_THRESHOLD: 50, // px from edge to trigger snap
  MIN_FLOATING_WIDTH: 280, // px
  MAX_FLOATING_WIDTH: 400, // px
  TRANSITION_DURATION: 300, // ms
} as const;

/**
 * localStorage keys
 */
export const STORAGE_KEYS = {
  SIDEBAR_DOCK: 'dashboard-sidebar-dock',
  SIDEBAR_POSITION: 'dashboard-sidebar-position',
} as const;

/**
 * Default messages
 */
export const MESSAGES = {
  EMPTY_STATE: 'No hay piezas cargadas',
  EMPTY_STATE_SUBTITLE: 'Las piezas validadas aparecerán aquí automáticamente',
  LOADING: 'Cargando piezas...',
  FILTERS_TITLE: 'Filtros',
  FILTERS_COMING_SOON: 'Próximamente...',
} as const;

/**
 * ARIA labels for accessibility
 */
export const ARIA_LABELS = {
  CANVAS: 'Vista 3D del dashboard de piezas',
  SIDEBAR: 'Panel de filtros lateral',
  DRAG_HANDLE: 'Arrastrar panel de filtros',
  DOCK_LEFT: 'Anclar panel a la izquierda',
  DOCK_RIGHT: 'Anclar panel a la derecha',
  FLOAT: 'Dejar panel flotante',
  TOGGLE_SIDEBAR: 'Mostrar/ocultar filtros',
} as const;

/**
 * Lighting configuration for Three.js scene — positions in metres.
 */
export const LIGHTING_CONFIG = {
  AMBIENT_INTENSITY: 0.4,
  DIRECTIONAL_INTENSITY: 1,
  DIRECTIONAL_POSITION: [50, 100, 50] as [number, number, number], // 50/100/50 m
  SHADOW_MAP_SIZE: 2048,
} as const;

/**
 * OrbitControls configuration — distances in metres.
 */
export const CONTROLS_CONFIG = {
  ENABLE_DAMPING: true,
  DAMPING_FACTOR: 0.05,
  MIN_DISTANCE: 0.001,  // 1 mm minimum zoom
  MAX_DISTANCE: 1000,   // 1 km maximum zoom-out (parts at ~90m from origin)
  MAX_POLAR_ANGLE: Math.PI, // Allow full rotation including below ground
} as const;

/**
 * Camera Fitting Configuration (CAD-style controls)
 */
export const CAMERA_FIT_CONFIG = {
  /** Offset multiplier for bounding sphere (1.2 = 20% margin around objects) */
  FIT_OFFSET: 1.2,
  /** Default animation duration for camera transitions (seconds) */
  ANIMATION_DURATION: 0.8,
  /** GSAP easing function for smooth, professional movement */
  ANIMATION_EASING: 'power2.inOut',
  /** Key code for "Focus Selected" action */
  FOCUS_KEY: 'f',
} as const;
