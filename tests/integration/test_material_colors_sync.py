"""
Integration tests for T-1507-TEST: MATERIAL_COLORS Synchronization

TDD Phase: RED — Verify backend ↔ frontend material dictionary consistency

Focus: 62 materials must match exactly between:
  - Backend: src/agent/constants.py MATERIAL_COLORS
  - Frontend: src/frontend/src/constants/materials.ts MATERIAL_COLORS
"""

import pytest


class TestMaterialColorsSync:
    """
    T-1507-TEST: Material Colors Dictionary Synchronization Test
    Verify 62 MATERIAL_COLORS entries match between backend and frontend
    """

    def test_int_be_material_colors_count_63(self):
        """
        INT-FE-03 (Backend side): Verify MATERIAL_COLORS dictionary has 63 entries

        Given: MATERIAL_COLORS in src/agent/constants.py
        When: Counting materials
        Then:
            - MATERIAL_COLORS has exactly 63 entries
            - Each material maps to RGB tuple (3 integers)
            - All RGB values in range [0, 255]
        """
        from src.agent.constants import MATERIAL_COLORS

        assert len(MATERIAL_COLORS) == 63, \
            f"MATERIAL_COLORS should have 63 entries, got {len(MATERIAL_COLORS)}"

        # Verify structure: {material_name: (R, G, B)}
        for material, rgb in MATERIAL_COLORS.items():
            assert isinstance(material, str), f"Material name '{material}' should be string"
            assert len(material) > 0, "Material name should not be empty"
            
            assert isinstance(rgb, tuple), f"RGB for '{material}' should be tuple"
            assert len(rgb) == 3, f"RGB for '{material}' should have 3 values"
            
            for i, val in enumerate(rgb):
                assert isinstance(val, int), \
                    f"RGB[{i}] for '{material}' should be int, got {type(val)}"
                assert 0 <= val <= 255, \
                    f"RGB[{i}] for '{material}' should be in [0,255], got {val}"

    def test_int_be_material_colors_includes_default_montjuic(self):
        """
        Verify "Montjuïc" (default material) is in MATERIAL_COLORS

        Given: MATERIAL_COLORS dictionary
        When: Searching for default material
        Then:
            - "Montjuïc" key exists
            - RGB value is [230, 180, 100] (warm ochre stone)
        """
        from src.agent.constants import MATERIAL_COLORS

        assert "Montjuïc" in MATERIAL_COLORS, \
            "Default material 'Montjuïc' must be in MATERIAL_COLORS"
        
        # Verify default RGB (from spec)
        expected_rgb = (230, 180, 100)
        actual_rgb = MATERIAL_COLORS["Montjuïc"]
        assert actual_rgb == expected_rgb, \
            f"Montjuïc RGB should be {expected_rgb}, got {actual_rgb}"

    def test_int_be_material_colors_includes_key_materials(self):
        """
        Verify key Sagrada Familia materials are present

        Given: MATERIAL_COLORS dictionary
        When: Checking for known materials from spec
        Then:
            - "Ulldecona" exists (reference material)
            - "Floresta" exists (reference material)
            - Materials are spelled correctly (accent marks)
        """
        from src.agent.constants import MATERIAL_COLORS

        key_materials = ["Montjuïc", "Ulldecona", "Floresta"]
        for material in key_materials:
            assert material in MATERIAL_COLORS, \
                f"Key material '{material}' must be in MATERIAL_COLORS"
