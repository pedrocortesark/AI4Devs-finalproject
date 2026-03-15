"""
Upload service - Business logic for file upload operations.

This module contains the core business logic for handling file uploads,
separate from the API routing layer to follow Clean Architecture principles.
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple
from supabase import Client
import structlog

from constants import (
    STORAGE_BUCKET_RAW_UPLOADS,
    STORAGE_UPLOAD_PATH_PREFIX,
    EVENT_TYPE_UPLOAD_CONFIRMED,
    TABLE_EVENTS,
    TASK_REGISTER_3DM_BLOCKS,
)

logger = structlog.get_logger()

# Rhino 3DM file signatures for content validation (magic bytes)
# These signatures identify legitimate Rhino 3D model files
RHINO_3DM_MAGIC_BYTES = [
    b'3D Geometry File Format',  # Rhino 3DM v4+
    b'\x3d\x3d\x3d\x3d\x3d\x3d',  # Rhino 3DM v1-3 (six equal signs)
]


class UploadService:
    """
    Service class for handling file upload operations.

    This class encapsulates all business logic related to file uploads,
    including storage verification and event creation.
    """

    def __init__(self, supabase_client: Client, celery_client=None):
        """
        Initialize the upload service.

        Args:
            supabase_client: Configured Supabase client instance
            celery_client: Optional Celery client for enqueuing tasks
        """
        self.supabase = supabase_client
        self.celery = celery_client

    def _validate_3dm_magic_bytes(self, file_content: bytes) -> bool:
        """
        Validate .3dm file by checking magic bytes (file signature).

        This prevents malware injection attacks where executables are renamed
        to .3dm extensions. We verify the file has a legitimate Rhino 3DM
        binary signature.

        Args:
            file_content: First 512+ bytes of the uploaded file

        Returns:
            True if file has valid Rhino 3DM signature, False otherwise

        References:
            - OWASP: A03:2021 – Injection
            - CVE-2022-XXXXX: File upload bypass vulnerabilities
        """
        return any(file_content.startswith(magic) for magic in RHINO_3DM_MAGIC_BYTES)

    def generate_presigned_url(self, file_id: str, filename: str) -> Tuple[str, str]:
        """
        Generate a signed upload URL for Supabase Storage.

        Args:
            file_id: UUID identifying the upload
            filename: Original filename

        Returns:
            Tuple of (signed_url, file_key)
        """
        file_key = f"{STORAGE_UPLOAD_PATH_PREFIX}/{file_id}/{filename}"
        result = self.supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).create_signed_upload_url(file_key)
        return result["signed_url"], file_key

    def verify_file_exists_in_storage(self, file_key: str) -> bool:
        """
        Verify that a file exists in Supabase Storage.

        Args:
            file_key: The S3 object key (path) of the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            # Extract directory path and filename
            if '/' in file_key:
                path = file_key.rsplit('/', 1)[0]
                file_name = file_key.split('/')[-1]
            else:
                path = ''
                file_name = file_key

            # List files in the directory
            files = self.supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).list(path=path)

            # Check if our file is in the list
            return any(f.get('name') == file_name for f in files)
        except Exception:
            # Any error means file not accessible
            return False

    def create_upload_event(
        self,
        file_id: str,
        file_key: str
    ) -> str:
        """
        Create an event record for a confirmed upload.

        Args:
            file_id: UUID of the uploaded file
            file_key: S3 object key where file was uploaded

        Returns:
            str: UUID of the created event

        Raises:
            Exception: If event creation fails
        """
        event_id = str(uuid.uuid4())
        event_data = {
            "id": event_id,
            "file_id": file_id,
            "event_type": EVENT_TYPE_UPLOAD_CONFIRMED,
            "metadata": {
                "file_key": file_key,
                "confirmed_at": datetime.utcnow().isoformat()
            },
            "created_at": datetime.utcnow().isoformat()
        }

        result = self.supabase.table(TABLE_EVENTS).insert(event_data).execute()

        if not result.data:
            raise Exception("Failed to create event record - no data returned")

        return event_id

    def enqueue_register_blocks(self, file_key: str) -> str:
        """
        Send a Celery task to parse the .3dm file and register one block
        per InstanceDefinition found inside it.

        Args:
            file_key: S3 object key of the uploaded .3dm file

        Returns:
            str: Celery task ID

        Raises:
            RuntimeError: If no celery client is configured
        """
        if self.celery is None:
            raise RuntimeError("Celery client not configured")

        result = self.celery.send_task(
            TASK_REGISTER_3DM_BLOCKS,
            args=[file_key]
        )
        return result.id

    def confirm_upload(
        self,
        file_id: str,
        file_key: str
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Confirm a completed file upload.

        This method orchestrates the full confirmation process:
        1. Verify file exists in storage
        2. Validate file content (magic bytes) to prevent malware injection
        3. Create event record in database
        4. Enqueue register_3dm_blocks task (creates N blocks, one per InstanceDefinition)

        Note: Block creation is now handled asynchronously by the agent worker,
        which parses the .3dm file and creates one block per InstanceDefinition.
        This replaces the old approach of creating a single PENDING block here.

        Args:
            file_id: UUID of the uploaded file
            file_key: S3 object key where file was uploaded

        Returns:
            Tuple of (success, event_id, task_id, error_message)
        """
        # Step 1: Verify file exists
        logger.info("confirm_upload.started", file_id=file_id, file_key=file_key)
        
        if not self.verify_file_exists_in_storage(file_key):
            logger.error("confirm_upload.file_not_found", file_key=file_key)
            return False, None, None, f"File not found in storage: {file_key}"

        logger.info("confirm_upload.file_verified", file_key=file_key)
        
        # Step 2: Validate file content (magic bytes) - SECURITY CRITICAL
        # Download file to check file signature (Supabase returns full file)
        logger.info("confirm_upload.downloading_file", file_key=file_key)
        try:
            file_content = self.supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).download(file_key)
            logger.info("confirm_upload.file_downloaded", file_key=file_key, size_bytes=len(file_content))

            # Check if file has valid Rhino 3DM signature (first 512 bytes)
            if not self._validate_3dm_magic_bytes(file_content[:512]):
                # SECURITY: Delete malicious file immediately
                logger.warning(
                    "magic_bytes_validation.failed",
                    file_key=file_key,
                    file_id=file_id,
                    reason="Invalid .3dm file signature"
                )
                try:
                    self.supabase.storage.from_(STORAGE_BUCKET_RAW_UPLOADS).remove([file_key])
                    logger.info("malicious_file.deleted", file_key=file_key)
                except Exception as delete_error:
                    logger.error("malicious_file.delete_failed", file_key=file_key, error=str(delete_error))

                return False, None, None, "Invalid .3dm file format - content validation failed"
            
            logger.info("confirm_upload.magic_bytes_validated", file_key=file_key)

        except Exception as e:
            logger.error("magic_bytes_validation.error", file_key=file_key, error=str(e))
            return False, None, None, f"File content validation error: {str(e)}"

        # Step 3: Create event record
        logger.info("confirm_upload.creating_event", file_id=file_id)
        try:
            event_id = self.create_upload_event(file_id, file_key)
            logger.info("confirm_upload.event_created", event_id=event_id)
        except Exception as e:
            logger.error("confirm_upload.event_creation_failed", error=str(e))
            return False, None, None, f"Database error: {str(e)}"

        # Step 4: Enqueue register_3dm_blocks (parses .3dm → N blocks, one per InstanceDefinition)
        logger.info("confirm_upload.enqueuing_task", file_key=file_key, celery_configured=self.celery is not None)
        try:
            task_id = self.enqueue_register_blocks(file_key)
            logger.info("confirm_upload.task_enqueued", task_id=task_id, file_key=file_key)
        except Exception as e:
            logger.error("confirm_upload.enqueue_failed", error=str(e), error_type=type(e).__name__)
            return True, event_id, None, f"Enqueue error: {str(e)}"

        logger.info("confirm_upload.completed", event_id=event_id, task_id=task_id)
        return True, event_id, task_id, None
