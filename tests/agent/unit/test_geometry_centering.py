"""
Unit tests for geometry centering and bbox computation (T-0502-AGENT).

Verifies that _extract_and_merge_meshes:
  1. Translates world-space Rhino coordinates to origin (centroid ≈ [0,0,0])
  2. Preserves bounding-box dimensions after centring
  3. Returns a valid bbox dict in centred coordinates

These tests encode the coordinate-system contract between the agent and the
Three.js viewer: the GLB must be centred at origin so PartMesh.tsx can place
it at its grid position without per-part offset math.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

import trimesh

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_mesh_at(vertices_np: np.ndarray, n_tris: int = 20):
    """Build a mock rhino3dm mesh object from a numpy vertex array.

    Uses simple degenerate triangles (all indices cycling through the vertex list),
    which is enough to exercise the extraction / centering path without needing
    watertight geometry.
    """
    mock_mesh = MagicMock()
    mock_mesh.Vertices = [
        MagicMock(X=float(v[0]), Y=float(v[1]), Z=float(v[2]))
        for v in vertices_np
    ]
    n_verts = len(vertices_np)
    mock_faces = []
    for i in range(n_tris):
        f = MagicMock()
        f.IsQuad = False
        f.A = i % n_verts
        f.B = (i + 1) % n_verts
        f.C = (i + 2) % n_verts
        mock_faces.append(f)
    mock_mesh.Faces = mock_faces
    return mock_mesh


def _make_rhino_file(mock_mesh):
    """Wrap a mock mesh in a mock rhino3dm File3dm."""
    mock_obj = MagicMock()
    mock_obj.Geometry = mock_mesh
    mock_obj.Geometry.ObjectType = 32  # ObjectType.Mesh
    mock_obj.Attributes.Id = "aa000000-0000-0000-0000-000000000001"

    mock_file = MagicMock()
    mock_file.Objects = [mock_obj]
    mock_file.InstanceDefinitions = []
    return mock_file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_box_at_origin():
    """200×300×400 mm axis-aligned box centred at origin."""
    verts = np.array([
        [-100, -150, -200],
        [ 100, -150, -200],
        [ 100,  150, -200],
        [-100,  150, -200],
        [-100, -150,  200],
        [ 100, -150,  200],
        [ 100,  150,  200],
        [-100,  150,  200],
    ], dtype=float)
    return verts


@pytest.fixture
def box_at_rhino_world_space():
    """Same 200×300×400 mm box but translated to a Sagrada Família building position.

    Typical .3dm files have geometry 45 000–75 000 mm from the world origin.
    """
    offset = np.array([45000.0, 73000.0, 12000.0])
    verts = np.array([
        [-100, -150, -200],
        [ 100, -150, -200],
        [ 100,  150, -200],
        [-100,  150, -200],
        [-100, -150,  200],
        [ 100, -150,  200],
        [ 100,  150,  200],
        [-100,  150,  200],
    ], dtype=float) + offset
    return verts, offset


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGeometryCentring:
    """_extract_and_merge_meshes must centre geometry at origin before export."""

    def _run_extract(self, rhino_file, block_id="test-block-id", iso_code="SF-TEST-T-001"):
        """Helper: call the real _extract_and_merge_meshes with rhino3dm patched."""
        from src.agent.tasks.geometry_processing import _extract_and_merge_meshes
        import rhino3dm as r3dm

        with patch.object(r3dm, 'ObjectType') as mock_ot:
            mock_ot.InstanceReference = 4096
            mock_ot.Mesh = 32
            mock_ot.Brep = 16
            return _extract_and_merge_meshes(rhino_file, block_id, iso_code)

    # ------------------------------------------------------------------
    # 1. Centroid ends up near origin
    # ------------------------------------------------------------------
    def test_centroid_within_tolerance_after_centring(self, small_box_at_origin):
        """After centring, centroid must be within 1 mm of [0, 0, 0]."""
        # Translate box away from origin to simulate world-space input
        offset = np.array([12345.0, -6789.0, 999.0])
        mock_mesh = _make_mock_mesh_at(small_box_at_origin + offset)
        rhino_file = _make_rhino_file(mock_mesh)

        mesh, _, _ = self._run_extract(rhino_file)

        centroid_dist = np.linalg.norm(mesh.centroid)
        assert centroid_dist < 1.0, (
            f"Centroid {mesh.centroid.tolist()} is {centroid_dist:.3f} mm from origin "
            f"(tolerance 1 mm)"
        )

    # ------------------------------------------------------------------
    # 2. Sagrada Família building-position coordinates get centred
    # ------------------------------------------------------------------
    def test_world_space_coordinates_centred(self, box_at_rhino_world_space):
        """Geometry at Sagrada Família building position must be moved to origin."""
        verts, offset = box_at_rhino_world_space
        mock_mesh = _make_mock_mesh_at(verts)
        rhino_file = _make_rhino_file(mock_mesh)

        mesh, _, _ = self._run_extract(rhino_file)

        centroid_dist = np.linalg.norm(mesh.centroid)
        assert centroid_dist < 1.0, (
            f"World-space geometry at offset {offset.tolist()} not centred: "
            f"centroid = {mesh.centroid.tolist()}, dist = {centroid_dist:.3f} mm"
        )

    # ------------------------------------------------------------------
    # 3. Dimensions are preserved (centring is a pure translation)
    # ------------------------------------------------------------------
    def test_dimensions_preserved_after_centring(self, box_at_rhino_world_space):
        """Bounding-box dimensions must be unchanged by the centring translation.

        The box is 200×300×400 mm regardless of where it sits in the world.
        """
        verts, _ = box_at_rhino_world_space
        mock_mesh = _make_mock_mesh_at(verts)
        rhino_file = _make_rhino_file(mock_mesh)

        mesh, _, _ = self._run_extract(rhino_file)

        dims = mesh.bounds[1] - mesh.bounds[0]  # [width, height, depth]
        expected = np.array([200.0, 300.0, 400.0])
        np.testing.assert_allclose(dims, expected, atol=1.0,
            err_msg=f"Dimensions changed after centring: {dims} != {expected}")

    # ------------------------------------------------------------------
    # 4. Returned bbox matches mesh.bounds in centred space
    # ------------------------------------------------------------------
    def test_bbox_matches_centred_mesh_bounds(self, small_box_at_origin):
        """The returned bbox dict must equal trimesh.bounds of the centred mesh."""
        mock_mesh = _make_mock_mesh_at(small_box_at_origin)
        rhino_file = _make_rhino_file(mock_mesh)

        mesh, _, bbox = self._run_extract(rhino_file)

        np.testing.assert_allclose(bbox["min"], mesh.bounds[0], atol=1e-6)
        np.testing.assert_allclose(bbox["max"], mesh.bounds[1], atol=1e-6)

    # ------------------------------------------------------------------
    # 5. bbox keys and shape
    # ------------------------------------------------------------------
    def test_bbox_has_required_keys_and_shape(self, small_box_at_origin):
        """bbox must have 'min' and 'max' keys, each a list of 3 floats."""
        mock_mesh = _make_mock_mesh_at(small_box_at_origin)
        rhino_file = _make_rhino_file(mock_mesh)

        _, _, bbox = self._run_extract(rhino_file)

        assert "min" in bbox and "max" in bbox
        assert len(bbox["min"]) == 3
        assert len(bbox["max"]) == 3
        assert all(isinstance(v, float) for v in bbox["min"])
        assert all(isinstance(v, float) for v in bbox["max"])

    # ------------------------------------------------------------------
    # 6. bbox dimensions match expected part size
    # ------------------------------------------------------------------
    def test_bbox_dimensions_match_geometry(self, box_at_rhino_world_space):
        """bbox max - bbox min must equal the actual part dimensions."""
        verts, _ = box_at_rhino_world_space
        mock_mesh = _make_mock_mesh_at(verts)
        rhino_file = _make_rhino_file(mock_mesh)

        _, _, bbox = self._run_extract(rhino_file)

        dims = [
            bbox["max"][0] - bbox["min"][0],
            bbox["max"][1] - bbox["min"][1],
            bbox["max"][2] - bbox["min"][2],
        ]
        assert abs(dims[0] - 200.0) < 1.0, f"Width {dims[0]} != 200mm"
        assert abs(dims[1] - 300.0) < 1.0, f"Height {dims[1]} != 300mm"
        assert abs(dims[2] - 400.0) < 1.0, f"Depth {dims[2]} != 400mm"

    # ------------------------------------------------------------------
    # 7. Multiple meshes merged before centring
    # ------------------------------------------------------------------
    def test_multiple_meshes_centred_as_single_unit(self):
        """When a file contains multiple meshes they must be merged THEN centred."""
        # Two spheres at opposite world-space positions
        s1 = trimesh.creation.icosphere(subdivisions=1, radius=50.0)
        s1.apply_translation([10000.0, 20000.0, 30000.0])
        s2 = trimesh.creation.icosphere(subdivisions=1, radius=50.0)
        s2.apply_translation([10200.0, 20000.0, 30000.0])

        mock_objects = []
        for sphere in (s1, s2):
            mock_mesh = MagicMock()
            mock_mesh.Vertices = [
                MagicMock(X=float(v[0]), Y=float(v[1]), Z=float(v[2]))
                for v in sphere.vertices
            ]
            mock_faces = []
            for face in sphere.faces:
                f = MagicMock()
                f.IsQuad = False
                f.A, f.B, f.C = int(face[0]), int(face[1]), int(face[2])
                mock_faces.append(f)
            mock_mesh.Faces = mock_faces

            mock_obj = MagicMock()
            mock_obj.Geometry = mock_mesh
            mock_obj.Geometry.ObjectType = 32
            mock_obj.Attributes.Id = f"aa{id(sphere):016x}"[:36]
            mock_objects.append(mock_obj)

        mock_file = MagicMock()
        mock_file.Objects = mock_objects
        mock_file.InstanceDefinitions = []

        mesh, _, bbox = self._run_extract(mock_file)

        centroid_dist = np.linalg.norm(mesh.centroid)
        assert centroid_dist < 1.0, (
            f"Merged mesh centroid {mesh.centroid.tolist()} not at origin "
            f"(dist={centroid_dist:.3f} mm)"
        )
        # Each sphere is 100mm diameter; the pair spans ~300mm on X
        dims = mesh.bounds[1] - mesh.bounds[0]
        assert dims[0] > 100.0, f"X-span {dims[0]} should be >100mm for 2 separated spheres"
