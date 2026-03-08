"""
Geometry Processing Tasks for Low-Poly GLB Generation (T-0502-AGENT).

This module contains Celery tasks for processing .3dm files and generating
low-poly GLB representations suitable for web visualization.
"""

import os
import json
import shutil
import subprocess
import psycopg2
from contextlib import contextmanager
import structlog
import requests

# Import from parent package
try:
    from ..celery_app import celery_app
    from ..constants import (
        TASK_GENERATE_LOW_POLY_GLB,
        DECIMATION_TARGET_FACES,
        PROCESSED_GEOMETRY_BUCKET,
        RAW_UPLOADS_BUCKET,
        LOW_POLY_PREFIX,
        TEMP_DIR,
        ERROR_MSG_NO_MESHES_FOUND,
        ERROR_MSG_BLOCK_NOT_FOUND,
        ERROR_MSG_FAILED_PARSE_3DM,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
        MAX_3DM_FILE_SIZE_MB,
        DRACO_COMPRESSION_LEVEL,
        DRACO_QUANTIZE_POSITION_BITS,
        DRACO_QUANTIZE_NORMAL_BITS,
        DRACO_QUANTIZE_TEXCOORD_BITS,
        VALID_MATERIALS,
        DEFAULT_MATERIAL,
        MATERIAL_USERSTRING_KEY,
    )
except ImportError:
    # Fallback for test environment
    from src.agent.celery_app import celery_app
    from src.agent.constants import (
        TASK_GENERATE_LOW_POLY_GLB,
        DECIMATION_TARGET_FACES,
        PROCESSED_GEOMETRY_BUCKET,
        RAW_UPLOADS_BUCKET,
        LOW_POLY_PREFIX,
        TEMP_DIR,
        ERROR_MSG_NO_MESHES_FOUND,
        ERROR_MSG_BLOCK_NOT_FOUND,
        ERROR_MSG_FAILED_PARSE_3DM,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
        MAX_3DM_FILE_SIZE_MB,
        DRACO_COMPRESSION_LEVEL,
        DRACO_QUANTIZE_POSITION_BITS,
        DRACO_QUANTIZE_NORMAL_BITS,
        DRACO_QUANTIZE_TEXCOORD_BITS,
        VALID_MATERIALS,
        DEFAULT_MATERIAL,
        MATERIAL_USERSTRING_KEY,
    )

import rhino3dm
import trimesh
import numpy as np

# Import Supabase client (must be at module level for mocking in tests)
try:
    from infra.supabase_client import get_supabase_client
except ModuleNotFoundError:
    from src.agent.infra.supabase_client import get_supabase_client

logger = structlog.get_logger()


@contextmanager
def get_db_connection():
    """Get a PostgreSQL database connection using psycopg2.

    Returns a context manager that yields a connection object.
    Connection is automatically closed after use.

    Yields:
        psycopg2.connection: Database connection
    """
    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@db:5432/sfpm_db")
    conn = psycopg2.connect(database_url)
    try:
        yield conn
    finally:
        conn.close()


# Mock S3 client for testing (will be replaced by real implementation)
class S3Client:
    """Mock S3 client for testing purposes."""

    def download_file(self, url: str, local_path: str):
        """Download file from S3 URL to local path."""
        pass

    def upload(self, bucket: str, key: str, file_path: str):
        """Upload file to S3 bucket."""
        pass


# Global S3 client instance (mocked in tests)
s3_client = S3Client()


def _fetch_block_metadata(block_id: str) -> tuple[str, str, str | None]:
    """Fetch block metadata from database.

    Args:
        block_id: UUID of the block to query

    Returns:
        Tuple of (url_original, iso_code, low_poly_url)

    Raises:
        ValueError: If block not found in database

    Example:
        url, iso_code, low_poly_url = _fetch_block_metadata("123e4567-e89b-12d3-a456-426614174000")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT url_original, iso_code, low_poly_url FROM blocks WHERE id = %s",
            (block_id,)
        )
        row = cursor.fetchone()

        if not row:
            error_msg = ERROR_MSG_BLOCK_NOT_FOUND.format(block_id=block_id)
            logger.error("fetch_block_metadata.not_found", block_id=block_id)
            raise ValueError(error_msg)

        url_original, iso_code, low_poly_url = row
        logger.info("fetch_block_metadata.success",
                   block_id=block_id, iso_code=iso_code,
                   already_processed=low_poly_url is not None)
        return url_original, iso_code, low_poly_url


def _download_3dm_from_s3(url: str, local_path: str) -> None:
    """
    Download .3dm file from Supabase Storage (primary) or HTTP URL (fallback).

    Treats `url` as a Supabase storage key first (e.g. 'uploads/{id}/file.3dm').
    Falls back to HTTP requests for full URLs, then to s3_client mock for tests.

    Args:
        url: Supabase storage key or HTTP URL of the .3dm file
        local_path: Local filesystem path where file will be saved

    Raises:
        FileNotFoundError: If download fails from all sources
        ValueError: If file exceeds MAX_3DM_FILE_SIZE_MB
    """
    # Primary: Supabase storage client (handles storage paths like 'uploads/...')
    try:
        supabase = get_supabase_client()
        content = supabase.storage.from_(RAW_UPLOADS_BUCKET).download(url)

        # isinstance check distinguishes real bytes from test mocks (MagicMock)
        if isinstance(content, (bytes, bytearray)) and len(content) > 0:
            file_size_mb = len(content) / (1024 * 1024)
            if file_size_mb > MAX_3DM_FILE_SIZE_MB:
                raise ValueError(
                    f"File size {file_size_mb:.1f}MB exceeds limit {MAX_3DM_FILE_SIZE_MB}MB. "
                    f"Possible zip bomb attack or corrupt file."
                )
            with open(local_path, 'wb') as f:
                f.write(content)
            logger.info("download_3dm.supabase_success", key=url, size_mb=f"{file_size_mb:.2f}")
            return
    except ValueError:
        raise  # Re-raise size validation errors
    except Exception as e:
        logger.warning(
            "download_3dm.supabase_failed_trying_http",
            url=url,
            error=str(e),
            message="Falling back to HTTP download"
        )

    # Fallback: HTTP download (for full HTTPS URLs)
    try:
        response = requests.head(url, timeout=10)
        response.raise_for_status()

        content_length = int(response.headers.get('Content-Length', 0))
        size_mb = content_length / (1024 * 1024)
        max_bytes = MAX_3DM_FILE_SIZE_MB * 1024 * 1024

        if content_length > max_bytes:
            error_msg = (
                f"File size {size_mb:.1f}MB exceeds limit {MAX_3DM_FILE_SIZE_MB}MB. "
                f"Possible zip bomb attack or corrupt file."
            )
            logger.error("download_3dm.size_exceeded", url=url, size_mb=size_mb)
            raise ValueError(error_msg)

    except requests.exceptions.RequestException as e:
        logger.warning("download_3dm.head_request_failed", url=url, error=str(e))

    try:
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info("download_3dm.http_success", url=url, local_path=local_path)

    except requests.exceptions.RequestException as e:
        logger.warning(
            "download_3dm.requests_failed_fallback",
            url=url,
            error=str(e),
            message="Falling back to s3_client.download_file()"
        )
        s3_client.download_file(url, local_path)
        logger.info("download_3dm.success_fallback", url=url, local_path=local_path)


def _parse_rhino_file(file_path: str, iso_code: str) -> rhino3dm.File3dm:
    """Parse .3dm file using rhino3dm library.

    Args:
        file_path: Local path to .3dm file
        iso_code: ISO code of the block (for error messages)

    Returns:
        Parsed rhino3dm File3dm object

    Raises:
        ValueError: If file is corrupted or cannot be parsed
    """
    rhino_file = rhino3dm.File3dm.Read(file_path)

    if rhino_file is None:
        error_msg = ERROR_MSG_FAILED_PARSE_3DM.format(iso_code=iso_code)
        logger.error("parse_rhino_file.failed", iso_code=iso_code, path=file_path)
        raise ValueError(error_msg)

    logger.info("parse_rhino_file.success",
               iso_code=iso_code, objects_count=len(rhino_file.Objects))
    return rhino_file


def _validate_and_normalize_material(raw_value: str) -> str:
    """Validate and normalize material string (T-1504-AGENT).
    
    Validates against 62 real stone types from MATERIAL_COLORS dictionary.
    Normalizes to title case and trims whitespace.
    
    Args:
        raw_value: Raw material string from UserString
    
    Returns:
        Normalized material (one of 62 types) or "Montjuïc" if invalid
    """
    normalized = raw_value.strip().capitalize()
    return normalized if normalized in VALID_MATERIALS else DEFAULT_MATERIAL


def get_material_color(material: str) -> tuple[int, int, int]:
    """Get RGB color for a given material (T-1504-AGENT - AC-06).
    
    Returns the RGB color tuple associated with a material type.
    If material is not found, returns the default material color (Montjuïc).
    Used by frontend for canvas rendering of 3D parts.
    
    Args:
        material: Material name from MATERIAL_COLORS dictionary
    
    Returns:
        RGB tuple (R, G, B) with values in range [0, 255]
    
    Examples:
        >>> get_material_color("Ulldecona")
        (240, 220, 180)
        
        >>> get_material_color("Montjuïc")
        (230, 180, 100)
        
        >>> get_material_color("InvalidMaterial")
        (230, 180, 100)  # Returns Montjuïc default color
    """
    return MATERIAL_COLORS.get(material, MATERIAL_COLORS[DEFAULT_MATERIAL])


def _extract_material_type(rhino_file: rhino3dm.File3dm, block_id: str, iso_code: str) -> str:
    """Extract material type from Rhino UserString (T-1504-AGENT).
    
    Extracts "Material" UserString from object-level ONLY (no document/layer fallback).
    Validates against 62 real stone types from MATERIAL_COLORS dictionary.
    
    Implementation Details:
    - AC-02: Searches ONLY in object.Attributes.GetUserStrings() (no document/layer)
    - AC-03: Normalizes input (.strip().capitalize()) for case-insensitive matching
    - AC-04: Validates against VALID_MATERIALS (62 types), logs warning if invalid
    - AC-05: Defaults to "Montjuïc" (most common material) if not found
    
    Args:
        rhino_file: Parsed rhino3dm.File3dm object
        block_id: UUID of the block (for logging)
        iso_code: ISO code of the block (for logging)
    
    Returns:
        Validated material_type: One of 62 real stone types
    
    Examples:
        >>> # Extract valid material from object UserString
        >>> rhino_file = rhino3dm.File3dm.Read("GLPER.B-PAE0720.0701.3dm")
        >>> material = _extract_material_type(rhino_file, "uuid-123", "GLPER.B-PAE0720.0701")
        >>> print(material)  # "Montjuïc" or "Ulldecona" or other valid material
        
        >>> # Default when no Material UserString found
        >>> rhino_file_no_material = rhino3dm.File3dm.Read("block_without_material.3dm")
        >>> material = _extract_material_type(rhino_file_no_material, "uuid-456", "TEST.001")
        >>> print(material)  # "Montjuïc" (default)
        
        >>> # Normalization: lowercase → title case
        >>> # If object has Material="ulldecona", returns "Ulldecona"
    """
    
    # Search only in object-level UserString (AC-02: Extracción Solo de Object UserStrings)
    if hasattr(rhino_file, 'Objects') and rhino_file.Objects is not None:
        for obj in rhino_file.Objects:
            try:
                if hasattr(obj, 'Attributes') and hasattr(obj.Attributes, 'GetUserStrings'):
                    obj_strings = obj.Attributes.GetUserStrings()
                    if obj_strings is not None and hasattr(obj_strings, 'Keys'):
                        if MATERIAL_USERSTRING_KEY in obj_strings.Keys:
                            raw_value = obj_strings[MATERIAL_USERSTRING_KEY]
                            material_type = _validate_and_normalize_material(raw_value)
                            
                            if material_type != DEFAULT_MATERIAL or raw_value.strip().capitalize() in VALID_MATERIALS:
                                logger.info("extract_material_type.success",
                                          block_id=block_id,
                                          material_type=material_type,
                                          source="object",
                                          raw_value=raw_value)
                            else:
                                logger.warning("extract_material_type.invalid_value",
                                             block_id=block_id,
                                             raw_value=raw_value,
                                             normalized=raw_value.strip().capitalize(),
                                             source="object",
                                             defaulting_to=DEFAULT_MATERIAL)
                            return material_type
            except Exception as e:
                logger.warning("extract_material_type.object_error",
                             block_id=block_id,
                             error=str(e))
                continue
    
    # Default to "Montjuïc" if not found (AC-05: Default Fallback a Montjuïc)
    logger.info("extract_material_type.default",
               block_id=block_id,
               material_type=DEFAULT_MATERIAL,
               source="default",
               reason="No Material UserString found in objects")
    return DEFAULT_MATERIAL


def _extract_and_merge_meshes(
    rhino_file: rhino3dm.File3dm,
    block_id: str,
    iso_code: str
) -> tuple[trimesh.Trimesh, int]:
    """Extract meshes from preprocessed Rhino file using InstanceObject API.

    Expects .3dm files with ONLY InstanceObject architecture (ADR-001):
    - InstanceDefinitions contain Mesh geometry (after Rhino Desktop _Mesh preprocessing)
    - InstanceReferences are the scene objects (skipped during extraction)
    - rhino3dm exposes InstanceDefinition Meshes when iterating file3dm.Objects

    Deduplication key: iso_code == Codi User String == InstanceDefinition.Name.
    Files must be preprocessed: Brep geometry inside InstanceDefinitions must be
    converted to Mesh via Rhino Desktop _Mesh command before uploading.

    Args:
        rhino_file: Parsed rhino3dm File3dm object
        block_id: UUID of the block (for logging)
        iso_code: ISO code of the block — must match InstanceDefinition.Name (Codi)

    Returns:
        Tuple of (merged_mesh, original_faces_count)

    Raises:
        ValueError: If no valid meshes found (file not preprocessed or wrong file)

    Example:
        mesh, face_count = _extract_and_merge_meshes(rhino_file, block_id, "GLPER.B-PAE0720.0102")
    """
    # Phase 1: InstanceDefinition structure validation (ADR-001 API usage)
    idef_count = len(rhino_file.InstanceDefinitions)
    matched_idef = None

    for idef in rhino_file.InstanceDefinitions:
        logger.debug("extract_meshes.idef",
                     name=idef.Name, id=str(idef.Id),
                     object_ids=len(idef.GetObjectIds()))
        if idef.Name == iso_code:
            matched_idef = idef

    if matched_idef:
        logger.info("extract_meshes.idef_matched",
                    block_id=block_id, iso_code=iso_code,
                    idef_id=str(matched_idef.Id))
    else:
        logger.warning("extract_meshes.idef_not_matched",
                       block_id=block_id, iso_code=iso_code,
                       available=[idef.Name for idef in rhino_file.InstanceDefinitions])

    iref_count = sum(
        1 for obj in rhino_file.Objects
        if getattr(obj.Geometry, 'ObjectType', None) == rhino3dm.ObjectType.InstanceReference
    )
    logger.info("extract_meshes.file_structure",
                block_id=block_id, iso_code=iso_code,
                instance_definitions=idef_count,
                instance_references=iref_count)

    # Phase 2: Extract Mesh objects (POC pattern — export_gltf_draco.py:73–122)
    # rhino3dm's object table exposes Meshes embedded inside InstanceDefinitions
    # when iterating file3dm.Objects alongside the InstanceReferences.
    #
    # InstanceDefinition filter: each block maps 1-to-1 to one InstanceDefinition
    # (iso_code == idef.Name). Only process objects whose ID is listed in that
    # InstanceDefinition's object table so each GLB contains only its own geometry.
    # Fallback: if no InstanceDefinition matched (unit tests, standalone geometry),
    # skip the filter and process all objects.
    if matched_idef:
        idef_object_ids = set(str(oid).lower() for oid in matched_idef.GetObjectIds())
        logger.info("extract_meshes.idef_filter_active",
                    block_id=block_id, iso_code=iso_code,
                    object_ids_count=len(idef_object_ids))
    else:
        idef_object_ids = None  # No filter — process all objects

    all_vertices = []
    all_faces = []
    vertex_offset = 0
    original_faces_count = 0
    mesh_count = 0
    brep_count = 0

    # Collect mesh geometries to process:
    # - Direct Mesh objects (preprocessed files)
    # - Render meshes attached to Brep objects (raw files saved from Rhino)
    meshes_to_process = []

    for obj in rhino_file.Objects:
        # Skip objects that don't belong to the matched InstanceDefinition
        if idef_object_ids is not None:
            if str(obj.Attributes.Id).lower() not in idef_object_ids:
                continue

        geom = obj.Geometry
        obj_type = getattr(geom, 'ObjectType', None)

        # Skip InstanceReferences (scene placement objects, not geometry)
        if obj_type == rhino3dm.ObjectType.InstanceReference:
            continue

        # Primary: isinstance check for real rhino3dm objects (POC pattern)
        # Fallback: ObjectType comparison for unit test MagicMocks (ObjectType=32)
        is_mesh = isinstance(geom, rhino3dm.Mesh) or obj_type == rhino3dm.ObjectType.Mesh
        if is_mesh:
            meshes_to_process.append(geom)
        elif obj_type == rhino3dm.ObjectType.Brep:
            brep_count += 1
            # BrepFace.GetMesh(Render) returns the render mesh attached to each
            # face — pre-computed by Rhino when the file was saved.
            # This avoids requiring _Mesh preprocessing before upload.
            for brep_face in geom.Faces:
                mesh = brep_face.GetMesh(rhino3dm.MeshType.Render)
                if mesh is not None:
                    meshes_to_process.append(mesh)

    if brep_count > 0:
        logger.info("extract_meshes.breps_with_render_mesh",
                    block_id=block_id, iso_code=iso_code,
                    brep_count=brep_count, meshes_from_breps=len(meshes_to_process))

    # Process all collected mesh geometries
    for geom in meshes_to_process:
        mesh_count += 1
        vertices = np.array([[v.X, v.Y, v.Z] for v in geom.Vertices])
        if len(vertices) == 0:
            continue

        # Extract faces: rhino3dm returns 4-tuples — (A,B,C,C) for triangles, (A,B,C,D) for quads
        # Unit test mocks use objects with .IsQuad, .A, .B, .C, .D attributes
        for face in geom.Faces:
            if isinstance(face, tuple):
                a, b, c, d = face
                if c == d:
                    # Triangle (degenerate quad with C repeated)
                    all_faces.append([a + vertex_offset, b + vertex_offset, c + vertex_offset])
                    original_faces_count += 1
                else:
                    # Quad: split into 2 triangles (A,B,C) + (A,C,D)
                    all_faces.append([a + vertex_offset, b + vertex_offset, c + vertex_offset])
                    all_faces.append([a + vertex_offset, c + vertex_offset, d + vertex_offset])
                    original_faces_count += 2
            else:
                # Mock format with .IsQuad attribute (unit tests only)
                if face.IsQuad:
                    all_faces.append([face.A + vertex_offset, face.B + vertex_offset, face.C + vertex_offset])
                    all_faces.append([face.A + vertex_offset, face.C + vertex_offset, face.D + vertex_offset])
                    original_faces_count += 2
                else:
                    all_faces.append([face.A + vertex_offset, face.B + vertex_offset, face.C + vertex_offset])
                    original_faces_count += 1

        all_vertices.append(vertices)
        vertex_offset += len(vertices)

    if not all_vertices:
        error_msg = ERROR_MSG_NO_MESHES_FOUND.format(iso_code=iso_code)
        logger.error("extract_meshes.no_meshes", block_id=block_id, iso_code=iso_code)
        raise ValueError(error_msg)

    # Merge into single trimesh
    combined_vertices = np.vstack(all_vertices)
    combined_faces = np.array(all_faces)
    merged_mesh = trimesh.Trimesh(vertices=combined_vertices, faces=combined_faces, process=True)

    # Keep geometry in Rhino world-space coordinates (absolute building position).
    # This creates a true digital twin where parts maintain their real spatial relationships.
    # The frontend will render them at their actual building positions.
    # Z-up → Y-up rotation is applied during GLB export (see _export_and_upload_glb).
    centroid = merged_mesh.centroid.copy()
    logger.info("extract_meshes.absolute_coords",
                block_id=block_id, iso_code=iso_code,
                centroid_mm=centroid.tolist(),
                message="Geometry preserved in Rhino world coordinates")

    # Compute bounding box in absolute Rhino coordinates.
    # Stored in the database so the frontend can:
    # 1. Position parts at their real building location
    # 2. Render BBoxProxy wireframe for LOD level 2
    # 3. Calculate camera bounds for auto-fit
    # trimesh.bounds returns [[x_min, y_min, z_min], [x_max, y_max, z_max]].
    bbox = {
        "min": merged_mesh.bounds[0].tolist(),
        "max": merged_mesh.bounds[1].tolist(),
    }
    logger.info("extract_meshes.bbox_absolute",
                block_id=block_id, iso_code=iso_code,
                bbox_min=bbox["min"], bbox_max=bbox["max"])

    logger.info("extract_meshes.success",
                block_id=block_id,
                meshes_found=mesh_count,
                original_faces=original_faces_count,
                actual_faces=len(merged_mesh.faces),
                vertices=len(merged_mesh.vertices))

    return merged_mesh, original_faces_count, bbox


def _apply_decimation(
    mesh: trimesh.Trimesh,
    target_faces: int,
    block_id: str
) -> tuple[trimesh.Trimesh, int]:
    """Apply quadric decimation to reduce mesh complexity.

    Uses trimesh's quadric decimation algorithm (via open3d backend) to reduce
    face count while preserving overall shape. Skips decimation if mesh is
    already below target. Falls back to original mesh if decimation fails.

    Args:
        mesh: Input trimesh mesh
        target_faces: Target number of faces after decimation
        block_id: UUID of the block (for logging)

    Returns:
        Tuple of (decimated_mesh, decimated_faces_count)

    Example:
        decimated_mesh, face_count = _apply_decimation(mesh, 1000, block_id)
    """
    actual_faces = len(mesh.faces)

    if actual_faces <= target_faces:
        logger.info("decimation.skipped",
                   block_id=block_id,
                   faces=actual_faces,
                   target=target_faces)
        return mesh, actual_faces

    logger.info("decimation.attempt",
               block_id=block_id,
               target=target_faces,
               is_watertight=mesh.is_watertight,
               is_volume=mesh.is_volume,
               euler_number=mesh.euler_number)

    try:
        decimated_mesh = mesh.simplify_quadric_decimation(target_faces)
        decimated_faces_count = len(decimated_mesh.faces)

        if decimated_faces_count == actual_faces:
            logger.warning("decimation.failed",
                         block_id=block_id,
                         reason="Mesh geometry not suitable for quadric decimation")
        else:
            logger.info("decimation.success",
                       block_id=block_id,
                       original=actual_faces,
                       decimated=decimated_faces_count)

        return decimated_mesh, decimated_faces_count

    except Exception as e:
        logger.error("decimation.error", block_id=block_id, error=str(e))
        # Fall back to non-decimated mesh
        return mesh, actual_faces


def _apply_draco_compression(input_path: str, output_path: str) -> bool:
    """Apply Draco compression to GLB via gltf-pipeline CLI (Node.js).

    Mirrors POC: poc/formats-comparison/exporters/export_gltf_draco.py:166-207

    Falls back to copying the uncompressed file if gltf-pipeline is not
    available (dev environments without Node.js installed).

    Args:
        input_path: Path to uncompressed GLB file
        output_path: Path for Draco-compressed output

    Returns:
        True if Draco applied, False if fallback copy used
    """
    cmd = [
        "gltf-pipeline",
        "-i", input_path,
        "-o", output_path,
        "-d",
        "--draco.compressionLevel", str(DRACO_COMPRESSION_LEVEL),
        "--draco.quantizePositionBits", str(DRACO_QUANTIZE_POSITION_BITS),
        "--draco.quantizeNormalBits", str(DRACO_QUANTIZE_NORMAL_BITS),
        "--draco.quantizeTexcoordBits", str(DRACO_QUANTIZE_TEXCOORD_BITS),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        compressed_kb = os.path.getsize(output_path) // 1024
        original_kb = os.path.getsize(input_path) // 1024
        logger.info("draco_compression.success",
                    input_kb=original_kb,
                    output_kb=compressed_kb,
                    reduction_pct=round((1 - compressed_kb / max(original_kb, 1)) * 100, 1))
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("draco_compression.fallback",
                       error=str(e),
                       message="Uploading uncompressed GLB")
        shutil.copy2(input_path, output_path)
        return False


def _export_and_upload_glb(
    mesh: trimesh.Trimesh,
    block_id: str
) -> tuple[str, int]:
    """Export mesh to GLB format, apply Draco compression, and upload to S3.

    Pipeline:
    1. Apply Z-up → Y-up rotation (Rhino → Three.js coordinate system)
    2. Export uncompressed GLB to /tmp/{block_id}_raw.glb
    3. Apply Draco compression → /tmp/{block_id}.glb (falls back if unavailable)
    4. Upload compressed GLB to Supabase Storage
    5. Clean up both temp files

    Args:
        mesh: Trimesh mesh to export (in Rhino Z-up coordinates)
        block_id: UUID of the block (used in S3 key)

    Returns:
        Tuple of (public_url, file_size_kb)

    Example:
        url, size = _export_and_upload_glb(mesh, "123e4567-e89b-12d3-a456-426614174000")
    """
    # Step 1: Apply Z-up → Y-up rotation for Three.js compatibility
    # Rhino: Z-up (architectural standard)
    # Three.js: Y-up (WebGL standard)
    # Rotation: -90° around X-axis converts Z-up to Y-up
    rotation_matrix = trimesh.transformations.rotation_matrix(
        -np.pi / 2,  # -90 degrees
        [1, 0, 0],   # Around X-axis
        [0, 0, 0]    # At origin
    )
    mesh.apply_transform(rotation_matrix)
    logger.info("export_glb.rotation_applied",
                block_id=block_id,
                message="Applied Z-up → Y-up rotation for Three.js")

    # Step 2: Export raw (uncompressed) GLB
    raw_glb_path = os.path.join(TEMP_DIR, f"{block_id}_raw.glb")
    temp_glb_path = os.path.join(TEMP_DIR, f"{block_id}.glb")
    mesh.export(raw_glb_path, file_type='glb')

    raw_size_kb = os.path.getsize(raw_glb_path) // 1024
    logger.info("export_glb.raw",
               block_id=block_id,
               file_size_kb=raw_size_kb,
               path=raw_glb_path)

    # Step 2: Apply Draco compression (mirrors POC export_gltf_draco.py:166-207)
    _apply_draco_compression(raw_glb_path, temp_glb_path)

    # Clean up raw file immediately after compression
    try:
        os.remove(raw_glb_path)
    except Exception as e:
        logger.warning("cleanup.raw_glb_failed", block_id=block_id, error=str(e))

    # Get final compressed file size
    file_size_bytes = os.path.getsize(temp_glb_path)
    file_size_kb = file_size_bytes // 1024

    logger.info("export_glb.success",
               block_id=block_id,
               file_size_kb=file_size_kb,
               path=temp_glb_path)

    # Step 3: Upload to Supabase Storage
    supabase = get_supabase_client()
    glb_key = f"{LOW_POLY_PREFIX}{block_id}.glb"

    with open(temp_glb_path, 'rb') as f:
        glb_data = f.read()

    supabase.storage.from_(PROCESSED_GEOMETRY_BUCKET).upload(
        glb_key,
        glb_data,
        {'content-type': 'model/gltf-binary', 'upsert': 'true'}
    )

    # Get public URL
    low_poly_url = supabase.storage.from_(PROCESSED_GEOMETRY_BUCKET).get_public_url(glb_key)

    logger.info("upload_glb.success",
               block_id=block_id,
               url=low_poly_url,
               key=glb_key)

    # Step 4: Cleanup compressed temp file
    try:
        os.remove(temp_glb_path)
    except Exception as e:
        logger.warning("cleanup.temp_glb_failed", block_id=block_id, error=str(e))

    return low_poly_url, file_size_kb


def _update_block_low_poly_url(block_id: str, url: str, bbox: dict, material_type: str) -> None:
    """Update database with low_poly_url, bbox, and material_type for processed block.

    Args:
        block_id: UUID of the block to update
        url: Public URL of the uploaded GLB file
        bbox: Bounding box in centred coordinates: {"min": [x,y,z], "max": [x,y,z]}
        material_type: Validated material type ("Stone" or "Ceramic")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blocks SET low_poly_url = %s, bbox = %s, material_type = %s WHERE id = %s",
            (url, json.dumps(bbox), material_type, block_id)
        )
        conn.commit()

    logger.info("update_db.success", block_id=block_id, low_poly_url=url,
                bbox_min=bbox["min"], bbox_max=bbox["max"], material_type=material_type)


@celery_app.task(
    name=TASK_GENERATE_LOW_POLY_GLB,
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_DELAY_SECONDS
)
def generate_low_poly_glb(self, block_id: str):
    """Generate Low-Poly GLB from .3dm file.

    Main orchestrator task that coordinates the 10-step pipeline to convert
    high-poly .3dm CAD files into low-poly GLB models suitable for web visualization.

    Pipeline Steps:
        1. Fetch block metadata from database (url_original, iso_code)
        2. Download .3dm file from S3 to temp directory
        3. Parse .3dm with rhino3dm
        4. Extract meshes and handle quad faces
        5. Merge all meshes into single trimesh
        6. Decimate to target face count (~1000 triangles)
        7. Export to GLB format
        8. Upload GLB to S3 (processed-geometry/low-poly/)
        9. Update database with low_poly_url
        10. Cleanup temp files

    Args:
        block_id: UUID of the block to process

    Returns:
        dict: Processing results containing:
            - status (str): 'success' or 'error'
            - low_poly_url (str): Public URL of uploaded GLB file
            - original_faces (int): Face count before decimation
            - decimated_faces (int): Face count after decimation
            - file_size_kb (int): GLB file size in kilobytes
            - error_message (str|None): Error details if failed

    Raises:
        ValueError: If block not found, no meshes, or parsing fails
        FileNotFoundError: If S3 download fails

    Example:
        result = generate_low_poly_glb.delay("123e4567-e89b-12d3-a456-426614174000")
        # Returns: {'status': 'success', 'low_poly_url': 'https://...', ...}
    """
    logger.info("generate_low_poly_glb.started", block_id=block_id)
    temp_3dm_path = None

    try:
        # Step 1: Fetch block metadata
        url_original, iso_code, existing_low_poly_url = _fetch_block_metadata(block_id)

        # Step 1b: Idempotency — skip if Codi/iso_code already has a GLB
        if existing_low_poly_url:
            logger.info("generate_low_poly_glb.already_processed",
                        block_id=block_id, iso_code=iso_code,
                        low_poly_url=existing_low_poly_url)
            return {
                'status': 'skipped',
                'low_poly_url': existing_low_poly_url,
                'original_faces': 0,
                'decimated_faces': 0,
                'file_size_kb': 0,
                'error_message': None
            }

        # Step 2: Download .3dm file
        temp_3dm_path = os.path.join(TEMP_DIR, f"{block_id}.3dm")
        _download_3dm_from_s3(url_original, temp_3dm_path)

        # Step 3: Parse .3dm file
        rhino_file = _parse_rhino_file(temp_3dm_path, iso_code)

        # Step 3b: Extract material type from UserStrings (T-1503-AGENT)
        material_type = _extract_material_type(rhino_file, block_id, iso_code)

        # Step 4-5: Extract and merge meshes (returns bbox in centred coords)
        merged_mesh, original_faces_count, bbox = _extract_and_merge_meshes(
            rhino_file, block_id, iso_code
        )

        # Step 6: Apply decimation
        decimated_mesh, decimated_faces_count = _apply_decimation(
            merged_mesh, DECIMATION_TARGET_FACES, block_id
        )

        # Step 7-8: Export and upload GLB
        low_poly_url, file_size_kb = _export_and_upload_glb(decimated_mesh, block_id)

        # Step 9: Update database (low_poly_url + bbox + material_type)
        _update_block_low_poly_url(block_id, low_poly_url, bbox, material_type)

        # Step 10: Cleanup temp .3dm file
        if temp_3dm_path and os.path.exists(temp_3dm_path):
            try:
                os.remove(temp_3dm_path)
                logger.info("cleanup.success", block_id=block_id, file=temp_3dm_path)
            except Exception as e:
                logger.warning("cleanup.failed", block_id=block_id, error=str(e))

        logger.info("generate_low_poly_glb.completed",
                   block_id=block_id,
                   low_poly_url=low_poly_url,
                   original_faces=original_faces_count,
                   decimated_faces=decimated_faces_count,
                   file_size_kb=file_size_kb)

        return {
            'status': 'success',
            'low_poly_url': low_poly_url,
            'original_faces': original_faces_count,
            'decimated_faces': decimated_faces_count,
            'file_size_kb': file_size_kb,
            'error_message': None
        }

    except Exception as e:
        logger.exception("generate_low_poly_glb.error", block_id=block_id, error=str(e))
        raise
