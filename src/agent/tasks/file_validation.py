"""
Celery task definitions for SF-PM Agent.

This module contains all async tasks executed by the Celery worker,
including health checks and file validation workflows.
"""

# Import from celery_app in same PYTHONPATH (/app)
from celery_app import celery_app
from constants import (
    TASK_HEALTH_CHECK,
    TASK_VALIDATE_FILE,
    TASK_REGISTER_3DM_BLOCKS,
    TASK_GENERATE_LOW_POLY_GLB,
    TASK_MAX_RETRIES,
    TASK_RETRY_DELAY_SECONDS,
)

import structlog
from datetime import datetime

logger = structlog.get_logger()


def _is_transient_error(exc: Exception, error_msg: str = None) -> bool:
    """Determine if error is transient (should retry) or permanent.
    
    Checks both exception type and error message for transient patterns.
    
    Args:
        exc: Exception to classify
        error_msg: Optional explicit error message (overrides exc message)
        
    Returns:
        bool: True if error is transient (should retry), False if permanent
    """
    transient_patterns = [
        "timeout", "timed out", "connection", "network",
        "rate limit", "503", "502", "504", "temporary",
        "unavailable", "redis", "could not connect"
    ]
    check_msg = error_msg if error_msg else str(exc)
    return any(pattern in check_msg.lower() for pattern in transient_patterns)


@celery_app.task(
    name=TASK_HEALTH_CHECK,
    bind=True,
    max_retries=0
)
def health_check(self):
    """
    Dummy task for infrastructure validation.

    Returns worker metadata to confirm Celery is operational.
    Used by integration tests to verify worker connectivity.

    Returns:
        dict: Status metadata including worker_id, hostname, timestamp
    """
    return {
        "status": "healthy",
        "worker_id": self.request.id,
        "hostname": self.request.hostname,
        "timestamp": datetime.utcnow().isoformat() if not self.request.eta else str(self.request.eta)
    }


@celery_app.task(
    name=TASK_VALIDATE_FILE,
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_DELAY_SECONDS
)
def validate_file(self, part_id: str, s3_key: str):
    """
    Validate .3dm file from S3.

    This task:
    1. Updates block status to 'processing'
    2. Downloads .3dm from S3 to /tmp
    3. Parses with rhino3dm.File3dm.Read()
    4. Extracts layer metadata
    5. Saves validation report to database
    6. Updates block status to 'validated' or 'error_processing'
    7. Cleans up temporary files

    Args:
        part_id: UUID of the part in database
        s3_key: S3 object key for the .3dm file

    Returns:
        dict: Result with success status and metadata
    """
    logger.info("validate_file.started", part_id=part_id, s3_key=s3_key)

    # Import services
    try:
        from services.file_download_service import FileDownloadService
        from services.rhino_parser_service import RhinoParserService
        from services.db_service import DBService
    except ModuleNotFoundError:
        from src.agent.services.file_download_service import FileDownloadService
        from src.agent.services.rhino_parser_service import RhinoParserService
        from src.agent.services.db_service import DBService

    # Initialize services
    file_download = FileDownloadService()
    rhino_parser = RhinoParserService()
    db_service = DBService()

    # Worker identifier for audit trail
    worker_id = self.request.hostname or "unknown-worker"

    try:
        # Step 1: Update status to processing
        db_service.update_block_status(part_id, "processing")

        # Step 2: Download file from S3
        success, local_path, download_error = file_download.download_from_s3(s3_key)

        if not success:
            logger.error("validate_file.download_failed", part_id=part_id, error=download_error)

            # Check if error is transient (network/S3 issue) or permanent (not found)
            if _is_transient_error(Exception(download_error), download_error):
                # Exponential backoff: 30s → 60s → 120s → 240s → 480s
                countdown = TASK_RETRY_DELAY_SECONDS * (2 ** self.request.retries)
                
                logger.warning(
                    "validate_file.download_retry_scheduled",
                    part_id=part_id,
                    retry_count=self.request.retries + 1,
                    countdown_seconds=countdown
                )
                
                # Raise retry exception (Celery will automatically retry)
                raise self.retry(exc=Exception(download_error), countdown=countdown, max_retries=TASK_MAX_RETRIES)
            
            # Permanent error: save report and update status
            db_service.save_validation_report(
                part_id=part_id,
                is_valid=False,
                errors=[{
                    "category": "io",
                    "target": s3_key,
                    "message": download_error
                }],
                metadata={},
                validated_by=worker_id
            )

            db_service.update_block_status(part_id, "error_processing")

            return {
                "success": False,
                "part_id": part_id,
                "error": download_error
            }

        # Step 3: Parse .3dm file
        parse_result = rhino_parser.parse_file(local_path)

        # Step 4: Cleanup temp file
        file_download.cleanup_temp_file(local_path)

        # Step 5: Process results
        if not parse_result.success:
            logger.error("validate_file.parse_failed", part_id=part_id, error=parse_result.error_message)

            # Parse errors are typically permanent (corrupted file, invalid format)
            # But check for transient patterns just in case (memory issues, etc.)
            if _is_transient_error(Exception(parse_result.error_message), parse_result.error_message):
                countdown = TASK_RETRY_DELAY_SECONDS * (2 ** self.request.retries)
                
                logger.warning(
                    "validate_file.parse_retry_scheduled",
                    part_id=part_id,
                    retry_count=self.request.retries + 1,
                    countdown_seconds=countdown
                )
                
                raise self.retry(exc=Exception(parse_result.error_message), countdown=countdown, max_retries=TASK_MAX_RETRIES)
            
            # Permanent parse error: save report and update status
            db_service.save_validation_report(
                part_id=part_id,
                is_valid=False,
                errors=[{
                    "category": "io",
                    "target": s3_key,
                    "message": parse_result.error_message
                }],
                metadata={},
                validated_by=worker_id
            )

            db_service.update_block_status(part_id, "error_processing")

            return {
                "success": False,
                "part_id": part_id,
                "error": parse_result.error_message
            }

        # Step 6: Build metadata from parsed layers
        layers_metadata = [
            {
                "name": layer.name,
                "index": layer.index,
                "object_count": layer.object_count,
                "color": layer.color,
                "is_visible": layer.is_visible
            }
            for layer in parse_result.layers
        ]

        metadata = {
            "layers": layers_metadata,
            **parse_result.file_metadata
        }

        # Step 7: Save validation report (no errors for MVP - T-026/T-027 add validation)
        db_service.save_validation_report(
            part_id=part_id,
            is_valid=True,
            errors=[],
            metadata=metadata,
            validated_by=worker_id
        )

        # Step 8: Update status to validated
        db_service.update_block_status(part_id, "validated")

        # Step 9: Enqueue geometry processing to generate low-poly GLB
        celery_app.send_task(TASK_GENERATE_LOW_POLY_GLB, args=[part_id])
        logger.info("validate_file.geometry_task_enqueued", part_id=part_id)

        logger.info(
            "validate_file.success",
            part_id=part_id,
            layer_count=len(parse_result.layers)
        )

        return {
            "success": True,
            "part_id": part_id,
            "layer_count": len(parse_result.layers),
            "metadata": metadata
        }

    except Exception as e:
        logger.exception("validate_file.unexpected_error", part_id=part_id, error=str(e), retry_count=self.request.retries)

        # Check if error is transient
        if _is_transient_error(e):
            countdown = TASK_RETRY_DELAY_SECONDS * (2 ** self.request.retries)
            
            logger.warning(
                "validate_file.retry_scheduled",
                part_id=part_id,
                retry_count=self.request.retries + 1,
                countdown_seconds=countdown,
                error_type=type(e).__name__
            )
            
            raise self.retry(exc=e, countdown=countdown, max_retries=TASK_MAX_RETRIES)
        
        # Permanent error: save report and update status
        try:
            db_service.save_validation_report(
                part_id=part_id,
                is_valid=False,
                errors=[{
                    "category": "io",
                    "target": s3_key,
                    "message": f"Unexpected error: {str(e)}"
                }],
                metadata={},
                validated_by=worker_id
            )

            db_service.update_block_status(part_id, "error_processing")
        except Exception as db_error:
            logger.exception("validate_file.db_error_during_error_handling", error=str(db_error))

        return {
            "success": False,
            "part_id": part_id,
            "error": str(e)
        }


@celery_app.task(
    name=TASK_REGISTER_3DM_BLOCKS,
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_DELAY_SECONDS
)
def register_3dm_blocks(self, file_key: str):
    """
    Parse a .3dm file and register one block per InstanceDefinition.

    Replaces the old "create one PENDING block per upload" approach.
    A single .3dm file contains N InstanceDefinitions (Codis), each of
    which must become an independent block in the database.

    This task is idempotent: re-uploading the same file skips iso_codes
    that already exist (leverages the UNIQUE constraint on blocks.iso_code).

    Workflow:
    1. Download .3dm file from S3
    2. Enumerate InstanceDefinitions (each .Name is an iso_code / Codi)
    3. Register new blocks in DB (skip existing ones)
    4. Enqueue validate_file for each newly created block
    5. Clean up temp file

    Args:
        file_key: S3 object key of the uploaded .3dm file

    Returns:
        dict: {success, registered, skipped, block_ids}
    """
    logger.info("register_3dm_blocks.started", file_key=file_key)

    # Import services
    try:
        from services.file_download_service import FileDownloadService
        from services.db_service import DBService
    except ModuleNotFoundError:
        from src.agent.services.file_download_service import FileDownloadService
        from src.agent.services.db_service import DBService

    import rhino3dm

    file_download = FileDownloadService()
    db_service = DBService()

    # Step 1: Download .3dm file from S3
    success, local_path, download_error = file_download.download_from_s3(file_key)
    if not success:
        logger.error("register_3dm_blocks.download_failed", file_key=file_key, error=download_error)
        return {"success": False, "error": download_error}

    try:
        # Step 2: Open file and enumerate InstanceDefinitions
        file3dm = rhino3dm.File3dm.Read(local_path)
        if file3dm is None:
            raise ValueError(f"rhino3dm could not open file: {file_key}")

        iso_codes = [idef.Name for idef in file3dm.InstanceDefinitions]
        logger.info("register_3dm_blocks.idefs_found",
                    file_key=file_key,
                    count=len(iso_codes),
                    iso_codes=iso_codes)

        if not iso_codes:
            logger.warning("register_3dm_blocks.no_idefs", file_key=file_key)
            return {"success": True, "registered": 0, "skipped": 0, "block_ids": []}

        # Step 3: Register blocks (idempotent — skips existing iso_codes)
        new_blocks = db_service.register_blocks_for_iso_codes(iso_codes, file_key)

        # Step 4: Enqueue validate_file for each newly created block
        for block in new_blocks:
            celery_app.send_task(TASK_VALIDATE_FILE, args=[block["id"], file_key])
            logger.info("register_3dm_blocks.validate_enqueued",
                        block_id=block["id"],
                        iso_code=block["iso_code"])

        skipped = len(iso_codes) - len(new_blocks)
        logger.info("register_3dm_blocks.success",
                    file_key=file_key,
                    registered=len(new_blocks),
                    skipped=skipped)

        return {
            "success": True,
            "registered": len(new_blocks),
            "skipped": skipped,
            "block_ids": [b["id"] for b in new_blocks],
        }

    except Exception as e:
        logger.exception("register_3dm_blocks.error", file_key=file_key, error=str(e))
        return {"success": False, "error": str(e)}

    finally:
        file_download.cleanup_temp_file(local_path)
