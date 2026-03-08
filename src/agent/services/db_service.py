"""
Database Service

Handles database operations for agent worker.
Updates block status and saves validation reports.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog
from infra.supabase_client import get_supabase_client

logger = structlog.get_logger()


class DBService:
    """
    Service for database operations during file validation.

    Handles block status updates and validation report persistence.
    """

    def __init__(self):
        """Initialize service with Supabase client."""
        self.supabase = get_supabase_client()

    def update_block_status(self, part_id: str, status: str) -> bool:
        """
        Update block status in database.

        Args:
            part_id: Block ID
            status: New status value (e.g., 'processing', 'validated', 'error_processing')

        Returns:
            True if update succeeded, False otherwise
        """
        logger.info("db_service.update_block_status", part_id=part_id, status=status)

        try:
            result = self.supabase.table("blocks").update({
                "status": status
            }).eq("id", part_id).execute()

            if result.data:
                logger.info("db_service.update_block_status.success", part_id=part_id, status=status)
                return True
            else:
                logger.error("db_service.update_block_status.no_rows_affected", part_id=part_id)
                return False

        except Exception as e:
            logger.exception("db_service.update_block_status.error", part_id=part_id, error=str(e))
            return False

    def save_validation_report(
        self,
        part_id: str,
        is_valid: bool,
        errors: list,
        metadata: Dict[str, Any],
        validated_by: str
    ) -> bool:
        """
        Save validation report to database.

        Args:
            part_id: Block ID
            is_valid: Whether validation passed
            errors: List of validation errors
            metadata: Extracted metadata
            validated_by: Worker identifier

        Returns:
            True if save succeeded, False otherwise
        """
        logger.info("db_service.save_validation_report", part_id=part_id, is_valid=is_valid)

        try:
            # Build validation report JSON
            validation_report = {
                "is_valid": is_valid,
                "errors": errors,
                "metadata": metadata,
                "validated_at": datetime.utcnow().isoformat() + "Z",
                "validated_by": validated_by
            }

            # Update blocks table
            result = self.supabase.table("blocks").update({
                "validation_report": validation_report
            }).eq("id", part_id).execute()

            if result.data:
                logger.info("db_service.save_validation_report.success", part_id=part_id)
                return True
            else:
                logger.error("db_service.save_validation_report.no_rows_affected", part_id=part_id)
                return False

        except Exception as e:
            logger.exception("db_service.save_validation_report.error", part_id=part_id, error=str(e))
            return False

    def register_blocks_for_iso_codes(self, iso_codes: List[str], file_key: str) -> List[Dict[str, str]]:
        """
        Register blocks for InstanceDefinition iso_codes found in a .3dm file.

        Idempotent: iso_codes that already have a block record are skipped.
        Uses the UNIQUE constraint on iso_code to avoid duplicates.

        Args:
            iso_codes: List of InstanceDefinition.Name values from the .3dm file
            file_key: S3 object key of the source .3dm file (stored as url_original)

        Returns:
            List of {id, iso_code} dicts for newly created blocks only.
            Returns empty list if all iso_codes already existed.
        """
        logger.info("db_service.register_blocks_for_iso_codes", iso_code_count=len(iso_codes))

        try:
            # 1. Find which iso_codes already have a block
            existing = self.supabase.table("blocks").select("iso_code").in_("iso_code", iso_codes).execute()
            existing_codes = {row["iso_code"] for row in (existing.data or [])}

            # 2. Only insert the new ones
            new_iso_codes = [code for code in iso_codes if code not in existing_codes]

            if not new_iso_codes:
                logger.info("db_service.register_blocks_for_iso_codes.all_exist",
                            skipped=len(existing_codes))
                return []

            # 3. Batch insert new blocks
            rows = [
                {
                    "iso_code": code,
                    "tipologia": "pending",
                    "url_original": file_key,
                }
                for code in new_iso_codes
            ]
            result = self.supabase.table("blocks").insert(rows).execute()

            new_blocks = [{"id": row["id"], "iso_code": row["iso_code"]} for row in result.data]
            logger.info("db_service.register_blocks_for_iso_codes.success",
                        new_count=len(new_blocks), skipped_count=len(existing_codes))
            return new_blocks

        except Exception as e:
            logger.exception("db_service.register_blocks_for_iso_codes.error", error=str(e))
            raise

    def get_block(self, part_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch block record from database.

        Args:
            part_id: Block ID

        Returns:
            Block record as dict, or None if not found
        """
        logger.info("db_service.get_block", part_id=part_id)

        try:
            result = self.supabase.table("blocks").select("*").eq("id", part_id).execute()

            if result.data and len(result.data) > 0:
                logger.info("db_service.get_block.success", part_id=part_id)
                return result.data[0]
            else:
                logger.warning("db_service.get_block.not_found", part_id=part_id)
                return None

        except Exception as e:
            logger.exception("db_service.get_block.error", part_id=part_id, error=str(e))
            return None
