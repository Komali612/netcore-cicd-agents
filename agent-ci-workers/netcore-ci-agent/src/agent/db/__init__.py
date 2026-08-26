"""Database layer for the netcore CI agent.

Public surface (import from ``agent.db``):
    enabled()                     is persistence configured?
    begin_ci_run / finish_ci_run / fail_ci_run   record a CI run
    init_db()                     create tables (dev/bootstrap)
    session_scope()               transactional session (advanced use)

Design & swap-out notes: see db/README.md.
"""
from __future__ import annotations

from .engine import enabled, init_db, session_scope
from .repository import begin_ci_run, fail_ci_run, finish_ci_run, redact_config

__all__ = [
    "enabled",
    "init_db",
    "session_scope",
    "begin_ci_run",
    "finish_ci_run",
    "fail_ci_run",
    "redact_config",
]
