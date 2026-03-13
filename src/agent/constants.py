"""
Agent Worker Constants

Centralized configuration values for Celery worker and task execution.
Following Clean Architecture pattern (separation from config.py which handles env vars).
"""

# Celery Worker Configuration
CELERY_APP_NAME = "sf_pm_agent"

# Task Execution Timeouts
# Large .3dm files (up to 500MB) can take several minutes to parse with rhino3dm
TASK_TIME_LIMIT_SECONDS = 600  # 10 minutes hard kill
TASK_SOFT_TIME_LIMIT_SECONDS = 540  # 9 minutes warning (allows cleanup)

# Worker Behavior
WORKER_PREFETCH_MULTIPLIER = 1  # One task at a time (isolate large file processing)

# Result Storage
RESULT_EXPIRES_SECONDS = 3600  # 1 hour (results cleaned up automatically)

# Task Retry Policy
TASK_MAX_RETRIES = 3
TASK_RETRY_DELAY_SECONDS = 60  # 1 minute between retries

# Task Names (for type safety and refactoring)
TASK_HEALTH_CHECK = "agent.tasks.health_check"
TASK_VALIDATE_FILE = "agent.tasks.validate_file"
TASK_REGISTER_3DM_BLOCKS = "agent.tasks.register_3dm_blocks"

# Validation Patterns
# ISO-19650 nomenclature:  [PREFIX]-[ZONE/CODE]-[TYPE]-[ID]
# Examples: SF-NAV-CO-001, SFC-NAV1-A-999, AB-CD12-XY-123
# Pattern breakdown:
#   - [A-Z]{2,3}: 2-3 uppercase letters (project prefix)
#   - [A-Z0-9]{3,4}: 3-4 alphanumeric uppercase (zone/code)
#   - [A-Z]{1,2}: 1-2 uppercase letters (element type)
#   - \d{3}: exactly 3 digits (sequential ID)
ISO_19650_LAYER_NAME_PATTERN = r"^[A-Z]{2,3}-[A-Z0-9]{3,4}-[A-Z]{1,2}-\d{3}$"
ISO_19650_PATTERN_DESCRIPTION = "[PREFIX]-[ZONE]-[TYPE]-[ID] (e.g., SF-NAV-CO-001)"

# Geometry Validation
GEOMETRY_CATEGORY_NAME = "geometry"
MIN_VALID_VOLUME = 1e-6  # Minimum volume in cubic units (avoid near-zero volumes)
MAX_3DM_FILE_SIZE_MB = 500  # Maximum file size for .3dm files (prevent zip bomb DoS)
MAX_FILE_SIZE_BYTES = MAX_3DM_FILE_SIZE_MB * 1024 * 1024  # 500MB converted to bytes for Pydantic validation

# Geometry Error Messages Templates
GEOMETRY_ERROR_INVALID = "Geometry is marked as invalid by Rhino (obj.Geometry.IsValid = False)"
GEOMETRY_ERROR_NULL = "Geometry is null or missing"
GEOMETRY_ERROR_DEGENERATE_BBOX = "Bounding box is degenerate or invalid"
GEOMETRY_ERROR_ZERO_VOLUME = "Solid geometry has zero or near-zero volume (< {min_volume} cubic units)"

# ===== T-0502-AGENT: Geometry Processing =====

# Task Names
TASK_GENERATE_LOW_POLY_GLB = "agent.generate_low_poly_glb"

# LOD System - Multi-Level Decimation Targets (US-015)
# 3-level LOD + BBox proxy for optimal performance/quality balance
LOD_DECIMATION_TARGETS = {
    'high': None,    # High-poly: no decimation (~5000-8000 faces, <5m viewing distance)
    'mid': 2000,     # Mid-poly: moderate decimation (~1500-2000 faces, 5-20m viewing distance)
    'low': 500,      # Low-poly: aggressive decimation (~400-600 faces, 20-50m viewing distance)
}

# Legacy constant (deprecated - use LOD_DECIMATION_TARGETS['low'])
DECIMATION_TARGET_FACES = LOD_DECIMATION_TARGETS['low']  # Backward compatibility

MAX_ORIGINAL_FACES_WARNING = 100_000  # Log warning if geometry exceeds 100K faces (timeout risk)

# File Size Limits (updated for LOD system)
MAX_GLB_SIZE_KB = {
    'high': 800,   # High-poly target: ~600-800KB with Draco
    'mid': 400,    # Mid-poly target: ~300-400KB with Draco
    'low': 200,    # Low-poly target: ~150-200KB with Draco
}
MAX_3DM_DOWNLOAD_SIZE_MB = 500  # Reject .3dm files >500MB (timeout risk)

# S3/Storage Configuration
PROCESSED_GEOMETRY_BUCKET = "processed-geometry"
LOD_PREFIXES = {
    'high': 'high-poly/',
    'mid': 'mid-poly/',
    'low': 'low-poly/',
}
# Legacy (deprecated - use LOD_PREFIXES['low'])
LOW_POLY_PREFIX = LOD_PREFIXES['low']

RAW_UPLOADS_BUCKET = "raw-uploads"

# Temp File Paths
TEMP_DIR = "/tmp"  # Docker container temp directory

# ===== Draco Compression (via gltf-pipeline CLI — mirrors POC export_gltf_draco.py) =====
DRACO_COMPRESSION_LEVEL = 7         # 0-10 scale (POC used 10; 7 = good quality/size balance)
DRACO_QUANTIZE_POSITION_BITS = 14   # ~0.1mm precision at Sagrada Família scale (POC value)
DRACO_QUANTIZE_NORMAL_BITS = 10
DRACO_QUANTIZE_TEXCOORD_BITS = 12

# Bbox Centering Validation
BBOX_CENTROID_TOLERANCE_MM = 1.0    # Centroid must be within 1mm of origin after centering

# Error Messages
ERROR_MSG_NO_MESHES_FOUND = "No meshes found in {iso_code}"
ERROR_MSG_BLOCK_NOT_FOUND = "Block {block_id} not found in database"
ERROR_MSG_FAILED_PARSE_3DM = "Failed to parse .3dm file for {iso_code}"
ERROR_MSG_S3_DOWNLOAD_FAILED = "S3 download failed after {retries} retries"

# ===== T-1504-AGENT: Material Type Extraction - Real Stone Dictionary (62 types) =====

# Stone material to RGB color mapping (62 types from Sagrada Família)
# Source: C# Dictionary from BIM Manager (2026-03-07)
# Usage: Frontend canvas rendering + material validation
MATERIAL_COLORS = {
    # Warm tones (ochres, creams, beiges)
    "Montjuïc": (230, 180, 100),               # Warm ochre (DEFAULT)
    "Ulldecona": (240, 220, 180),              # Light cream
    "Floresta": (225, 200, 130),               # Golden sand
    "Beix Anglès": (210, 195, 170),            # Beige
    "Beix mallorca": (215, 190, 150),          # Golden beige
    "Crema marfil": (235, 225, 200),           # Ivory cream
    "Itaunas": (225, 210, 160),                # Yellow beige
    "Jodhpur beix": (220, 200, 170),           # Sand beige
    "Pedra de vilafranca": (230, 210, 170),    # Light yellow
    "Pedra de figueres": (230, 215, 185),      # Light beige
    "Pedra de calafell": (225, 215, 190),      # Light cream
    "Udelfangen": (230, 220, 200),             # Fine light beige
    "Stanton Moor": (220, 190, 170),           # Light reddish beige
    
    # Browns and reds
    "Granit moreno ingemarga": (145, 95, 60),  # Brown
    "Granit boveda moreno": (110, 80, 60),     # Dark brown
    "Granit moreno torible": (130, 90, 70),    # Dark reddish brown
    "Granit Torrat": (150, 110, 80),           # Toasted brown
    "Roig st. jaume": (160, 70, 70),           # Dark red
    "Rosso levanto": (170, 100, 90),           # Veined red
    "Calcària griotte": (150, 70, 70),         # Red black
    "Sorrenca de st. vicenç (rocafort)": (200, 150, 130),  # Sandy red
    "Zarcilla": (170, 130, 110),               # Reddish brown
    "Pulpis": (180, 160, 140),                 # Light brown
    "Pedra de mistretta": (190, 160, 120),     # Golden brown
    
    # Grays (light to dark)
    "Pedra del garraf": (220, 220, 220),       # White gray
    "Blanc cardenal": (230, 230, 235),         # Light grayish white
    "Calcària de st. vicens": (210, 210, 215), # Grayish white
    "Granit gris quintana": (170, 170, 170),   # Light gray
    "Granit de vilachà": (160, 160, 170),      # Granite gray
    "Montserrat": (170, 160, 170),             # Pinkish gray
    "Granit zamora": (180, 165, 175),          # Pink gray
    "Pedra de les masies de roda": (205, 190, 195),  # Light pinkish gray
    "Postaer Alte Poste": (210, 205, 190),     # Cream gray
    "Leïstadter": (200, 200, 170),             # Yellowish gray
    "Granit gudiña": (90, 90, 95),             # Dark gray
    "Granit merufe": (100, 100, 110),          # Veined dark gray
    "Granit del tarn": (180, 180, 190),        # Silvery gray
    
    # Greenish grays
    "Cantàbria": (120, 150, 140),              # Greenish gray
    "Escòcia": (140, 160, 150),                # Greenish gray
    "Llisós": (180, 190, 180),                 # Light greenish gray
    "Granit orrius o ull de serp": (130, 150, 130),  # Green gray
    
    # Bluish tones
    "Blavozy": (160, 170, 190),                # Bluish gray
    "Pedra del figueró": (140, 150, 175),      # Blue gray
    "Granit blau bahia": (60, 80, 130),        # Dark blue
    "Granit de fraguas": (100, 110, 130),      # Dark bluish gray
    "Ocean Black": (50, 60, 70),               # Bluish black
    
    # Blacks and dark tones
    "Basalt de castellfollit": (70, 70, 75),   # Grayish black
    "Basalt italià": (50, 50, 55),             # Intense black
    "Granit negre zimbawe": (40, 40, 45),      # Graphite black
    "Volcanica": (80, 80, 90),                 # Textured dark gray
    
    # Whites and very light tones
    "Blanc macael": (250, 250, 250),           # Pure white
    "Granit blanco cristal": (240, 240, 240),  # Crystal white
    "Alabastre": (245, 240, 235),              # Translucent white
    "Pedra de colmenar": (235, 230, 215),      # Cream white
    "Marbre de tassos": (240, 235, 230),       # Veined white
    "Marbre de carrara": (245, 245, 245),      # Carrara white
    "Himàlaia": (240, 235, 225),               # Veined crystal white
    
    # Pinks
    "Jodhpur Pink": (230, 200, 200),           # Light pink
    
    # Special tones
    "Pòrfir": (150, 100, 150),                 # Purple
    "Ònix": (180, 220, 200),                   # Translucent green
    
    # Travertines
    "Travertí romà": (220, 200, 170),          # Travertine beige
    "Travertí de terol": (210, 180, 150),      # Reddish beige
    "Travertí de granada": (200, 170, 140),    # Dark beige
}

# Derived constants
VALID_MATERIALS = list(MATERIAL_COLORS.keys())  # 62 materials
DEFAULT_MATERIAL = "Montjuïc"  # Most common material in Sagrada Família
MATERIAL_USERSTRING_KEY = "Material"  # Rhino UserString key for material metadata
