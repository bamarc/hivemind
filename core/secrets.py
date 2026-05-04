"""
Symmetric secret encryption using Fernet.

Encryption key is stored at ``~/.hivemind/secret.key`` (``0600`` permissions).
Auto-generated on first call to :func:`encrypt`.

Encrypted values are stored in YAML with the ``enc://`` prefix, keeping the
config file human-readable while protecting secrets at rest.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

SECRET_KEY_PATH = Path("~/.hivemind/secret.key").expanduser()
ENC_PREFIX = "enc://"


def _ensure_key() -> bytes:
    """Load the existing key or generate a new one.

    The key file is created with ``0600`` permissions so only the owning
    user can read it.
    """
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        SECRET_KEY_PATH.write_bytes(key)
        SECRET_KEY_PATH.chmod(0o600)
        return key
    return SECRET_KEY_PATH.read_bytes()


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* and return an ``enc://``-prefixed token.

    The token can safely be stored in a YAML configuration file.
    """
    f = Fernet(_ensure_key())
    return ENC_PREFIX + f.encrypt(plaintext.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a value that starts with ``enc://``.

    Non-encrypted values are passed through unchanged.
    """
    if not value.startswith(ENC_PREFIX):
        return value
    f = Fernet(_ensure_key())
    return f.decrypt(value[len(ENC_PREFIX) :].encode()).decode()


def is_encrypted(value: str) -> bool:
    """Return ``True`` if *value* appears to be an encrypted token."""
    return value.startswith(ENC_PREFIX)
