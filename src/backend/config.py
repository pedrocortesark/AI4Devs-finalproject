from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional
import os
from urllib.parse import quote_plus

class Settings(BaseSettings):
    """
    Project settings and environment variables management.
    Uses pydantic-settings to automatically load vars from .env and environment.
    """
    # Database
    DATABASE_URL: str = "postgresql://user:password@db:5432/sfpm_db"

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # T-1001-INFRA: CloudFront CDN for GLB files
    CDN_BASE_URL: str = "https://tqduceanvyckaztgpcmw.supabase.co/storage/v1/object/public/processed-geometry"
    USE_CDN: bool = False

    # Celery (Task Queue) - Built dynamically with URL encoding in validator
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # App Settings
    PROJECT_NAME: str = "SF-PM"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @model_validator(mode='after')
    def build_redis_urls(self):
        """
        Build Redis URLs after all env vars are loaded.
        Priority: REDIS_URL > REDIS_PRIVATE_URL > Manual construction
        """
        # Only build if not explicitly set via env var
        if not self.CELERY_BROKER_URL:
            # Priority 1: Use Railway's auto-injected REDIS_URL
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                self.CELERY_BROKER_URL = redis_url
                self.CELERY_RESULT_BACKEND = redis_url
                return self
            
            # Priority 2: Use Railway's alternative REDIS_PRIVATE_URL
            redis_private_url = os.getenv("REDIS_PRIVATE_URL")
            if redis_private_url:
                self.CELERY_BROKER_URL = redis_private_url
                self.CELERY_RESULT_BACKEND = redis_private_url
                return self
            
            # Priority 3: Manual construction (Docker local)
            redis_password = os.getenv("REDIS_PASSWORD", "")
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = os.getenv("REDIS_PORT", "6379")
            redis_db = os.getenv("REDIS_DB", "0")
            
            # URL-encode password to handle special characters (@, #, /, etc.)
            if redis_password:
                encoded_password = quote_plus(redis_password)
                url = f"redis://default:{encoded_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                # No password (development/testing)
                url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            
            self.CELERY_BROKER_URL = url
            self.CELERY_RESULT_BACKEND = url
        
        return self

# Instantiate settings
settings = Settings()
