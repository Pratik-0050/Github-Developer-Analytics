"""Database connection, engine configuration, and session dependency."""

import time
from typing import Generator, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base import Base

# Engine configuration depending on DB dialect
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL / other production databases with pooling
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables registered with Base metadata."""
    # Import all models to ensure they are registered with Base.metadata
    import app.models.db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_oauth_columns()


def _ensure_oauth_columns() -> None:
    """Lightweight auto-migration for Step 7 columns on pre-existing DBs.

    create_all() never alters existing tables, so earlier SQLite/Postgres
    files lack github_token_encrypted et al. Add them idempotently.
    """
    from sqlalchemy import inspect

    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            if "users" not in insp.get_table_names():
                return
            existing = {c["name"] for c in insp.get_columns("users")}
            missing_sql = {
                "github_token_encrypted": "ALTER TABLE users ADD COLUMN github_token_encrypted TEXT",
                "token_scope": "ALTER TABLE users ADD COLUMN token_scope VARCHAR(255)",
                "token_obtained_at": "ALTER TABLE users ADD COLUMN token_obtained_at DATETIME",
            }
            for col, ddl in missing_sql.items():
                if col not in existing:
                    try:
                        conn.exec_driver_sql(ddl)
                    except Exception:
                        pass
            conn.commit()
    except Exception:
        pass


def check_db_connection() -> Tuple[bool, float, str]:
    """
    Ping the database to verify connectivity.
    Returns (is_connected, latency_ms, dialect_name).
    """
    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        dialect = engine.dialect.name
        return True, latency_ms, dialect
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, latency_ms, str(exc)
