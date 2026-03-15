"""
Health check endpoint for Celery connectivity.

This endpoint verifies that the backend can connect to Redis and send tasks.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from infra.celery_client import get_celery_client
from constants import TASK_REGISTER_3DM_BLOCKS
import structlog

router = APIRouter()
logger = structlog.get_logger()


class CeleryHealthResponse(BaseModel):
    """Response model for Celery health check"""
    celery_configured: bool
    broker_url: str
    can_send_task: bool
    error: str | None = None


@router.get("/celery-health", response_model=CeleryHealthResponse)
async def check_celery_health() -> CeleryHealthResponse:
    """
    Check if backend can connect to Celery/Redis.
    
    Returns:
        CeleryHealthResponse: Status of Celery connectivity
    """
    try:
        celery = get_celery_client()
        broker_url = celery.conf.broker_url
        
        # Mask password in URL for security
        masked_url = broker_url
        if "@" in broker_url and ":" in broker_url:
            parts = broker_url.split("@")
            if len(parts) == 2:
                prefix = parts[0].split(":")[0]  # redis://
                suffix = parts[1]  # redis.railway.internal:6379/0
                masked_url = f"{prefix}://:****@{suffix}"
        
        logger.info("celery_health_check.broker_url", url=masked_url)
        
        # Try to send a dummy task
        try:
            result = celery.send_task(
                "agent.health_check",
                args=[],
                countdown=0
            )
            logger.info("celery_health_check.task_sent", task_id=result.id)
            
            return CeleryHealthResponse(
                celery_configured=True,
                broker_url=masked_url,
                can_send_task=True,
                error=None
            )
        except Exception as send_error:
            logger.error("celery_health_check.send_failed", error=str(send_error))
            return CeleryHealthResponse(
                celery_configured=True,
                broker_url=masked_url,
                can_send_task=False,
                error=f"Cannot send task: {str(send_error)}"
            )
            
    except Exception as e:
        logger.error("celery_health_check.failed", error=str(e))
        return CeleryHealthResponse(
            celery_configured=False,
            broker_url="ERROR",
            can_send_task=False,
            error=str(e)
        )
