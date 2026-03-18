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

        SECURITY FIX: Always prioritize REDIS_URL even if CELERY_BROKER_URL exists
        with Railway template placeholders like ${REDIS_PASSWORD}
        """
        import re

        # Ignore Railway template variables that contain ${...} placeholders (not expanded)
        if self.CELERY_BROKER_URL and '${' in self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = None  # Force manual construction

        # Priority 1: Use Railway's auto-injected REDIS_URL (overrides any existing value)
        redis_url = os.getenv("REDIS_URL")
        # Ignore if it's a template
        if redis_url and '${' not in redis_url:
            # Railway Redis doesn't use ACL usernames, remove 'default:' if present
            # Pattern: redis://default:password@ → redis://:password@
            cleaned_url = re.sub(r'redis://default:', 'redis://:', redis_url)
            self.CELERY_BROKER_URL = cleaned_url
            self.CELERY_RESULT_BACKEND = cleaned_url
            return self

        # Priority 2: Use Railway's alternative REDIS_PRIVATE_URL
        redis_private_url = os.getenv("REDIS_PRIVATE_URL")
        if redis_private_url and '${' not in redis_private_url:
            cleaned_url = re.sub(r'redis://default:', 'redis://:', redis_private_url)
            self.CELERY_BROKER_URL = cleaned_url
            self.CELERY_RESULT_BACKEND = cleaned_url
            return self

        # Priority 3: Manual construction (Docker local) - only if no Railway vars
        if not self.CELERY_BROKER_URL:
            redis_password = os.getenv("REDIS_PASSWORD", "")
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = os.getenv("REDIS_PORT", "6379")
            redis_db = os.getenv("REDIS_DB", "0")

            # URL-encode password to handle special characters (@, #, /, etc.)
            if redis_password:
                encoded_password = quote_plus(redis_password)
                # Railway Redis doesn't use ACL usernames, only password
                # Format: redis://:password@host:port/db (note the colon before password)
                url = f"redis://:{encoded_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                # No password (development/testing)
                url = f"redis://{redis_host}:{redis_port}/{redis_db}"

            self.CELERY_BROKER_URL = url
            self.CELERY_RESULT_BACKEND = url

        return self  # CRITICAL: Pydantic model_validator must always return self

# Instantiate settings
settings = Settings()
