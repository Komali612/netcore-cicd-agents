"""Database configuration — one place that owns the connection string.

MySQL today, Postgres (or anything SQLAlchemy speaks) tomorrow: nothing else in
the codebase names a driver or a host. Point everything through ``DATABASE_URL``,
or let this build one from discrete ``DB_*`` parts. If neither is configured the
whole DB layer is a no-op (``enabled()`` is False) so the agent still runs
exactly as before — persistence is additive, never required.

Env vars
--------
    DATABASE_URL     full SQLAlchemy URL; wins if set
                     e.g. mysql+pymysql://user:pass@host:3306/netcore_cicd
                     e.g. postgresql+psycopg://user:pass@host:5432/netcore_cicd
  ...or the discrete parts (used only when DATABASE_URL is unset):
    DB_DRIVER        default 'mysql+pymysql'  (swap to 'postgresql+psycopg')
    DB_HOST          default '127.0.0.1'
    DB_PORT          default '3306'
    DB_USER          default 'root'
    DB_PASSWORD      default ''
    DB_NAME          e.g. 'netcore_cicd'   (required to enable via parts)
    DB_ECHO          '1' to log SQL
    DB_ENCRYPTION_KEY  Fernet key for encrypting secret columns (see crypto.py)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class DBConfig:
    url: str | None
    echo: bool

    def enabled(self) -> bool:
        """True when a usable connection string is configured."""
        return bool(self.url)


def _build_url_from_parts() -> str | None:
    """Assemble a SQLAlchemy URL from DB_* parts. Returns None if no DB_NAME —
    without a database name there is nothing to connect to, so we stay disabled."""
    name = os.getenv("DB_NAME")
    if not name:
        return None
    driver = os.getenv("DB_DRIVER", "mysql+pymysql")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    auth = quote_plus(user)
    if password:
        auth = f"{auth}:{quote_plus(password)}"
    return f"{driver}://{auth}@{host}:{port}/{name}"


def load_config() -> DBConfig:
    """Read the environment fresh each call (tests and callers can rebind env)."""
    url = os.getenv("DATABASE_URL") or _build_url_from_parts()
    echo = os.getenv("DB_ECHO", "").lower() in {"1", "true", "yes"}
    return DBConfig(url=url, echo=echo)
