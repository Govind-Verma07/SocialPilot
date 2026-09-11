"""
app/core/encryption.py
----------------------
Symmetric token encryption at rest using Fernet (AES-128-CBC + HMAC-SHA256).
OAuth access tokens and refresh tokens are encrypted before being written
to PostgreSQL, and decrypted only when making provider API requests.
Tokens are NEVER returned to API clients or logged.
"""

import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet_key() -> bytes:
    """
    Derive a deterministic 32-byte URL-safe base64 Fernet key from the JWT_SECRET_KEY.
    This guarantees encryption is always functional without requiring additional config.
    """
    secret_bytes = settings.JWT_SECRET_KEY.encode("utf-8")
    digest = hashlib.sha256(secret_bytes).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_get_fernet_key())


def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a plain text OAuth token for database storage at rest."""
    if not plain_token:
        return None
    encrypted_bytes = _fernet.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt a stored token back to plain text for platform API calls."""
    if not encrypted_token:
        return None
    try:
        decrypted_bytes = _fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception:
        return None
