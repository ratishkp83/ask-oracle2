"""Symmetric encryption for secrets stored at rest (e.g. profile passwords).

Uses Fernet (AES-128-CBC + HMAC) from the `cryptography` package. The Fernet
key is derived from the ``APP_SECRET_KEY`` environment variable via SHA-256 so
operators may supply any passphrase rather than a raw Fernet key. The plaintext
secret is never written to disk or returned by the API.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

_APP_SECRET_ENV = "APP_SECRET_KEY"


class SecretConfigError(RuntimeError):
    """Raised when secret encryption is requested but APP_SECRET_KEY is unset."""


def _fernet() -> Fernet:
    secret = os.getenv(_APP_SECRET_ENV)
    if not secret or not secret.strip():
        raise SecretConfigError(
            f"{_APP_SECRET_ENV} is not set. It is required to store or read "
            "encrypted connection passwords. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it in your env."
        )
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return an opaque, storable token string."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`.

    Raises :class:`SecretConfigError` if the key cannot decrypt the token (for
    example after ``APP_SECRET_KEY`` was rotated), so callers can surface a
    clear message instead of a raw cryptography error.
    """
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretConfigError(
            "Stored credential could not be decrypted. Has APP_SECRET_KEY "
            "changed since the profile was saved?"
        ) from exc


def generate_app_secret_key() -> str:
    """Convenience helper to mint a fresh key for first-time setup."""
    return Fernet.generate_key().decode("utf-8")
