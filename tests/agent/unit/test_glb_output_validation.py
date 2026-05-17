"""
Unit tests for GLB output format and scale correctness (T-0502-AGENT).

These tests exercise the real trimesh export path with synthetic geometry
(no rhino3dm, no S3, no DB) to verify that the binary GLB produced by the
pipeline is safe for web rendering in the Three.js viewer.

Contract being tested:
  - GLB binary is valid (correct magic bytes, parseable by trimesh)
  - Vertex coordinates are in millimetres, centred near origin (< 10 m)
  - Face count is at or below DECIMATION_TARGET_FACES after pipeline
  - No NaN / Infinity in vertex data
  - Normals exist and are non-degenerate
  - Draco path produces a smaller file than the uncompressed path
    (when gltf-pipeline is available in the test environment)
"""

import os
import struct
import tempfile

import numpy as np
import pytest
import trimesh

# Check if fast-simplification is available
try:
    import fast_simplification
    HAS_FAST_SIMPLIFICATION = True
except ImportError:
    HAS_FAST_SIMPLIFICATION = False

from src.agent.constants import DECIMATION_TARGET_FACES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GLB_MAGIC = b"glTF"
_GLTF_PIPELINE_AVAILABLE: bool | None = None  # Cached after first check


def _is_gltf_pipeline_available() -> bool:
    global _GLTF_PIPELINE_AVAILABLE
    if _GLTF_PIPELINE_AVAILABLE is None:
        import subprocess
        try:
            subprocess.run(
                ["gltf-pipeline", "--version"],
                capture_output=True,
                check=True,
                timeout=10,
            )
            _GLTF_PIPELINE_AVAILABLE = True
        except Exception:
            _GLTF_PIPELINE_AVAILABLE = False
    return _GLTF_PIPELINE_AVAILABLE


def _export_mesh_to_glb(mesh: trimesh.Trimesh) -> bytes:
    """Export trimesh to a GLB byte string (mirrors _export_and_upload_glb internals)."""
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        tmp_path = f.name
    try:
        mesh.export(tmp_path, file_type="glb")
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass


def _export_mesh_to_tmp_path(mesh: trimesh.Trimesh) -> str:
    """Export mesh to a temp file, returning the path. Caller is responsible for cleanup."""
    fd, path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    mesh.export(path, file_type="glb")
    return path


def _apply_full_pipeline(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Run extract→decimate steps on a synthetic mesh (mirrors geometry_processing steps)."""
    from src.agent.tasks.geometry_processing import _apply_decimation

    # Centre (mirrors _extract_and_merge_meshes)
    centroid = mesh.centroid.copy()
    mesh = mesh.copy()
    mesh.vertices = mesh.vertices - centroid

    # Decimate
    mesh, _ = _apply_decimation(mesh, DECIMATION_TARGET_FACES, "test-block-id")
    return mesh


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def capitel_like_mesh():
    """Icosphere ≈ 1 280 faces at origin — simulates a low-detail capitel (stone capital).

    Real capitels are ~300mm wide × 400mm tall; we use radius=150 to approximate that scale.
    """
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=150.0)
    return sphere


@pytest.fixture
def large_mesh_needs_decimation():
    """High-poly icosphere ~20 000 faces — forces the decimation branch."""
    sphere = trimesh.creation.icosphere(subdivisions=5, radius=500.0)
    assert len(sphere.faces) > DECIMATION_TARGET_FACES
    return sphere


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGLBFormat:
    """The binary GLB produced by the pipeline must be valid for web rendering."""

    def test_glb_magic_bytes(self, capitel_like_mesh):
        """GLB must start with the 4-byte 'glTF' magic string (RFC 2397 §2.1)."""
        glb_bytes = _export_mesh_to_glb(capitel_like_mesh)
        assert glb_bytes[:4] == GLB_MAGIC, (
            f"First 4 bytes are {glb_bytes[:4]!r}, expected {GLB_MAGIC!r}"
        )

    def test_glb_version_is_2(self, capitel_like_mesh):
        """GLB version field must be 2 (glTF 2.0 — required by Three.js useGLTF)."""
        glb_bytes = _export_mesh_to_glb(capitel_like_mesh)
        # Header layout: magic(4) version(4) length(4)
        version = struct.unpack_from("<I", glb_bytes, 4)[0]
        assert version == 2, f"GLB version {version} != 2"

    def test_glb_parseable_by_trimesh(self, large_mesh_needs_decimation):
        """trimesh.load() must be able to re-parse the GLB without exceptions."""
        processed = _apply_full_pipeline(large_mesh_needs_decimation)
        glb_path = _export_mesh_to_tmp_path(processed)
        try:
            loaded = trimesh.load(glb_path, force="mesh")
            assert loaded is not None
        finally:
            os.remove(glb_path)


class TestGLBScale:
    """Vertex coordinates must be in millimetres, centred near origin."""

    def test_vertex_range_within_10m_of_origin(self, capitel_like_mesh):
        """No vertex may be further than 10 000 mm (10 m) from origin.

        A part centred at origin should not have vertices beyond its own bounding
        box.  10 m is a conservative upper bound for the largest SF architectural
        piece.
        """
        processed = _apply_full_pipeline(capitel_like_mesh)
        glb_bytes = _export_mesh_to_glb(processed)

        reloaded = trimesh.load(
            trimesh.util.wrap_as_stream(glb_bytes),
            file_type="glb",
            force="mesh",
        )
        max_coord = np.abs(reloaded.vertices).max()
        assert max_coord < 10_000.0, (
            f"Max vertex coordinate {max_coord:.1f} mm exceeds 10 000 mm threshold. "
            "Geometry may not have been centred."
        )

    def test_no_nan_or_inf_in_vertices(self, large_mesh_needs_decimation):
        """Vertex buffer must contain only finite numbers."""
        processed = _apply_full_pipeline(large_mesh_needs_decimation)
        glb_bytes = _export_mesh_to_glb(processed)

        reloaded = trimesh.load(
            trimesh.util.wrap_as_stream(glb_bytes),
            file_type="glb",
            force="mesh",
        )
        assert np.isfinite(reloaded.vertices).all(), (
            "GLB vertex buffer contains NaN or Inf values — Three.js will render nothing."
        )

    def test_vertex_coordinates_are_mm_scale_not_meters(self, capitel_like_mesh):
        """Confirm coordinates are in mm, not converted to meters.

        A capitel with radius=150 mm should have vertices in the ±150 mm range,
        NOT ±0.150 m.  If someone mistakenly divides by 1000, max_coord ≈ 0.15.
        """
        processed = _apply_full_pipeline(capitel_like_mesh)
        glb_bytes = _export_mesh_to_glb(processed)

        reloaded = trimesh.load(
            trimesh.util.wrap_as_stream(glb_bytes),
            file_type="glb",
            force="mesh",
        )
        max_coord = np.abs(reloaded.vertices).max()
        assert max_coord > 10.0, (
            f"Max coordinate {max_coord:.3f} looks like meters, not mm. "
            "Do not divide Rhino coordinates by 1000."
        )


class TestGLBGeometry:
    """Geometric properties of the GLB must satisfy viewer requirements."""

    @pytest.mark.skipif(not HAS_FAST_SIMPLIFICATION, reason="fast-simplification module not installed")
    def test_face_count_at_or_below_target(self, large_mesh_needs_decimation):
        """After decimation, face count must not exceed DECIMATION_TARGET_FACES."""
        processed = _apply_full_pipeline(large_mesh_needs_decimation)
        assert len(processed.faces) <= DECIMATION_TARGET_FACES, (
            f"Face count {len(processed.faces)} exceeds target {DECIMATION_TARGET_FACES}. "
            "Decimation did not run or failed silently."
        )

    @pytest.mark.skipif(not HAS_FAST_SIMPLIFICATION, reason="fast-simplification module not installed")
    def test_decimation_achieves_reduction_for_high_poly_mesh(self, large_mesh_needs_decimation):
        """High-poly mesh must be reduced by at least 50%."""
        original_faces = len(large_mesh_needs_decimation.faces)
        processed = _apply_full_pipeline(large_mesh_needs_decimation)
        reduction = 1.0 - len(processed.faces) / original_faces
        assert reduction >= 0.5, (
            f"Decimation only reduced faces by {reduction * 100:.1f}% "
            f"(from {original_faces} to {len(processed.faces)}). "
            "Expected at least 50% reduction for high-poly input."
        )

    def test_already_low_poly_skips_decimation(self):
        """Mesh below target must pass through unchanged."""
        from src.agent.tasks.geometry_processing import _apply_decimation

        small_sphere = trimesh.creation.icosphere(subdivisions=1, radius=100.0)
        assert len(small_sphere.faces) < DECIMATION_TARGET_FACES

        result, face_count = _apply_decimation(small_sphere, DECIMATION_TARGET_FACES, "test")
        assert face_count == len(small_sphere.faces), (
            "Decimation should be skipped when mesh is already below target."
        )

    def test_normals_are_nonzero_after_export(self, capitel_like_mesh):
        """Mesh must have vertex normals (required for meshStandardMaterial lighting)."""
        processed = _apply_full_pipeline(capitel_like_mesh)
        glb_bytes = _export_mesh_to_glb(processed)

        reloaded = trimesh.load(
            trimesh.util.wrap_as_stream(glb_bytes),
            file_type="glb",
            force="mesh",
        )
        # vertex_normals raises if not computable
        norms = reloaded.vertex_normals
        zero_norms = np.all(norms == 0, axis=1).sum()
        assert zero_norms < len(norms) * 0.01, (
            f"{zero_norms}/{len(norms)} vertex normals are zero-length. "
            "Lighting will be broken in Three.js."
        )


class TestDracoCompression:
    """_apply_draco_compression must reduce file size when gltf-pipeline is available."""

    def test_draco_produces_smaller_file(self, capitel_like_mesh):
        """Draco-compressed GLB must be smaller than the uncompressed source."""
        if not _is_gltf_pipeline_available():
            pytest.skip("gltf-pipeline not installed — skipping Draco test")

        from src.agent.tasks.geometry_processing import _apply_draco_compression

        raw_path = _export_mesh_to_tmp_path(capitel_like_mesh)
        fd, draco_path = tempfile.mkstemp(suffix=".glb")
        os.close(fd)
        try:
            applied = _apply_draco_compression(raw_path, draco_path)
            assert applied, "Draco compression reported failure despite gltf-pipeline being available"

            raw_kb = os.path.getsize(raw_path) // 1024
            draco_kb = os.path.getsize(draco_path) // 1024
            assert draco_kb < raw_kb, (
                f"Draco GLB ({draco_kb} KB) is not smaller than raw GLB ({raw_kb} KB)"
            )
        finally:
            for p in (raw_path, draco_path):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass

    def test_draco_fallback_copies_file_when_unavailable(self, capitel_like_mesh):
        """When gltf-pipeline is absent, file must be copied unchanged (no exception)."""
        from src.agent.tasks.geometry_processing import _apply_draco_compression
        import subprocess

        raw_path = _export_mesh_to_tmp_path(capitel_like_mesh)
        fd, draco_path = tempfile.mkstemp(suffix=".glb")
        os.close(fd)
        try:
            # Patch subprocess.run to simulate missing gltf-pipeline
            import unittest.mock as mock
            with mock.patch("src.agent.tasks.geometry_processing.subprocess.run",
                            side_effect=FileNotFoundError("gltf-pipeline not found")):
                applied = _apply_draco_compression(raw_path, draco_path)

            assert not applied, "Should return False when falling back"
            assert os.path.getsize(draco_path) == os.path.getsize(raw_path), (
                "Fallback copy must produce an identical file"
            )
        finally:
            for p in (raw_path, draco_path):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
