"""
Unit tests for Material Type Extraction - Real Stone Dictionary (T-1504-AGENT).

Tests the _extract_material_type() function that extracts and validates
material_type from Rhino .3dm file UserStrings using 62 real stone types
from Sagrada Família MATERIAL_COLORS dictionary.

Key Changes from T-1503-AGENT:
  - Materials: 2 generic (Stone/Ceramic) → 62 real types (Montjuïc, Ulldecona, Floresta, etc.)
  - Extraction: Document→Layer→Object priority → **Object UserString ONLY**
  - Default: "Stone" → "Montjuïc" (most common material)
  - Validation: Against 62-material dictionary with RGB colors

TDD Phase: RED - These tests will fail until T-1504 implementation is complete.
"""

import pytest
from unittest.mock import MagicMock, Mock
from src.agent.tasks.geometry_processing import _extract_material_type, _validate_and_normalize_material


# ===== FIXTURES =====

@pytest.fixture
def mock_rhino_file_with_object_material():
    """Mock rhino3dm.File3dm with Material UserString at object level."""
    def _create_file(material_name: str):
        mock_file = MagicMock()
        
        # Object with Material UserString
        mock_obj = MagicMock()
        mock_attrs = MagicMock()
        mock_attrs.Id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
        
        mock_obj_strings = MagicMock()
        mock_obj_strings.Keys = ["Material", "Mass"]
        mock_obj_strings.__getitem__ = lambda self, key: {
            "Material": material_name,
            "Mass": "450kg"
        }[key]
        
        mock_attrs.GetUserStrings = lambda: mock_obj_strings
        mock_obj.Attributes = mock_attrs
        
        mock_file.Objects = [mock_obj]
        
        return mock_file
    
    return _create_file


@pytest.fixture
def mock_rhino_file_multiple_objects():
    """Mock rhino3dm.File3dm with multiple objects (different materials)."""
    def _create_file(material_names: list[str]):
        mock_file = MagicMock()
        
        objects = []
        for mat_name in material_names:
            mock_obj = MagicMock()
            mock_attrs = MagicMock()
            
            mock_obj_strings = MagicMock()
            mock_obj_strings.Keys = ["Material"]
            mock_obj_strings.__getitem__ = lambda self, key, mat=mat_name: mat if key == "Material" else None
            
            mock_attrs.GetUserStrings = lambda strings=mock_obj_strings: strings
            mock_obj.Attributes = mock_attrs
            objects.append(mock_obj)
        
        mock_file.Objects = objects
        
        return mock_file
    
    return _create_file


@pytest.fixture
def mock_rhino_file_no_material():
    """Mock rhino3dm.File3dm with NO Material UserString."""
    mock_file = MagicMock()
    
    # Object WITHOUT Material UserString
    mock_obj = MagicMock()
    mock_attrs = MagicMock()
    
    mock_obj_strings = MagicMock()
    mock_obj_strings.Keys = ["Mass", "Workshop"]  # No "Material" key
    mock_obj_strings.__getitem__ = lambda self, key: {
        "Mass": "450kg",
        "Workshop": "Granollers"
    }[key] if key in ["Mass", "Workshop"] else None
    
    mock_attrs.GetUserStrings = lambda: mock_obj_strings
    mock_obj.Attributes = mock_attrs
    
    mock_file.Objects = [mock_obj]
    
    return mock_file


@pytest.fixture
def mock_rhino_file_empty():
    """Mock rhino3dm.File3dm with NO objects at all."""
    mock_file = MagicMock()
    mock_file.Objects = []
    return mock_file


# ===== HAPPY PATH TESTS =====

def test_hp_01_extract_montjuic_from_object_level(mock_rhino_file_with_object_material):
    """
    HP-01: Extract Material UserString "Montjuïc" from object level.
    
    Given: .3dm file with object-level UserString "Material": "Montjuïc"
    When: _extract_material_type() is called
    Then: Returns "Montjuïc"
    
    AC-02: Extracción Solo de Object UserStrings
    """
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-001"
    
    rhino_file = mock_rhino_file_with_object_material("Montjuïc")
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Montjuïc", "Should extract 'Montjuïc' from object-level UserString"


def test_hp_02_extract_ulldecona_from_object_level(mock_rhino_file_with_object_material):
    """
    HP-02: Extract Material UserString "Ulldecona" from object level.
    
    Given: .3dm file with object-level UserString "Material": "Ulldecona"
    When: _extract_material_type() is called
    Then: Returns "Ulldecona"
    
    AC-02: Extracción Solo de Object UserStrings
    """
    block_id = "550e8400-e29b-41d4-a716-446655440001"
    iso_code = "SAGR-Z1-002"
    
    rhino_file = mock_rhino_file_with_object_material("Ulldecona")
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Ulldecona", "Should extract 'Ulldecona' from object-level UserString"


def test_hp_03_extract_floresta_from_object_level(mock_rhino_file_with_object_material):
    """
    HP-03: Extract Material UserString "Floresta" from object level.
    
    Given: .3dm file with object-level UserString "Material": "Floresta"
    When: _extract_material_type() is called
    Then: Returns "Floresta"
    
    AC-02: Extracción Solo de Object UserStrings
    """
    block_id = "550e8400-e29b-41d4-a716-446655440002"
    iso_code = "SAGR-Z1-003"
    
    rhino_file = mock_rhino_file_with_object_material("Floresta")
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Floresta", "Should extract 'Floresta' from object-level UserString"


def test_hp_04_multiple_objects_uses_first_found(mock_rhino_file_multiple_objects):
    """
    HP-04: When multiple objects have Material UserString, use first match.
    
    Given: .3dm file with 2 objects: first has "Ulldecona", second has "Floresta"
    When: _extract_material_type() is called
    Then: Returns "Ulldecona" (first match)
    
    AC-02: Object-level extraction priority
    """
    block_id = "550e8400-e29b-41d4-a716-446655440003"
    iso_code = "SAGR-Z1-004"
    
    rhino_file = mock_rhino_file_multiple_objects(["Ulldecona", "Floresta"])
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Ulldecona", "Should use first object's material when multiple objects exist"


def test_hp_05_default_to_montjuic_when_not_found(mock_rhino_file_no_material):
    """
    HP-05: Default to "Montjuïc" when no Material UserString found.
    
    Given: .3dm file with object but NO "Material" UserString
    When: _extract_material_type() is called
    Then: Returns "Montjuïc" (default material)
    
    AC-05: Default Fallback a Montjuïc
    """
    block_id = "550e8400-e29b-41d4-a716-446655440004"
    iso_code = "SAGR-Z1-005"
    
    result = _extract_material_type(mock_rhino_file_no_material, block_id, iso_code)
    
    assert result == "Montjuïc", "Should default to 'Montjuïc' when Material UserString not found"


# ===== EDGE CASES TESTS =====

def test_ec_01_normalize_lowercase_to_title_case(mock_rhino_file_with_object_material):
    """
    EC-01: Normalize lowercase input "ulldecona" → "Ulldecona" (title case).
    
    Given: Object UserString with "Material": "ulldecona" (lowercase)
    When: _extract_material_type() is called
    Then: Normalizes to "Ulldecona" and matches dictionary
    
    AC-03: Normalización de Input
    """
    block_id = "550e8400-e29b-41d4-a716-446655440005"
    iso_code = "SAGR-Z1-006"
    
    rhino_file = mock_rhino_file_with_object_material("ulldecona")  # lowercase
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Ulldecona", "Should normalize 'ulldecona' → 'Ulldecona' (title case)"


def test_ec_02_trim_whitespace(mock_rhino_file_with_object_material):
    """
    EC-02: Trim leading/trailing whitespace from " Montjuïc " → "Montjuïc".
    
    Given: Object UserString with "Material": "  Montjuïc  " (whitespace)
    When: _extract_material_type() is called
    Then: Trims whitespace and returns "Montjuïc"
    
    AC-03: Normalización de Input
    """
    block_id = "550e8400-e29b-41d4-a716-446655440006"
    iso_code = "SAGR-Z1-007"
    
    rhino_file = mock_rhino_file_with_object_material("  Montjuïc  ")  # whitespace
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Montjuïc", "Should trim whitespace '  Montjuïc  ' → 'Montjuïc'"


def test_ec_03_normalize_uppercase_to_title_case(mock_rhino_file_with_object_material):
    """
    EC-03: Normalize uppercase input "FLORESTA" → "Floresta" (title case).
    
    Given: Object UserString with "Material": "FLORESTA" (uppercase)
    When: _extract_material_type() is called
    Then: Normalizes to "Floresta"
    
    AC-03: Normalización de Input
    """
    block_id = "550e8400-e29b-41d4-a716-446655440007"
    iso_code = "SAGR-Z1-008"
    
    rhino_file = mock_rhino_file_with_object_material("FLORESTA")  # uppercase
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Floresta", "Should normalize 'FLORESTA' → 'Floresta' (title case)"


def test_ec_04_empty_objects_list_defaults_to_montjuic(mock_rhino_file_empty):
    """
    EC-04: When .3dm has no objects at all, default to "Montjuïc".
    
    Given: .3dm file with empty Objects list
    When: _extract_material_type() is called
    Then: Returns "Montjuïc" (default)
    
    AC-05: Default Fallback a Montjuïc
    """
    block_id = "550e8400-e29b-41d4-a716-446655440008"
    iso_code = "SAGR-Z1-009"
    
    result = _extract_material_type(mock_rhino_file_empty, block_id, iso_code)
    
    assert result == "Montjuïc", "Should default to 'Montjuïc' when .3dm has no objects"


# ===== ERROR HANDLING TESTS =====

def test_err_01_invalid_material_granite_defaults_to_montjuic(mock_rhino_file_with_object_material):
    """
    ERR-01: Invalid material "Granite" defaults to "Montjuïc" + warning logged.
    
    Given: Object UserString with "Material": "Granite" (not in 62-material dictionary)
    When: _extract_material_type() is called
    Then: Returns "Montjuïc" (default) and logs warning
    
    AC-04: Validación Contra 62 Materiales
    """
    block_id = "550e8400-e29b-41d4-a716-446655440009"
    iso_code = "SAGR-Z1-010"
    
    rhino_file = mock_rhino_file_with_object_material("Granite")  # Invalid material
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Montjuïc", "Should default to 'Montjuïc' when material 'Granite' is invalid"


def test_err_02_empty_string_defaults_to_montjuic(mock_rhino_file_with_object_material):
    """
    ERR-02: Empty string "" in Material UserString defaults to "Montjuïc".
    
    Given: Object UserString with "Material": "" (empty string)
    When: _extract_material_type() is called
    Then: Returns "Montjuïc" (default) and logs warning
    
    AC-04: Validación Contra 62 Materiales
    """
    block_id = "550e8400-e29b-41d4-a716-446655440010"
    iso_code = "SAGR-Z1-011"
    
    rhino_file = mock_rhino_file_with_object_material("")  # Empty string
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Montjuïc", "Should default to 'Montjuïc' when material is empty string"


def test_err_03_invalid_material_concrete_defaults_to_montjuic(mock_rhino_file_with_object_material):
    """
    ERR-03: Invalid material "Concrete" defaults to "Montjuïc" + warning logged.
    
    Given: Object UserString with "Material": "Concrete" (not in 62-material dictionary)
    When: _extract_material_type() is called
    Then: Returns "Montjuïc" (default) and logs warning
    
    AC-04: Validación Contra 62 Materiales
    """
    block_id = "550e8400-e29b-41d4-a716-446655440011"
    iso_code = "SAGR-Z1-012"
    
    rhino_file = mock_rhino_file_with_object_material("Concrete")  # Invalid material
    
    result = _extract_material_type(rhino_file, block_id, iso_code)
    
    assert result == "Montjuïc", "Should default to 'Montjuïc' when material 'Concrete' is invalid"
