"""Secrets at rest: Fernet with a key derived from ASSAYR_SECRET_KEY."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret_key: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest()))


def encrypt(secret_key: str, value: str) -> str:
    return _fernet(secret_key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(secret_key: str, token: str) -> str | None:
    """The secret, or None when the key does not match (for example after the key was replaced)."""
    try:
        return _fernet(secret_key).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
