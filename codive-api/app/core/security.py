"""
Two unrelated jobs live here on purpose, because they're the two places a
mistake is expensive: signing the session JWT, and encrypting GitHub access
tokens at rest.

Session JWTs use PyJWT (HS256) - short, standard, no reason to hand-roll it.
GitHub tokens are encrypted with Fernet (AES-128-CBC + HMAC, from the
`cryptography` package) before they ever reach the database, so a database
leak does not hand out live GitHub credentials.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

# PyJWT is imported lazily inside the two functions that need it rather than
# at module level. Behavior in production is identical (requirements.txt
# always installs it) - this only changes *when* the import happens, so
# that the Fernet-based functions below (which have no PyJWT dependency at
# all) stay importable and unit-testable in an environment that has
# `cryptography` but not yet `PyJWT`, without needing a stub or a mock.


class ConfigurationError(RuntimeError):
    """Raised when a security operation is attempted without the key it needs."""


# ---------------------------------------------------------------- sessions --

@dataclass(frozen=True)
class SessionClaims:
    user_id: str
    github_login: str
    issued_at: int
    expires_at: int


def create_session_token(user_id: str, github_login: str) -> str:
    import jwt  # lazy - see note at top of file

    settings = get_settings()
    if not settings.secret_key:
        raise ConfigurationError("SECRET_KEY is not set")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "login": github_login,
        "iat": now,
        "exp": now + settings.session_max_age_seconds,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def verify_session_token(token: str) -> SessionClaims | None:
    import jwt  # lazy - see note at top of file

    settings = get_settings()
    if not settings.secret_key:
        raise ConfigurationError("SECRET_KEY is not set")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return SessionClaims(
        user_id=payload["sub"],
        github_login=payload.get("login", ""),
        issued_at=payload["iat"],
        expires_at=payload["exp"],
    )


# ------------------------------------------------------- token encryption --

def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.token_encryption_key:
        raise ConfigurationError("TOKEN_ENCRYPTION_KEY is not set")
    key = settings.token_encryption_key.encode()
    # Accept a raw 32-byte secret too, not just a pre-formatted Fernet key,
    # so `TOKEN_ENCRYPTION_KEY=<anything long and random>` works without the
    # user having to run `Fernet.generate_key()` themselves.
    try:
        return Fernet(key)
    except (ValueError, Exception):
        padded = base64.urlsafe_b64encode(key.ljust(32, b"0")[:32])
        return Fernet(padded)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str | None:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None


def generate_fernet_key() -> str:
    """Used by `scripts/gen-keys.py` to print a value for TOKEN_ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()
