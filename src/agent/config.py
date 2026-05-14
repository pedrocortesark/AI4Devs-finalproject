"""
Configuration module for SF-PM Agent.

Uses pydantic-settings for environment-based configuration management,
mirroring the backend pattern for consistency.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional
import os
from urllib.parse import quote_plus


class Settings(BaseSettings):
    """
    Agent-specific configuration.
    Mirrors backend pattern for consistency.
    """
    # Celery - Built dynamically with URL encoding in validator
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Database (for direct writes)
    DATABASE_URL: str = "postgresql://user:password@db:5432/sfpm_db"

    # Supabase (for S3 downloads)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # File Processing Limits
    MAX_FILE_SIZE_MB: int = 500
    TEMP_DIR: str = "/tmp/sf-pm-agent"

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
        
        RAILWAY FIX: Ignores template variables like ${REDIS_PASSWORD} and removes
        'default:' username (Railway Redis uses password-only authentication).
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
        
        return self


# Instantiate settings
settings = Settings()
