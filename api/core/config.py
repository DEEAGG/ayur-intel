"""AYUR-INTEL — Application configuration.

All settings are loaded from environment variables. No secrets in code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    AYURINTEL_DB_PATH: str = str(PROJECT_ROOT / "data" / "ayur_intel.db")

    # Application
    AYURINTEL_HOST: str = "127.0.0.1"
    AYURINTEL_PORT: int = 8000
    AYURINTEL_DEBUG: bool = True

    # Authentication
    AYURINTEL_SESSION_SECRET: str = "change-me-in-production"
    AYURINTEL_SESSION_TTL_SECONDS: int = 86400
    AYURINTEL_DEMO_MODE: bool = True

    # CORS
    AYURINTEL_CORS_ALLOW_ORIGINS: str = "http://127.0.0.1:8000"

    # Plant Identification (PlantNet)
    AYURINTEL_PLANT_ID_PROVIDER: str = "unconfigured"  # 'plantnet' or 'unconfigured'
    AYURINTEL_PLANTNET_API_KEY: str = ""  # Get free key at https://my.plantnet.org/
    AYURINTEL_PLANTNET_PROJECT: str = "all"  # 'all', 'weurope', 'canada', etc.

    # AI Settings
    GEMINI_API_KEY: Optional[str] = None
    AYURINTEL_GEMINI_API_KEY: Optional[str] = None

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton — import this, don't create a new Settings each time.
settings = Settings()

# Ensure data directory exists
(Path(settings.AYURINTEL_DB_PATH).parent).mkdir(parents=True, exist_ok=True)
