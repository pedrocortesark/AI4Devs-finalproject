"""
Unit tests for Material Type Extraction from Rhino UserStrings (T-1503-AGENT).

Tests the _extract_material_type() function that extracts and validates
material_type from Rhino .3dm file UserStrings with priority search:
  1. Document-level UserString
  2. Layer-level UserString
  3. Object-level UserString
  4. Default to "Stone"

TDD Phase: RED - These tests will fail until implementation is complete.
"""

import pytest
from unittest.mock import MagicMock, Mock
from src.agent.tasks.geometry_processing import _extract_material_type


# ===== FIXTURES =====

@pytest.fixture
def mock_rhino_file_with_document_material():
    """Mock rhino3dm.File3dm with Material UserString at document level."""
    mock_file = MagicMock()
    
    # Document-level user strings
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material", "Project"]
    mock_strings.__getitem__ = lambda self, key: {
        "Material": "Stone",
        "Project": "Sagrada Familia"
    }[key]
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    return mock_file


@pytest.fixture
def mock_rhino_file_with_layer_material():
    """Mock rhino3dm.File3dm with Material UserString at layer level."""
    mock_file = MagicMock()
    
    # No document strings
    mock_file.Strings = None
    
    # Layer with Material UserString
    mock_layer = MagicMock()
    mock_layer.Name = "SF-C12-M-001"
    
    mock_layer_strings = MagicMock()
    mock_layer_strings.Keys = ["Material", "Workshop"]
    mock_layer_strings.__getitem__ = lambda self, key: {
        "Material": "Ceramic",
        "Workshop": "Granollers"
    }[key]
    
    mock_layer.GetUserStrings = lambda: mock_layer_strings
    
    mock_file.Layers = [mock_layer]
    mock_file.Objects = []
    
    return mock_file


@pytest.fixture
def mock_rhino_file_with_object_material():
    """Mock rhino3dm.File3dm with Material UserString at object level."""
    mock_file = MagicMock()
    
    # No document or layer strings
    mock_file.Strings = None
    mock_file.Layers = []
    
    # Object with Material UserString
    mock_obj = MagicMock()
    mock_attrs = MagicMock()
    mock_attrs.Id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    
    mock_obj_strings = MagicMock()
    mock_obj_strings.Keys = ["Material", "Mass"]
    mock_obj_strings.__getitem__ = lambda self, key: {
        "Material": "Stone",
        "Mass": "450kg"
    }[key]
    
    mock_attrs.GetUserStrings = lambda: mock_obj_strings
    mock_obj.Attributes = mock_attrs
    
    mock_file.Objects = [mock_obj]
    
    return mock_file


@pytest.fixture
def mock_rhino_file_no_material():
    """Mock rhino3dm.File3dm with NO Material UserString."""
    mock_file = MagicMock()
    
    # Document strings without Material
    mock_strings = MagicMock()
    mock_strings.Keys = ["Project", "RevisionDate"]
    mock_strings.__getitem__ = lambda self, key: {
        "Project": "Sagrada Familia",
        "RevisionDate": "2026-03-01"
    }[key]
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    return mock_file


# ===== HAPPY PATH TESTS =====

def test_hp_01_extract_stone_from_document_level(mock_rhino_file_with_document_material):
    """
    HP-01: Extract Material UserString "Stone" from document level.
    
    Given: .3dm file with document-level UserString "Material": "Stone"
    When: _extract_material_type() is called
    Then: Returns "Stone"
    """
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-001"
    
    result = _extract_material_type(
        mock_rhino_file_with_document_material,
        block_id,
        iso_code
    )
    
    assert result == "Stone", "Should extract 'Stone' from document-level UserString"


def test_hp_02_extract_ceramic_from_document_level():
    """
    HP-02: Extract Material UserString "Ceramic" from document level.
    
    Given: .3dm file with document-level UserString "Material": "Ceramic"
    When: _extract_material_type() is called
    Then: Returns "Ceramic"
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "Ceramic"
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-002"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Ceramic", "Should extract 'Ceramic' from document-level UserString"


def test_hp_03_extract_from_layer_when_no_document(mock_rhino_file_with_layer_material):
    """
    HP-03: Extract Material UserString from layer level when document level not found.
    
    Given: .3dm file with NO document-level Material, but layer has "Material": "Ceramic"
    When: _extract_material_type() is called
    Then: Returns "Ceramic" from layer UserString
    """
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-003"
    
    result = _extract_material_type(
        mock_rhino_file_with_layer_material,
        block_id,
        iso_code
    )
    
    assert result == "Ceramic", "Should extract 'Ceramic' from layer-level UserString"


def test_hp_04_extract_from_object_when_no_document_or_layer(mock_rhino_file_with_object_material):
    """
    HP-04: Extract Material UserString from object level (last priority).
    
    Given: .3dm file with NO document/layer Material, but object has "Material": "Stone"
    When: _extract_material_type() is called
    Then: Returns "Stone" from object UserString
    """
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-004"
    
    result = _extract_material_type(
        mock_rhino_file_with_object_material,
        block_id,
        iso_code
    )
    
    assert result == "Stone", "Should extract 'Stone' from object-level UserString"


def test_hp_05_default_to_stone_when_not_found(mock_rhino_file_no_material):
    """
    HP-05: Default to "Stone" when Material UserString not found anywhere.
    
    Given: .3dm file with NO Material UserString at any level
    When: _extract_material_type() is called
    Then: Returns "Stone" (default for architectural elements)
    """
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-005"
    
    result = _extract_material_type(
        mock_rhino_file_no_material,
        block_id,
        iso_code
    )
    
    assert result == "Stone", "Should default to 'Stone' when Material UserString not found"


# ===== EDGE CASES (Normalization) =====

def test_ec_01_normalize_lowercase_to_title_case():
    """
    EC-01: Normalize lowercase "stone" to "Stone".
    
    Given: Material UserString with value "stone" (lowercase)
    When: _extract_material_type() is called
    Then: Normalizes to "Stone" (title case)
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "stone"  # lowercase
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-EC01"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should normalize lowercase 'stone' to 'Stone'"


def test_ec_02_trim_whitespace():
    """
    EC-02: Trim leading/trailing whitespace from Material value.
    
    Given: Material UserString with value " Ceramic " (whitespace)
    When: _extract_material_type() is called
    Then: Trims and returns "Ceramic"
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "  Ceramic  "  # whitespace
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-EC02"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Ceramic", "Should trim whitespace from ' Ceramic '"


def test_ec_03_normalize_uppercase_to_title_case():
    """
    EC-03: Normalize uppercase "STONE" to "Stone".
    
    Given: Material UserString with value "STONE" (uppercase)
    When: _extract_material_type() is called
    Then: Normalizes to "Stone"
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "STONE"  # uppercase
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-EC03"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should normalize uppercase 'STONE' to 'Stone'"


def test_ec_04_multiple_layers_uses_first_found():
    """
    EC-04: When multiple layers have Material UserString, use first found.
    
    Given: .3dm file with 3 layers, 2nd and 3rd have Material UserString
    When: _extract_material_type() is called
    Then: Returns value from 2nd layer (first found in iteration)
    """
    mock_file = MagicMock()
    mock_file.Strings = None
    
    # Layer 1: No Material
    layer1 = MagicMock()
    layer1.Name = "Layer-1"
    layer1.GetUserStrings = lambda: None
    
    # Layer 2: Has Material "Stone"
    layer2 = MagicMock()
    layer2.Name = "Layer-2"
    mock_strings_2 = MagicMock()
    mock_strings_2.Keys = ["Material"]
    mock_strings_2.__getitem__ = lambda self, key: "Stone"
    layer2.GetUserStrings = lambda: mock_strings_2
    
    # Layer 3: Has Material "Ceramic" (should be ignored)
    layer3 = MagicMock()
    layer3.Name = "Layer-3"
    mock_strings_3 = MagicMock()
    mock_strings_3.Keys = ["Material"]
    mock_strings_3.__getitem__ = lambda self, key: "Ceramic"
    layer3.GetUserStrings = lambda: mock_strings_3
    
    mock_file.Layers = [layer1, layer2, layer3]
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-EC04"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should use Material from first layer that has it (Layer-2)"


# ===== ERROR HANDLING (Invalid Values) =====

def test_err_01_invalid_material_wood_defaults_to_stone():
    """
    ERR-01: Invalid Material value "Wood" logs warning and defaults to "Stone".
    
    Given: Material UserString with invalid value "Wood"
    When: _extract_material_type() is called
    Then: Logs WARNING and returns "Stone" (default)
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "Wood"  # Invalid material
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-ERR01"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should default to 'Stone' when Material value is invalid ('Wood')"


def test_err_02_empty_string_defaults_to_stone():
    """
    ERR-02: Empty Material value "" defaults to "Stone".
    
    Given: Material UserString with empty string value
    When: _extract_material_type() is called
    Then: Returns "Stone" (default)
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: ""  # Empty string
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-ERR02"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should default to 'Stone' when Material value is empty string"


def test_err_03_invalid_material_concrete_defaults_to_stone():
    """
    ERR-03: Invalid Material value "concrete" logs warning and defaults to "Stone".
    
    Given: Material UserString with invalid value "concrete"
    When: _extract_material_type() is called
    Then: Logs WARNING and returns "Stone" (default)
    """
    mock_file = MagicMock()
    
    mock_strings = MagicMock()
    mock_strings.Keys = ["Material"]
    mock_strings.__getitem__ = lambda self, key: "concrete"  # Invalid material
    
    mock_file.Strings = mock_strings
    mock_file.Layers = []
    mock_file.Objects = []
    
    block_id = "550e8400-e29b-41d4-a716-446655440000"
    iso_code = "SAGR-Z1-ERR03"
    
    result = _extract_material_type(mock_file, block_id, iso_code)
    
    assert result == "Stone", "Should default to 'Stone' when Material value is invalid ('concrete')"
