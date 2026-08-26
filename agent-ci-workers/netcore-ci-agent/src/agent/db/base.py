"""Declarative base, shared mixins, enums, and the encrypted column type.

Everything here is dialect-agnostic on purpose (see db/README.md): generic
column types only, string-backed enums (no native ENUM to ALTER), and a
polymorphic ``ScopedMixin`` for tenant ownership. That keeps MySQL-now /
Postgres-later a config change, not a rewrite.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from . import crypto


class Base(DeclarativeBase):
    """Root of all ORM models."""


class TimestampMixin:
    """created_at / updated_at, maintained by the database clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --------------------------------------------------------------------------- #
# Enums — stored as short strings (native_enum=False) so adding a value is a
# code change, never a database migration of an ENUM type.
# --------------------------------------------------------------------------- #
class ScopeType(str, enum.Enum):
    ORG = "org"
    TEAM = "team"
    USER = "user"
    REPO = "repo"


class CredentialKind(str, enum.Enum):
    TOKEN = "token"
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH = "oauth"
    SECRET = "secret"
    SSH_KEY = "ssh_key"
    GENERIC = "generic"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    GENERATED = "generated"          # workflow generated, PR not requested
    OPENED = "opened"                # PR opened
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"
    SUCCEEDED = "succeeded"          # reserved: pipeline observed green
    FAILED = "failed"               # reserved: pipeline observed red


class PullRequestState(str, enum.Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    FAILED_TO_CREATE = "failed_to_create"


class SecretStatus(str, enum.Enum):
    SET = "set"
    FAILED = "failed"
    SKIPPED_EMPTY = "skipped_empty"


def _enum(py_enum: type[enum.Enum]) -> Enum:
    """String-backed Enum column that stores the member *value* (e.g. 'opened')."""
    return Enum(
        py_enum,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class ScopedMixin:
    """Polymorphic tenant ownership: (scope_type, scope_id) points at whichever of
    organization / team / user / repository owns this row.

    We deliberately use a polymorphic pointer instead of four nullable FKs here:
    ownership resolution has a natural precedence (user > team > org), a single
    (scope_type, scope_id, <key>) unique constraint is clean, and lookups are one
    indexed predicate. Referential integrity for the owner is enforced in the
    data-access layer (repository.py), which only ever writes ids it just created
    or resolved. The high-value operational chain (runs -> PRs -> secrets) DOES
    use real foreign keys — see models.py.
    """

    scope_type: Mapped[ScopeType] = mapped_column(_enum(ScopeType), nullable=False, index=True)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class EncryptedString(TypeDecorator):
    """Transparently encrypt on write / decrypt on read (Fernet, see crypto.py).

    Stored as opaque text; a DB dump shows only ciphertext. Writing a secret
    without ``DB_ENCRYPTION_KEY`` configured raises rather than silently
    persisting plaintext (fail closed).
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # Python -> DB
        if value is None:
            return None
        return crypto.encrypt(value)

    def process_result_value(self, value, dialect):  # DB -> Python
        if value is None:
            return None
        return crypto.decrypt(value)
