"""
Celery task definitions for SF-PM Agent.

This module contains all async tasks executed by the Celery worker,
including health checks and file validation workflows.
"""

# Conditional imports: src.agent.* preferred (tests + dev), fallback to direct (production)
try:
    from src.agent.celery_app import celery_app
    from src.agent.constants import (
        TASK_HEALTH_CHECK,
        TASK_VALIDATE_FILE,
        TASK_REGISTER_3DM_BLOCKS,
        TASK_GENERATE_LOW_POLY_GLB,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
    )
    from src.agent.services.file_download_service import FileDownloadService
    from src.agent.services.db_service import DBService
    from src.agent.services.rhino_parser_service import RhinoParserService
except ImportError:
    from celery_app import celery_app
    from constants import (
        TASK_HEALTH_CHECK,
        TASK_VALIDATE_FILE,
        TASK_REGISTER_3DM_BLOCKS,
        TASK_GENERATE_LOW_POLY_GLB,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
    )
    from services.file_download_service import FileDownloadService
    from services.db_service import DBService
    from services.rhino_parser_service import RhinoParserService

import structlog
from datetime import datetime
import rhino3dm

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


def _normalize_error(err) -> dict:
    """Coerce a graph error (str | pydantic model | dict) into a JSON-safe dict
    with the {category, target, message} shape DBService persists."""
    if isinstance(err, str):
        return {"category": "validation", "target": "", "message": err}
    if hasattr(err, "model_dump"):
        data = err.model_dump()
    elif isinstance(err, dict):
        data = err
    else:
        data = {"message": str(err)}
    return {
        "category": data.get("category", "validation"),
        "target": data.get("target", ""),
        "message": data.get("message", str(data)),
    }


def _collect_graph_errors(final_state) -> list:
    """Flatten nomenclature + geometry + runtime errors from the final
    LangGraph state into a single normalized list for the validation report."""
    collected = []
    for key in ("nomenclature_errors", "geometry_errors", "error_messages"):
        for err in final_state.get(key) or []:
            collected.append(_normalize_error(err))
    return collected


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
def validate_file(self, part_id: str, s3_key: str, iso_code: str = None):
    """
    Validate a .3dm block through the LangGraph "Librarian" pipeline (US-018).

    This task:
    1. Updates block status to 'processing'
    2. Downloads .3dm from S3 to /tmp and parses it with rhino3dm
    3. Pre-loads the parsed geometry into the LangGraph state and runs
       validation_graph (nomenclature + geometry validation + LLM tipologia
       classification with regex fallback)
    4. Maps the final graph state to the validation_report + block status +
       tipologia (persistence keyed by blocks.id via DBService)
    5. Cleans up temporary files

    Args:
        part_id: UUID of the block row in the database (blocks.id)
        s3_key: S3 object key for the uploaded .3dm file (shared by N blocks)
        iso_code: ISO-19650 code of this block (fed to the LLM classifier).
                  Optional for backward compatibility with old enqueues.

    Returns:
        dict: Result with success status and metadata
    """
    logger.info("validate_file.started", part_id=part_id, s3_key=s3_key, iso_code=iso_code)

    # Lazy import of the LangGraph pipeline: deferred to task-execution time so
    # that merely importing this module (e.g. Celery autodiscovery, pytest
    # collection of contract tests) does NOT eagerly compile the graph or pull
    # the graph→nodes→llm_client chain into sys.modules.
    try:
        from src.agent.graph.graph import validation_graph
        from src.agent.graph.state import make_initial_state, ValidationStatus
        from src.agent.graph.nodes import build_initial_geometry_metadata
    except ImportError:
        from graph.graph import validation_graph
        from graph.state import make_initial_state, ValidationStatus
        from graph.nodes import build_initial_geometry_metadata

    # Initialize services
    file_download = FileDownloadService()
    rhino_parser = RhinoParserService()
    db_service = DBService()

    # Worker identifier for audit trail
    worker_id = self.request.hostname or "unknown-worker"

    try:
        # Step 1: Update status to processing
        db_service.update_block_status(part_id, "processing")

        # Step 2: Download file from S3 (pass task_id to avoid race conditions)
        success, local_path, download_error = file_download.download_from_s3(s3_key, task_id=self.request.id)

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

        # Step 3b: Pre-build geometry_metadata from the file ON DISK, before
        # cleanup. This is fed into the LangGraph state so the ExtractGeometry
        # node reuses it instead of re-downloading by the (wrong) {block_id}.3dm
        # key. Only meaningful when the parse succeeded.
        geometry_metadata = None
        if parse_result.success:
            geometry_metadata = build_initial_geometry_metadata(
                local_path, parse_result, iso_code
            )

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

        # Step 6: Run the LangGraph "Librarian" pipeline.
        # We pre-load the parsed geometry so ExtractGeometry reuses it (its
        # idempotency guard) instead of re-downloading by the wrong key.
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

        initial_state = make_initial_state(
            block_id=part_id,
            retry_count=self.request.retries,
        )
        initial_state["geometry_metadata"] = geometry_metadata

        final_state = validation_graph.invoke(initial_state)

        overall_status = final_state.get("overall_status")
        is_valid = overall_status == ValidationStatus.VALIDATED
        semantic = final_state.get("semantic_data") or {}
        classification_method = final_state.get("classification_method")
        errors = _collect_graph_errors(final_state)

        metadata = {
            "layers": layers_metadata,
            **parse_result.file_metadata,
            "geometry": {
                "volume": geometry_metadata.get("volume"),
                "bbox": geometry_metadata.get("bbox"),
                "vertices_count": geometry_metadata.get("vertices_count"),
                "faces_count": geometry_metadata.get("faces_count"),
            },
            "classification": {
                "tipologia": semantic.get("tipologia"),
                "material": semantic.get("material"),
                "confidence": semantic.get("confidence"),
                "reasoning": semantic.get("reasoning"),
                "method": classification_method.value if classification_method else None,
                "circuit_breaker_tripped": final_state.get("circuit_breaker_tripped", False),
            },
            "validation_path": final_state.get("validation_path", []),
        }

        # Step 7: Persist the validation report (keyed by blocks.id)
        db_service.save_validation_report(
            part_id=part_id,
            is_valid=is_valid,
            errors=errors,
            metadata=metadata,
            validated_by=worker_id
        )

        # Step 8: Persist status (+ tipologia when the agent validated the piece)
        db_service.update_block_status(
            part_id, "validated" if is_valid else "error_processing"
        )
        if is_valid and semantic.get("tipologia"):
            db_service.update_block_classification(
                part_id, semantic["tipologia"], semantic.get("material")
            )

        # Step 9: Only generate the low-poly GLB for accepted pieces
        if is_valid:
            celery_app.send_task(TASK_GENERATE_LOW_POLY_GLB, args=[part_id])
            logger.info("validate_file.geometry_task_enqueued", part_id=part_id)

        logger.info(
            "validate_file.completed",
            part_id=part_id,
            is_valid=is_valid,
            overall_status=str(overall_status),
            tipologia=semantic.get("tipologia"),
            classification_method=classification_method.value if classification_method else None,
            layer_count=len(parse_result.layers),
        )

        return {
            "success": is_valid,
            "part_id": part_id,
            "overall_status": str(overall_status),
            "tipologia": semantic.get("tipologia"),
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

        # Step 4: Enqueue validate_file for each newly created block.
        # iso_code is passed so the LangGraph ClassifyTipologia node feeds the
        # real ISO-19650 code to the LLM (block id is an opaque UUID).
        for block in new_blocks:
            celery_app.send_task(
                TASK_VALIDATE_FILE,
                args=[block["id"], file_key, block["iso_code"]],
            )
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
