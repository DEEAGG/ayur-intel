"""AYUR-INTEL — Application configuration.

All settings are loaded from environment variables. No secrets in code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    AYURINTEL_DB_PATH: str = str(PROJECT_ROOT / "data" / "ayur_intel.db")

    # Application Environment
    # Options: 'development', 'production', 'staging', 'test'
    AYURINTEL_ENV: str = "development"
    AYURINTEL_DEBUG: Optional[bool] = None

    # Application Host & Port
    AYURINTEL_HOST: str = "127.0.0.1"
    AYURINTEL_PORT: int = 8000

    # Reverse Proxy & Client-IP Trust Policy
    # Only trust X-Forwarded-For/X-Real-IP if explicitly enabled behind a known reverse proxy
    AYURINTEL_TRUST_PROXY_HEADERS: bool = False
    AYURINTEL_BEHIND_PROXY: bool = False
    AYURINTEL_TRUSTED_PROXIES: str = "127.0.0.1,::1"

    # Authentication
    AYURINTEL_SESSION_SECRET: str = "change-me-in-production"
    AYURINTEL_SESSION_TTL_SECONDS: int = 86400
    AYURINTEL_DEMO_MODE: bool = True
    AYURINTEL_ADMIN_EMAIL: Optional[str] = None
    ADMIN_NOTIFICATION_EMAIL: Optional[str] = None
    AYURINTEL_PRODUCTION_URL: str = "https://ayur-intel.onrender.com/"

    # SMTP Configuration (Optional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "AYUR-INTEL Notifications"

    # Resend Configuration (Optional)
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: Optional[str] = None

    # CORS
    AYURINTEL_CORS_ALLOW_ORIGINS: str = "http://127.0.0.1:8000"

    # Plant Identification (PlantNet)
    AYURINTEL_PLANT_ID_PROVIDER: str = "unconfigured"  # 'plantnet' or 'unconfigured'
    AYURINTEL_PLANTNET_API_KEY: str = ""  # Get free key at https://my.plantnet.org/
    PLANTNET_API_KEY: Optional[str] = None
    AYURINTEL_PLANTNET_PROJECT: str = "all"  # 'all', 'weurope', 'canada', etc.

    @property
    def is_production(self) -> bool:
        """Return True if running in production mode.

        Fail-closed rules:
        1. Explicit AYURINTEL_ENV or ENVIRONMENT is 'production' / 'prod'.
        2. Render cloud deployment detected via RENDER / RENDER_SERVICE_ID.
        3. AYURINTEL_ENV model attribute set to 'production' / 'prod'.
        4. If AYURINTEL_DEBUG is explicitly False, treat as production unless
           an explicit development/test environment is declared.
        """
        explicit_env = os.getenv("AYURINTEL_ENV") or os.getenv("ENVIRONMENT")
        if explicit_env:
            clean_env = explicit_env.strip().lower()
            if clean_env in ("production", "prod"):
                return True
            if clean_env in ("development", "dev", "test", "testing"):
                return False

        if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
            return True

        if getattr(self, "AYURINTEL_ENV", "").strip().lower() in ("production", "prod"):
            return True

        if self.AYURINTEL_DEBUG is False:
            if not explicit_env or explicit_env.strip().lower() not in ("development", "dev", "test", "testing"):
                return True

        return False

    @property
    def effective_debug(self) -> bool:
        """Effective debug setting.

        Guarantees that production will NOT silently run with debug=True.
        """
        if self.AYURINTEL_DEBUG is not None:
            return self.AYURINTEL_DEBUG
        return not self.is_production

    @property
    def should_trust_proxy_headers(self) -> bool:
        """Return True if reverse proxy headers (X-Forwarded-For) should be trusted."""
        return bool(self.AYURINTEL_TRUST_PROXY_HEADERS or self.AYURINTEL_BEHIND_PROXY)

    @property
    def trusted_proxy_hosts(self) -> set[str]:
        """Return set of normalized trusted proxy IP strings."""
        raw = self.AYURINTEL_TRUSTED_PROXIES or ""
        return {ip.strip() for ip in raw.split(",") if ip.strip()}

    @model_validator(mode="after")
    def resolve_defaults(self) -> "Settings":
        """Resolve defaults based on environment mode when omitted."""
        if self.AYURINTEL_DEBUG is None:
            # Production cannot silently run with AYURINTEL_DEBUG=True
            self.AYURINTEL_DEBUG = not self.is_production
        return self

    @property
    def effective_plantnet_api_key(self) -> str:
        key = self.PLANTNET_API_KEY or self.AYURINTEL_PLANTNET_API_KEY or os.getenv("PLANTNET_API_KEY", "") or os.getenv("AYURINTEL_PLANTNET_API_KEY", "") or ""
        return key.strip()

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
