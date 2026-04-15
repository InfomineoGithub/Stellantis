import os
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient


class AuthError(Exception):
    """Exception raised for authentication errors."""

    pass


def _get_hs256_secret() -> str | None:
    """Return the HS256 shared secret if configured."""
    return os.getenv("JWT_SECRET") or os.getenv("BETTER_AUTH_SECRET") or None


def _try_hs256(token: str) -> dict[str, Any] | None:
    """Try HS256 verification with the shared secret.

    Returns the decoded payload on success, None if the secret is not set or the
    algorithm does not match (so we can fall through to JWKS).
    """
    secret = _get_hs256_secret()
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.exceptions.InvalidAlgorithmError:
        return None  # token uses a different algorithm — fall through to JWKS
    except jwt.InvalidTokenError:
        return None


def _jwks_url() -> str:
    """Return the JWKS endpoint URL for the better-auth server."""
    explicit = os.getenv("BETTER_AUTH_JWKS_URL")
    if explicit:
        return explicit
    base = os.getenv("BETTER_AUTH_URL", "http://localhost:2026").rstrip("/")
    return f"{base}/api/auth/jwks"


@lru_cache(maxsize=1)
def _get_jwks_client(url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given URL."""
    return PyJWKClient(url, cache_keys=True)


def _try_jwks(token: str) -> dict[str, Any]:
    """Verify an asymmetric JWT (EdDSA / ES256 / RS256) via JWKS.

    Raises AuthError on any failure.
    """
    jwks_url = _jwks_url()
    try:
        # Fetching the PyJWKClient from a cache ensures that
        # `cache_keys=True` actually persists across multiple verifications.
        jwks_client = _get_jwks_client(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA", "ES256", "ES384", "ES512", "RS256", "RS384", "RS512"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("JWT Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid JWT Token: {e}")
    except Exception as e:
        raise AuthError(f"Authentication failed (JWKS): {e}")


def verify_jwt(token: str) -> dict[str, Any]:
    """Verify and decode a JWT token.

    Strategy
    --------
    1.  Try HS256 with the shared secret (fast, no network). This handles
        tokens produced by the legacy shared-secret path.
    2.  Fall back to JWKS verification — required for tokens produced by
        better-auth's ``jwt()`` plugin which uses EdDSA asymmetric keys by
        default.
    """
    hs256_payload = _try_hs256(token)
    if hs256_payload is not None:
        return hs256_payload

    return _try_jwks(token)
