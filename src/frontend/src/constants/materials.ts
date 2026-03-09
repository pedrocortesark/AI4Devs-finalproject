/**
 * T-1505-FRONT: Material Colors Dictionary
 * 
 * Synchronized with backend src/agent/constants.py MATERIAL_COLORS
 * 62 real stone types from Sagrada Família with RGB tuples
 * 
 * Usage:
 * - Frontend canvas rendering: Apply material color to Three.js mesh
 * - Validation: TypeScript MaterialType = keyof typeof MATERIAL_COLORS
 * 
 * @see src/agent/constants.py - MATERIAL_COLORS (source of truth with 62 materials)
 */

/**
 * Complete material colors dictionary (62 materials)
 * RGB values in 0-255 range (convert to 0-1 for Three.js via getMaterialColor)
 */
export const MATERIAL_COLORS = {
  // Warm tones (ochres, creams, beiges)
  "Montjuïc": [230, 180, 100] as const,               // Warm ochre (DEFAULT)
  "Ulldecona": [240, 220, 180] as const,              // Light cream
  "Floresta": [225, 200, 130] as const,               // Golden sand
  "Beix Anglès": [210, 195, 170] as const,            // Beige
  "Beix mallorca": [215, 190, 150] as const,          // Golden beige
  "Crema marfil": [235, 225, 200] as const,           // Ivory cream
  "Itaunas": [225, 210, 160] as const,                // Yellow beige
  "Jodhpur beix": [220, 200, 170] as const,           // Sand beige
  "Pedra de vilafranca": [230, 210, 170] as const,    // Light yellow
  "Pedra de figueres": [230, 215, 185] as const,      // Light beige
  "Pedra de calafell": [225, 215, 190] as const,      // Light cream
  "Udelfangen": [230, 220, 200] as const,             // Fine light beige
  "Stanton Moor": [220, 190, 170] as const,           // Light reddish beige

  // Browns and reds
  "Granit moreno ingemarga": [145, 95, 60] as const,  // Brown
  "Granit boveda moreno": [110, 80, 60] as const,     // Dark brown
  "Granit moreno torible": [130, 90, 70] as const,    // Dark reddish brown
  "Granit Torrat": [150, 110, 80] as const,           // Toasted brown
  "Roig st. jaume": [160, 70, 70] as const,           // Dark red
  "Rosso levanto": [170, 100, 90] as const,           // Veined red
  "Calcària griotte": [150, 70, 70] as const,         // Red black
  "Sorrenca de st. vicenç (rocafort)": [200, 150, 130] as const,  // Sandy red
  "Zarcilla": [170, 130, 110] as const,               // Reddish brown
  "Pulpis": [180, 160, 140] as const,                 // Light brown
  "Pedra de mistretta": [190, 160, 120] as const,     // Golden brown

  // Grays (light to dark)
  "Pedra del garraf": [220, 220, 220] as const,       // White gray
  "Blanc cardenal": [230, 230, 235] as const,         // Light grayish white
  "Calcària de st. vicens": [210, 210, 215] as const, // Grayish white
  "Granit gris quintana": [170, 170, 170] as const,   // Light gray
  "Granit de vilachà": [160, 160, 170] as const,      // Granite gray
  "Montserrat": [170, 160, 170] as const,             // Pinkish gray
  "Granit zamora": [180, 165, 175] as const,          // Pink gray
  "Pedra de les masies de roda": [205, 190, 195] as const,  // Light pinkish gray
  "Postaer Alte Poste": [210, 205, 190] as const,     // Cream gray
  "Leïstadter": [200, 200, 170] as const,             // Yellowish gray
  "Granit gudiña": [90, 90, 95] as const,             // Dark gray
  "Granit merufe": [100, 100, 110] as const,          // Veined dark gray
  "Granit del tarn": [180, 180, 190] as const,        // Silvery gray

  // Greenish grays
  "Cantàbria": [120, 150, 140] as const,              // Greenish gray
  "Escòcia": [140, 160, 150] as const,                // Greenish gray
  "Llisós": [180, 190, 180] as const,                 // Light greenish gray
  "Granit orrius o ull de serp": [130, 150, 130] as const,  // Green gray

  // Bluish tones
  "Blavozy": [160, 170, 190] as const,                // Bluish gray
  "Pedra del figueró": [140, 150, 175] as const,      // Blue gray
  "Granit blau bahia": [60, 80, 130] as const,        // Dark blue
  "Granit de fraguas": [100, 110, 130] as const,      // Dark bluish gray
  "Ocean Black": [50, 60, 70] as const,               // Bluish black

  // Blacks and dark tones
  "Basalt de castellfollit": [70, 70, 75] as const,   // Grayish black
  "Basalt italià": [50, 50, 55] as const,             // Intense black
  "Granit negre zimbawe": [40, 40, 45] as const,      // Graphite black
  "Volcanica": [80, 80, 90] as const,                 // Textured dark gray

  // Whites and very light tones
  "Blanc macael": [250, 250, 250] as const,           // Pure white
  "Granit blanco cristal": [240, 240, 240] as const,  // Crystal white
  "Alabastre": [245, 240, 235] as const,              // Translucent white
  "Pedra de colmenar": [235, 230, 215] as const,      // Cream white
  "Marbre de tassos": [240, 235, 230] as const,       // Veined white
  "Marbre de carrara": [245, 245, 245] as const,      // Carrara white
  "Himàlaia": [240, 235, 225] as const,               // Veined crystal white

  // Pinks
  "Jodhpur Pink": [230, 200, 200] as const,           // Light pink

  // Special tones
  "Pòrfir": [150, 100, 150] as const,                 // Purple
  "Ònix": [180, 220, 200] as const,                   // Translucent green

  // Travertines
  "Travertí romà": [220, 200, 170] as const,          // Travertine beige
  "Travertí de terol": [210, 180, 150] as const,      // Reddish beige
  "Travertí de granada": [200, 170, 140] as const,    // Dark beige
} as const;

/**
 * Default material when not specified
 */
export const DEFAULT_MATERIAL = "Montjuïc" as const;

/**
 * Helper: Get RGB color array for a material (normalized 0-1 for Three.js)
 * 
 * @param material - Material type from MATERIAL_COLORS
 * @returns RGB color normalized to [0, 1] range for Three.js
 * 
 * @example
 * const color = getMaterialColor("Montjuïc"); // [0.902, 0.706, 0.392]
 */
export function getMaterialColor(material: keyof typeof MATERIAL_COLORS): [number, number, number] {
  const [r, g, b] = MATERIAL_COLORS[material];
  return [r / 255, g / 255, b / 255];
}

/**
 * Helper: Get RGB color as hex string for CSS
 * 
 * @param material - Material type from MATERIAL_COLORS
 * @returns Hex color string (e.g., "#e6b464")
 * 
 * @example
 * const hex = getMaterialColorHex("Montjuïc"); // "#e6b464"
 */
export function getMaterialColorHex(material: keyof typeof MATERIAL_COLORS): string {
  const [r, g, b] = MATERIAL_COLORS[material];
  const toHex = (val: number) => val.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}
