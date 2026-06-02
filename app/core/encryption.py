"""
OpsPilot — AES-256-GCM Data Encryption at Rest (Phase 8).

Provides:
  - ``encrypt(plaintext)`` / ``decrypt(ciphertext)`` helpers.
  - ``EncryptedString`` — a SQLAlchemy TypeDecorator that transparently
    encrypts on write and decrypts on read, requiring zero changes to
    query logic.

Key derivation:
  Uses the ``ENCRYPTION_KEY`` env var (32 bytes, hex-encoded) if set.
  Falls back to deriving a key from ``JWT_SECRET_KEY`` via HKDF-SHA256.
  This ensures the module works in all environments without extra setup.

Encryption scheme:
  AES-256-GCM with a random 12-byte nonce per encryption call.
  The output format is: ``base64(nonce + ciphertext + tag)``
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key() -> bytes:
    """
    Return a 32-byte AES key.

    Priority:
    1. ``ENCRYPTION_KEY`` env var (hex-encoded 32-byte value).
    2. Derived from ``JWT_SECRET_KEY`` via HKDF-SHA256.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if settings.ENCRYPTION_KEY is not None:
        raw = settings.ENCRYPTION_KEY.get_secret_value()
        try:
            key_bytes = bytes.fromhex(raw)
            if len(key_bytes) == 32:
                return key_bytes
        except ValueError:
            pass
        # Accept raw bytes if not valid hex
        return raw.encode()[:32].ljust(32, b"\x00")

    # Derive from JWT secret via HKDF
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    jwt_secret = settings.JWT_SECRET_KEY.get_secret_value().encode()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"opspilot-encryption-v1",
        info=b"aes-256-gcm-key",
    )
    return hkdf.derive(jwt_secret)


@lru_cache(maxsize=1)
def _get_aesgcm() -> AESGCM:
    """Cached AESGCM instance (key is derived once at startup)."""
    return AESGCM(_derive_key())


def encrypt(plaintext: str) -> str:
    """
    Encrypt a UTF-8 string using AES-256-GCM.

    Returns a base64-encoded string: ``base64(nonce[12] + ciphertext + tag[16])``.
    The nonce is randomly generated per call.
    """
    nonce = os.urandom(12)
    aesgcm = _get_aesgcm()
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt(token: str) -> str:
    """
    Decrypt a base64-encoded AES-256-GCM ciphertext string.

    Raises ``ValueError`` if decryption fails (wrong key or corrupted data).
    """
    try:
        data = base64.b64decode(token.encode())
        nonce, ciphertext = data[:12], data[12:]
        aesgcm = _get_aesgcm()
        return aesgcm.decrypt(nonce, ciphertext, None).decode()
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc


# ── SQLAlchemy TypeDecorator ──────────────────────────────────

try:
    from sqlalchemy import String
    from sqlalchemy.engine import Dialect
    from sqlalchemy.types import TypeDecorator

    class EncryptedString(TypeDecorator[str]):
        """
        A SQLAlchemy column type that transparently encrypts on write
        and decrypts on read using AES-256-GCM.

        Usage::

            from app.core.encryption import EncryptedString

            class Integration(Base):
                api_secret: Mapped[str] = mapped_column(EncryptedString(500))
        """

        impl = String
        cache_ok = True

        def __init__(self, length: int = 1000) -> None:
            super().__init__(length)

        def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
            if value is None:
                return None
            return encrypt(value)

        def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
            if value is None:
                return None
            try:
                return decrypt(value)
            except ValueError:
                # Return raw value if decryption fails (e.g. unencrypted legacy data)
                return value

except ImportError:
    pass  # SQLAlchemy not available in non-ORM contexts
