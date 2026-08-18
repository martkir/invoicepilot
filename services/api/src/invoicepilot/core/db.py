"""Database engine and session handling.

The engine is created lazily so importing this module (and therefore the CLI)
does not require DATABASE_URL to be set.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from invoicepilot.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set — check your .env file")
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope around a series of operations."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
