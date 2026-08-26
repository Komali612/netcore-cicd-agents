"""Engine + session lifecycle — the only module that opens connections.

Callers use ``session_scope()`` and never touch the engine directly. The
engine is a lazily-built singleton keyed off ``config.load_config()``; tests
build their own throwaway engine with ``make_engine('sqlite://...')`` and bind
it via ``configure(engine)``.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import config as db_config
from .base import Base

log = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """Build an engine with pooling defaults that survive MySQL's idle timeout.
    SQLite (tests) gets a shared static pool so an in-memory DB persists across
    sessions within a process."""
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # SQLite ignores FKs unless asked; turn them on so tests exercise them.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _rec):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine

    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,   # drop dead connections instead of erroring
        pool_recycle=1800,    # recycle before MySQL's default wait_timeout
        future=True,
    )


def configure(engine: Engine) -> None:
    """Bind the module to a specific engine (used by tests and db_init)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_engine() -> Optional[Engine]:
    """Return the shared engine, building it from env config on first use.
    Returns None when the DB layer is not configured (persistence disabled)."""
    global _engine
    if _engine is not None:
        return _engine
    cfg = db_config.load_config()
    if not cfg.enabled():
        return None
    configure(make_engine(cfg.url, echo=cfg.echo))
    return _engine


def enabled() -> bool:
    return get_engine() is not None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, roll back on error, always close."""
    if _SessionLocal is None and get_engine() is None:
        raise RuntimeError("Database is not configured; check DATABASE_URL / DB_* env.")
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables (dev/bootstrap). Production should use Alembic migrations;
    see db/README.md."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Database is not configured; nothing to initialise.")
    # Import models for their side effect of registering on Base.metadata.
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    log.info("Database schema ensured (%d tables).", len(Base.metadata.tables))
