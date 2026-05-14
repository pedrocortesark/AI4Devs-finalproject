"""
Application constants for the Sagrada Familia Parts Manager.

This module centralizes all hardcoded values used across the backend
to improve maintainability and avoid magic strings.
"""

# ===== Storage Configuration =====
STORAGE_BUCKET_RAW_UPLOADS = "raw-uploads"
STORAGE_BUCKET_PROCESSED = "processed-geometry"
STORAGE_PATH_PREFIX_MODELS = "models"  # NEW (T-1502-INFRA): Hierarchical prefix for organized storage
STORAGE_PATH_SUBDIR_LOW_POLY = "low-poly"  # NEW (T-1502-INFRA): Subdirectory for low-poly GLB files

# ===== Event Types =====
EVENT_TYPE_UPLOAD_CONFIRMED = "upload.confirmed"
EVENT_TYPE_PROCESSING_STARTED = "processing.started"
EVENT_TYPE_PROCESSING_COMPLETED = "processing.completed"
EVENT_TYPE_PROCESSING_FAILED = "processing.failed"
EVENT_TYPE_VALIDATION_PASSED = "validation.passed"
EVENT_TYPE_VALIDATION_FAILED = "validation.failed"

# ===== Database Tables =====
TABLE_EVENTS = "events"
TABLE_FILES = "files"
TABLE_PARTS = "parts"
TABLE_BLOCKS = "blocks"

# ===== File Validation =====
ALLOWED_EXTENSION = ".3dm"
MAX_FILE_SIZE_MB = 500
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 500MB converted to bytes for Pydantic validation

# ===== Upload Configuration =====
STORAGE_UPLOAD_PATH_PREFIX = "uploads"
PRESIGNED_URL_EXPIRATION_SECONDS = 300  # 5 minutes

# ===== Celery Task Names =====
TASK_VALIDATE_FILE = "agent.tasks.validate_file"
TASK_REGISTER_3DM_BLOCKS = "agent.tasks.register_3dm_blocks"

# ===== Block Defaults =====
BLOCK_TIPOLOGIA_PENDING = "pending"
BLOCK_ISO_CODE_PREFIX = "PENDING"

# ===== Parts Listing Query Fields =====
PARTS_LIST_SELECT_FIELDS = "id, iso_code, status, tipologia, low_poly_url, high_poly_url, mid_poly_url, mtl_url, bbox, rhino_metadata"
QUERY_FIELD_IS_ARCHIVED = "is_archived"
QUERY_FIELD_CREATED_AT = "created_at"
QUERY_ORDER_DESC = True

# ===== T-1809-INFRA: Metrics Configuration =====
METRICS_WINDOW_HOURS = 24  # Time window for 24h metrics
PERCENTILES = [0.50, 0.95, 0.99]  # Processing time percentiles to calculate
CLASSIFICATION_METHODS = ["LLM_GPT4", "FALLBACK_REGEX"]  # Valid classification methods

# Event types for metrics aggregation
EVENT_TYPE_GRAPH_STARTED = "GRAPH_STARTED"
EVENT_TYPE_GRAPH_COMPLETED = "GRAPH_COMPLETED"
EVENT_TYPE_GRAPH_FAILED = "GRAPH_FAILED"
EVENT_TYPE_NODE_COMPLETED = "NODE_COMPLETED"
EVENT_TYPE_FALLBACK_ACTIVATED = "FALLBACK_ACTIVATED"

# ===== Element API Query Fields (T-1504-BACK + US-015 LOD) =====
ELEMENTS_LIST_SELECT_FIELDS = "id, iso_code, status, material_type, high_poly_url, mid_poly_url, low_poly_url, mtl_url, bbox, rhino_metadata"
ELEMENT_DETAIL_SELECT_FIELDS = ("id, iso_code, status, material_type, created_at, updated_at, "
                                 "high_poly_url, mid_poly_url, low_poly_url, bbox, validation_report, rhino_metadata")

# ===== Validation Error Messages =====
ERROR_MSG_INVALID_STATUS = "Invalid status value. Must be one of: {valid_values}"
ERROR_MSG_INVALID_UUID = "Invalid workshop_id format. Must be a valid UUID."
ERROR_MSG_FETCH_PARTS_FAILED = "Failed to fetch parts: {error}"
ERROR_MSG_ELEMENT_NOT_FOUND = "Element not found"
ERROR_MSG_INVALID_UUID_FORMAT = "Invalid UUID format"
ERROR_MSG_DATABASE_ERROR = "Database error: {error}"
ERROR_MSG_FETCH_ELEMENTS_FAILED = "Failed to fetch elements: {error}"

# ===== T-1504-BACK: Material Type Validation - Real Stone Dictionary (62 types) =====
# Stone material to RGB color mapping (62 types from Sagrada Família)
# Source: C# Dictionary from BIM Manager (2026-03-07)
# Usage: Frontend canvas rendering + material validation
# Note: Duplicated from agent.constants for backend-only imports (Railway separation)
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

# ===== US-020: ISO-19650 Validation Pattern =====
# Duplicated from agent.constants for backend-only imports (Railway separation)
# See src/agent/constants.ISO_19650_LAYER_NAME_PATTERN for canonical definition
ISO_19650_LAYER_NAME_PATTERN = r"^[A-Z]{2,3}-[A-Z0-9]{3,4}-[A-Z]{1,2}-\d{3}$"
