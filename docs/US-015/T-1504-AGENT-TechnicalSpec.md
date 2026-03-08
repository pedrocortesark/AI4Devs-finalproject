# T-1504-AGENT: Material Type Extraction - Real Stone Dictionary (62 types)

**Created:** 2026-03-07 18:30  
**Status:** 🔜 READY (ENRICH Phase)  
**TDD Phase:** ENRICH (Technical Specification)  
**Story Points:** 5

---

## 🎯 Objetivo

Corregir la implementación de T-1503-AGENT que usaba una especificación incorrecta. El material NO es un enum simple ["Stone", "Ceramic"], sino uno de **62 tipos de piedra reales** usados en la Sagrada Família, cada uno con su color RGB asociado para el canvas 3D.

---

## ⚠️ Contexto: ¿Por Qué Este Ticket?

### Problema Descubierto en T-1503-AGENT

**Especificación Original (INCORRECTA):**
```python
# T-1503 pensaba que material era:
VALID_MATERIALS = ["Stone", "Ceramic"]  # ❌ INCORRECTO
```

**Realidad Descubierta:**
- Los archivos .3dm reales contienen UserStrings como `"Material": "Montjuïc"`, `"Material": "Ulldecona"`, etc.
- Son 62 tipos de piedra específicos, no categorías genéricas
- Cada material tiene un color RGB asociado para renderizado
- El UserString "Material" **siempre está en metadatos de objeto**, no en document/layer

### Impacto de T-1503 (Implementación Incorrecta)

| Aspecto | T-1503 | T-1504 (Correcto) |
|---------|--------|-------------------|
| Materiales válidos | 2 (Stone, Ceramic) | 62 (tipos reales) |
| Fuente de extracción | Document → Layer → Object → Default | **Object UserString solo** |
| Default fallback | "Stone" | "Montjuïc" (material más común) |
| Color mapping | ❌ No existe | ✅ RGB por material |
| Tests | Stone/Ceramic mockups | Montjuïc/Ulldecona reales |

---

## 📋 Acceptance Criteria

### AC-01: Material Dictionary con 62 Tipos Reales
**Given** el sistema tiene configurado el diccionario de materiales  
**When** un desarrollador inspecciona `src/agent/constants.py`  
**Then** debe existir `MATERIAL_COLORS` con exactamente 62 entradas  
**And** cada entrada tiene formato `{"Material": (R, G, B)}`  
**And** los valores RGB están en rango [0, 255]

**Ejemplo esperado:**
```python
MATERIAL_COLORS = {
    "Montjuïc": (230, 180, 100),
    "Ulldecona": (240, 220, 180),
    "Floresta": (225, 200, 130),
    # ... 59 materiales más
}
```

### AC-02: Extracción Solo de Object UserStrings
**Given** un archivo .3dm con UserString `"Material": "Montjuïc"` en un objeto  
**When** el agente procesa el archivo  
**Then** debe buscar SOLO en `object.Attributes.GetUserStrings()`  
**And** NO debe buscar en `rhino_file.Strings` (document level)  
**And** NO debe buscar en `layer.GetUserStrings()` (layer level)  
**And** debe devolver `"Montjuïc"`

### AC-03: Normalización de Input
**Given** un UserString con valor `"  montjuïc  "` (espacios + minúsculas)  
**When** el agente valida el material  
**Then** debe normalizar a `"Montjuïc"` (title case, sin espacios)  
**And** debe coincidir con la clave del diccionario  
**And** debe devolver `"Montjuïc"`

### AC-04: Validación Contra 62 Materiales
**Given** un UserString con valor `"Granite"` (no está en diccionario)  
**When** el agente valida el material  
**Then** debe loggear warning "Material inválido"  
**And** debe defaultear a `"Montjuïc"`  
**And** debe guardar `"Montjuïc"` en la base de datos

### AC-05: Default Fallback a Montjuïc
**Given** un archivo .3dm sin UserString "Material" en ningún objeto  
**When** el agente intenta extraer el material  
**Then** debe devolver `"Montjuïc"` por defecto  
**And** debe loggear info "Material no encontrado, usando default"

### AC-06: Color Mapping Disponible
**Given** el sistema tiene un material válido `"Ulldecona"`  
**When** se consulta `MATERIAL_COLORS["Ulldecona"]`  
**Then** debe devolver tupla RGB `(240, 220, 180)`  
**And** el frontend puede usar estos valores para colorear el canvas

### AC-07: Database Migration Ejecutada
**Given** la base de datos tiene la columna `material_type`  
**When** se inspecciona la constraint  
**Then** NO debe existir `CHECK (material_type IN ('Stone', 'Ceramic'))`  
**And** debe permitir TEXT libre  
**And** los 6 blocks existentes deben actualizarse a "Montjuïc" si tenían "Stone"

### AC-08: Tests con Materiales Reales
**Given** la suite de tests de T-1504  
**When** se ejecutan los tests  
**Then** deben usar materiales reales: "Montjuïc", "Ulldecona", "Floresta", etc.  
**And** NO deben usar "Stone" ni "Ceramic"  
**And** TODOS los tests de T-1503 deben reescribirse

### AC-09: Backward Compatibility en Database
**Given** la base de datos tiene blocks con `material_type = "Stone"` o `"Ceramic"` (de T-1503)  
**When** se ejecuta la migración T-1504  
**Then** `"Stone"` → `"Montjuïc"` (material por defecto)  
**And** `"Ceramic"` → `"Montjuïc"` (no hay equivalente cerámico en diccionario)  
**And** se loggea el número de rows actualizadas

### AC-10: Anti-regression Baseline
**Given** los 119 tests existentes del backend  
**When** se implementa T-1504  
**Then** TODOS los 119 tests deben seguir pasando  
**And** NO debe haber regresiones en tests no relacionados

---

## 🏗 Arquitectura

### Componentes Afectados

```
src/agent/
├── constants.py                    # ✅ MODIFICAR: Reemplazar VALID_MATERIALS
│   ├── MATERIAL_COLORS (nuevo)     # Dict con 62 materiales + RGB
│   ├── VALID_MATERIALS (update)    # list(MATERIAL_COLORS.keys())
│   └── DEFAULT_MATERIAL (update)   # "Montjuïc" (antes "Stone")
│
├── tasks/geometry_processing.py    # ✅ MODIFICAR: Lógica de extracción
│   ├── _extract_material_type()    # Simplificar: solo buscar en objects
│   └── _validate_and_normalize     # Actualizar validación vs 62 materiales
│
└── tests/agent/unit/
    └── test_material_extraction.py # ✅ REESCRIBIR: 12 tests con materiales reales

supabase/migrations/
└── 20260307000003_material_real_types.sql  # ✅ CREAR: Migración DB

docs/US-015/
├── T-1504-AGENT-TechnicalSpec.md   # ✅ ESTE ARCHIVO
└── MATERIAL_COLORS_SOURCE.md       # ✅ CREAR: Referencia del diccionario C#
```

---

## 📊 Data Model

### Material Colors Dictionary (62 entries)

```python
# src/agent/constants.py

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
MATERIAL_USERSTRING_KEY = "Material"  # Key in Rhino UserStrings
```

### Helper Functions

```python
# src/agent/tasks/geometry_processing.py

def get_material_color(material: str) -> tuple[int, int, int]:
    """Get RGB color for a given material.
    
    Args:
        material: Material name (e.g., "Montjuïc")
    
    Returns:
        RGB tuple (R, G, B) with values [0, 255]
    
    Example:
        >>> get_material_color("Ulldecona")
        (240, 220, 180)
    """
    return MATERIAL_COLORS.get(material, MATERIAL_COLORS[DEFAULT_MATERIAL])
```

---

## 🧪 Test Cases

### Test Plan Overview

| Category | Test Count | Description |
|----------|-----------|-------------|
| Happy Path | 5 | Extract real materials from objects |
| Edge Cases | 4 | Normalization, whitespace, case sensitivity |
| Error Handling | 3 | Invalid materials, empty strings, missing UserStrings |
| **TOTAL** | **12** | Same structure as T-1503, different materials |

### Happy Path Tests (5)

#### HP-01: Extract Montjuïc from Object UserString
```python
def test_hp_01_extract_montjuic_from_object_level():
    """Extract 'Montjuïc' from object-level UserString."""
    # ARRANGE
    rhino_file = create_mock_rhino_file_with_object_material("Montjuïc")
    
    # ACT
    result = _extract_material_type(rhino_file, "block-123", "TEST.CODE.001")
    
    # ASSERT
    assert result == "Montjuïc"
```

#### HP-02: Extract Ulldecona from Object UserString
```python
def test_hp_02_extract_ulldecona_from_object_level():
    """Extract 'Ulldecona' from object-level UserString."""
    # Similar structure, different material
```

#### HP-03: Extract Floresta from Object UserString
```python
def test_hp_03_extract_floresta_from_object_level():
    """Extract 'Floresta' from object-level UserString."""
```

#### HP-04: Multiple Objects Uses First Match
```python
def test_hp_04_multiple_objects_uses_first_found():
    """When multiple objects have Material UserString, use first match."""
    # ARRANGE
    rhino_file = Mock()
    rhino_file.Objects = [
        create_mock_object_with_material("Ulldecona"),  # First
        create_mock_object_with_material("Floresta"),   # Second (ignored)
    ]
    
    # ACT
    result = _extract_material_type(rhino_file, "block-123", "TEST")
    
    # ASSERT
    assert result == "Ulldecona"  # Uses first match
```

#### HP-05: Default to Montjuïc When Not Found
```python
def test_hp_05_default_to_montjuic_when_not_found():
    """Default to 'Montjuïc' when no Material UserString found."""
    # ARRANGE
    rhino_file = create_mock_rhino_file_empty()
    
    # ACT
    result = _extract_material_type(rhino_file, "block-123", "TEST")
    
    # ASSERT
    assert result == "Montjuïc"
```

### Edge Cases Tests (4)

#### EC-01: Normalize Lowercase to Title Case
```python
def test_ec_01_normalize_lowercase_to_title_case():
    """Normalize 'ulldecona' → 'Ulldecona' (title case)."""
    # Input: "ulldecona" → Expected: "Ulldecona"
```

#### EC-02: Trim Whitespace
```python
def test_ec_02_trim_whitespace():
    """Trim whitespace ' Montjuïc ' → 'Montjuïc'."""
```

#### EC-03: Normalize Uppercase
```python
def test_ec_03_normalize_uppercase_to_title_case():
    """Normalize 'FLORESTA' → 'Floresta'."""
```

#### EC-04: Case Insensitive Match with Accents
```python
def test_ec_04_case_insensitive_match_with_special_chars():
    """Normalize 'montjuic' (sin tilde) → 'Montjuïc' (con tilde)."""
    # ⚠️ NOTA: Este test puede fallar si no manejamos acentos
    # Solución: Normalizar input con unicodedata.normalize()
```

### Error Handling Tests (3)

#### ERR-01: Invalid Material Defaults to Montjuïc
```python
def test_err_01_invalid_material_granite_defaults_to_montjuic():
    """Invalid material 'Granite' → Default 'Montjuïc' + warning."""
    # Input: "Granite" (no está en diccionario)
    # Expected: "Montjuïc" + logger.warning()
```

#### ERR-02: Empty String Defaults to Montjuïc
```python
def test_err_02_empty_string_defaults_to_montjuic():
    """Empty string '' → Default 'Montjuïc' + warning."""
```

#### ERR-03: Invalid Material Concrete Defaults
```python
def test_err_03_invalid_material_concrete_defaults_to_montjuic():
    """Invalid material 'Concrete' → Default 'Montjuïc' + warning."""
```

---

## 🔄 Migration Strategy

### Database Migration: Remove Stone/Ceramic Constraint

**File:** `supabase/migrations/20260307000003_material_real_types.sql`

```sql
-- Migration: T-1504-AGENT - Allow real material types (62 types)
-- Author: AI Assistant
-- Date: 2026-03-07
-- Context: Remove CHECK constraint Stone/Ceramic from T-1503, allow TEXT

BEGIN;

-- Step 1: Drop CHECK constraint from T-1503
ALTER TABLE blocks 
  DROP CONSTRAINT IF EXISTS blocks_material_type_check;

-- Step 2: Update existing "Stone" → "Montjuïc" (default material)
--         Update existing "Ceramic" → "Montjuïc" (no ceramic equivalent in dict)
UPDATE blocks 
  SET material_type = 'Montjuïc'
  WHERE material_type IN ('Stone', 'Ceramic');

-- Step 3: Add comment documenting valid materials
COMMENT ON COLUMN blocks.material_type IS 
  'Material type: One of 62 real stone types (Montjuïc, Ulldecona, Floresta, etc.). See src/agent/constants.py MATERIAL_COLORS dictionary. Default: Montjuïc';

-- Step 4: Keep index for filtering
-- (Index already exists from T-1501: idx_blocks_material_type)

COMMIT;
```

### Rollback Plan

```sql
-- Rollback to T-1503 state (NOT RECOMMENDED, data loss)
BEGIN;

-- Revert all to "Stone"
UPDATE blocks SET material_type = 'Stone';

-- Re-add CHECK constraint
ALTER TABLE blocks 
  ADD CONSTRAINT blocks_material_type_check 
  CHECK (material_type IN ('Stone', 'Ceramic'));

COMMIT;
```

---

## 📝 Implementation Checklist

### Phase 1: ENRICH (Current)
- [x] Create technical specification document (this file)
- [x] Define 62 materials dictionary from C# source
- [x] Define test cases (12 tests)
- [x] Define database migration
- [ ] Update backlog with T-1504 entry
- [ ] Register in prompts.md (Entry #211)

### Phase 2: RED (Next)
- [ ] Create `test_material_extraction_v2.py` with 12 failing tests
- [ ] Update `MATERIAL_COLORS` in `constants.py` (62 entries)
- [ ] Run tests → Verify 12 FAILED (ImportError or assertion failures)
- [ ] Commit with message: `test(T-1504): RED - 12 tests with real materials`

### Phase 3: GREEN
- [ ] Update `_extract_material_type()` to search objects only
- [ ] Update `_validate_and_normalize_material()` for 62 materials
- [ ] Run tests → Verify 12 PASSED
- [ ] Run baseline → Verify 119 PASSED (no regression)
- [ ] Commit: `feat(T-1504): GREEN - Extract 62 real stone types`

### Phase 4: REFACTOR
- [ ] Extract helper `get_material_color(material) -> tuple`
- [ ] Add comprehensive docstrings with examples
- [ ] Remove T-1503 test file (obsolete)
- [ ] Apply database migration
- [ ] Update documentation (5 files)
- [ ] Commit: `refactor(T-1504): Clean code + docs`

### Phase 5: AUDIT
- [ ] Run full test suite (12 + 119 = 131 tests)
- [ ] Verify documentation updated
- [ ] Generate audit report
- [ ] Mark T-1504 as DONE in backlog
- [ ] Commit: `docs(T-1504): Audit APPROVED`

---

## 🚀 Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| Materials supported | 62 types | `len(MATERIAL_COLORS) == 62` |
| Tests passing | 12/12 (100%) | `pytest tests/agent/unit/test_material_extraction_v2.py` |
| Baseline regression | 0 (119/119) | `pytest tests/unit/` |
| Database migration | Applied | Check constraint removed |
| Existing blocks updated | 6 blocks → "Montjuïc" | `SELECT COUNT(*) FROM blocks WHERE material_type = 'Montjuïc'` |
| Color mapping available | 62 colors | `MATERIAL_COLORS["Ulldecona"]` returns RGB |

---

## 📚 References

### Source Documents
- **Original C# Dictionary:** Provided by BIM Manager (2026-03-07)
- **T-1503 Implementation:** `src/agent/tasks/geometry_processing.py` (lines 260-370)
- **T-1503 Tests:** `tests/agent/unit/test_material_extraction.py` (420 lines)
- **Database Schema:** T-1501 migration `20260306000001_element_model.sql`

### Related Tickets
- **T-1501-DB:** Added `material_type` column ✅ DONE
- **T-1502-INFRA:** Storage path conventions ✅ DONE
- **T-1503-AGENT:** Material extraction (INCORRECT SPECS) ✅ DONE (Superseded)
- **T-1504-AGENT:** This ticket (CORRECT SPECS) 🔜 READY

---

## ⚠️ Risks & Mitigations

### Risk 1: Accent Handling in Material Names
**Issue:** "Montjuïc" has special character (ï). Input might be "Montjuic" (sin tilde).  
**Mitigation:** Use `unicodedata.normalize('NFKD', text)` to normalize before comparison.

### Risk 2: Case Sensitivity
**Issue:** Input could be "MONTJUÏC", "montjuïc", "MontJuïc".  
**Mitigation:** Already handled by `.capitalize()` in `_validate_and_normalize_material()`.

### Risk 3: Existing Blocks with "Stone"/"Ceramic"
**Issue:** 6 production blocks have `material_type = "Stone"` from T-1503.  
**Mitigation:** Database migration converts "Stone" → "Montjuïc" automatically.

### Risk 4: Frontend Expects Color Values
**Issue:** Frontend dashboard needs RGB colors to render materials.  
**Mitigation:** `MATERIAL_COLORS` dict provides RGB. Backend API should return color in response (future ticket: T-1505-BACK).

### Risk 5: Performance with 62 Materials
**Issue:** Dictionary lookup with 62 keys might be slow.  
**Mitigation:** Python dict lookups are O(1). No performance impact expected.

---

## 🎓 Lessons Learned from T-1503

1. **Verify specs with real data:** Always check actual .3dm files before implementing
2. **Ask for examples:** Request sample UserString values from BIM Manager
3. **Document source systems:** C# dictionary from BIM tools should be documented
4. **Test with realistic data:** Use real material names in tests, not generic placeholders

---

**Status:** 🔜 READY FOR RED PHASE  
**Next Step:** Create test file with 12 failing tests  
**Estimated Time:** RED (30 min) + GREEN (45 min) + REFACTOR (30 min) + AUDIT (20 min) = ~2 hours total
