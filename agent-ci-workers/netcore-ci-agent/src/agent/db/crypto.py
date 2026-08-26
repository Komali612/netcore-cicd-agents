"""Application-level encryption for secret columns (defence in depth).

Tokens, passwords and OAuth tokens are encrypted **before** they reach the
database, so a DB dump or a read-replica leak never exposes plaintext secrets.
We use Fernet (AES-128-CBC + HMAC, from ``cryptography``) with a symmetric key
supplied out-of-band via ``DB_ENCRYPTION_KEY``.

Generate a key once and store it in your secret manager:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Rotation: every ciphertext is tagged with ``key_id()`` (a short fingerprint of
the active key). Keep old keys around to decrypt historical rows, add the new
key to encrypt fresh ones, and back-fill offline. If no key is configured the
DB layer refuses to *store* secret values (fails closed) but still records the
non-secret run/PR history.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet


class EncryptionUnavailable(RuntimeError):
    """Raised when a secret must be encrypted but no key is configured."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet | None:
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def available() -> bool:
    """True when a valid ``DB_ENCRYPTION_KEY`` is present."""
    return _fernet() is not None


def key_id() -> str | None:
    """Short, non-reversible fingerprint of the active key, stored alongside each
    ciphertext so rotation can tell which key encrypted a given row."""
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        return None
    raw = key.encode() if isinstance(key, str) else key
    return hashlib.sha256(raw).hexdigest()[:12]


def encrypt(plaintext: str) -> str:
    f = _fernet()
    if f is None:
        raise EncryptionUnavailable(
            "DB_ENCRYPTION_KEY is not set; refusing to store a secret in plaintext."
        )
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    f = _fernet()
    if f is None:
        raise EncryptionUnavailable("DB_ENCRYPTION_KEY is not set; cannot decrypt.")
    return f.decrypt(token.encode("ascii")).decode("utf-8")


def reset_cache() -> None:
    """Drop the cached Fernet (tests rebind DB_ENCRYPTION_KEY between cases)."""
    _fernet.cache_clear()
