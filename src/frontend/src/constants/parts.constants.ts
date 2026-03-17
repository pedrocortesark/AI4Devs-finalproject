/**
 * T-0506-FRONT: Parts Filter Constants
 *
 * Centralized constants for parts filtering UI.
 * Note: filter options (Agrupació, Material) are derived dynamically from
 * the loaded parts data in FilterBar, not defined statically here.
 */

/**
 * Visual feedback constants for non-matching parts
 */
export const FILTER_VISUAL_FEEDBACK = {
  /** Opacity for matching parts (fully visible) */
  MATCH_OPACITY: 1.0,

  /** Opacity for non-matching parts (faded out) */
  NON_MATCH_OPACITY: 0.2,

  /** CSS transition duration for smooth fade (milliseconds) */
  TRANSITION_DURATION: 300,
} as const;

/**
 * URL param keys for filter persistence
 */
export const FILTER_URL_PARAMS = {
  MATERIAL: 'material',
  AGRUPACIO: 'agrupacio',
  WORKSHOP: 'workshop_id',
  SEPARATOR: ',', // For multi-select arrays: material=Montjuïc,Ulldecona
} as const;
