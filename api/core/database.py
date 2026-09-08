import os
import logging
from sqlalchemy import create_engine

logger = logging.getLogger("ayur_intel.database")

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # PostgreSQL with asyncpg driver
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )
    logger.info("🔗 Using PostgreSQL (Production)")
else:
    from api.core.config import settings
    engine = create_engine(
        f"sqlite:///{settings.AYURINTEL_DB_PATH}",
        connect_args={"check_same_thread": False}
    )
    logger.info("🔗 Using SQLite (Development)")