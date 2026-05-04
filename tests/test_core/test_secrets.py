"""
Tests for :mod:`core.secrets`.

Uses a temporary directory as ``~/.hivemind`` to avoid clobbering the
user's real key file.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from core.secrets import ENC_PREFIX, decrypt, encrypt, is_encrypted


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
def _hive_dir(tmp_path: Path) -> Path:
    """Return a ``.hivemind`` directory inside *tmp_path*."""
    d = tmp_path / ".hivemind"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------
class TestEncryptDecrypt:
    def test_roundtrip(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", _hive_dir(tmp_path) / "secret.key")
        plain = "sk-abc123secret"
        token = encrypt(plain)
        assert token.startswith(ENC_PREFIX)
        assert decrypt(token) == plain

    def test_decrypt_passthrough(self):
        """Non-encrypted values should pass through unchanged."""
        assert decrypt("hello") == "hello"
        assert decrypt("") == ""

    def test_multiple_values_unique(self, monkeypatch, tmp_path: Path):
        """Each encryption should produce a unique token (salt/nonce)."""
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", _hive_dir(tmp_path) / "secret.key")
        plain = "same-value"
        t1 = encrypt(plain)
        t2 = encrypt(plain)
        assert t1 != t2  # Fernet is not deterministic
        assert decrypt(t1) == plain
        assert decrypt(t2) == plain

    def test_long_secret(self, monkeypatch, tmp_path: Path):
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", _hive_dir(tmp_path) / "secret.key")
        plain = "a" * 10000
        token = encrypt(plain)
        assert decrypt(token) == plain


class TestIsEncrypted:
    def test_encrypted_prefix(self):
        assert is_encrypted(f"{ENC_PREFIX}abc") is True

    def test_plain_text(self):
        assert is_encrypted("hello") is False
        assert is_encrypted("") is False

    def test_prefix_only(self):
        assert is_encrypted(ENC_PREFIX) is True


class TestKeyFile:
    def test_key_file_created_on_first_encrypt(self, monkeypatch, tmp_path: Path):
        key_path = _hive_dir(tmp_path) / "secret.key"
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", key_path)
        assert not key_path.exists()
        encrypt("test")
        assert key_path.exists()

    def test_key_file_permissions(self, monkeypatch, tmp_path: Path):
        key_path = _hive_dir(tmp_path) / "secret.key"
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", key_path)
        encrypt("test")
        mode = os.stat(key_path).st_mode & stat.S_IRWXU
        assert mode == stat.S_IRUSR | stat.S_IWUSR, f"Expected 0600, got {oct(mode)}"

    def test_key_persistence(self, monkeypatch, tmp_path: Path):
        key_path = _hive_dir(tmp_path) / "secret.key"
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", key_path)
        token = encrypt("persist-me")
        assert decrypt(token) == "persist-me"

    def test_existing_key_is_reused(self, monkeypatch, tmp_path: Path):
        key_path = _hive_dir(tmp_path) / "secret.key"
        monkeypatch.setattr("core.secrets.SECRET_KEY_PATH", key_path)
        encrypt("first")
        key_bytes = key_path.read_bytes()
        encrypt("second")
        assert key_path.read_bytes() == key_bytes
