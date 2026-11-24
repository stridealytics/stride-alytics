"""Auth helpers.

Phase 1 keeps the logic minimal so the endpoint contract works against
a Supabase JWT verifier. The actual Supabase REST call lives in
``supabase_client`` (added in Phase 2 when ``SUPABASE_URL`` is set).
"""

from __future__ import annotations

import time
from typing import Any, cast

import httpx
from jose import JWTError, jwt

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

JWT_ALGORITHM = "HS256"


def dev_auth_enabled() -> bool:
    """True only when running with ``ENVIRONMENT=development``.

    Gates the stub tokens (``dev:<id>``, ``dev-admin-token``) and the dev
    login fallback so they can never be used against a deployed API.
    """
    return settings.ENVIRONMENT.strip().lower() == "development"


def get_jwt_secret() -> str:
    # Read from settings (which also loads .env), not os.getenv, so the value
    # the middleware checked is the value used here.
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is not configured")
    return secret


_JWKS_TTL_SECONDS = 3600
_jwks_cache: tuple[float, dict[str, Any]] | None = None
_ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")


def jwks_url() -> str | None:
    if settings.SUPABASE_JWKS_URL:
        return settings.SUPABASE_JWKS_URL
    if settings.SUPABASE_URL:
        return settings.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return None


def auth_configured() -> bool:
    """True when a token can be verified at all (shared secret or a JWKS endpoint)."""
    return bool(settings.SUPABASE_JWT_SECRET or jwks_url())


def _get_jwks(force: bool = False) -> dict[str, Any]:
    """Fetch (and cache for an hour) the project's public signing keys."""
    global _jwks_cache
    now = time.monotonic()
    if not force and _jwks_cache and now - _jwks_cache[0] < _JWKS_TTL_SECONDS:
        return _jwks_cache[1]
    url = jwks_url()
    if not url:
        raise JWTError("no JWKS URL configured (set SUPABASE_URL or SUPABASE_JWKS_URL)")
    try:
        resp = httpx.get(url, timeout=5)
        resp.raise_for_status()
        payload: object = resp.json()
    except Exception as exc:  # noqa: BLE001 - any failure means we cannot verify
        raise JWTError(f"could not load signing keys: {exc}") from exc
    if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
        raise JWTError("JWKS response must be a JSON object")
    keys = cast(dict[str, Any], payload)
    _jwks_cache = (now, keys)
    return keys


def _signing_key(kid: str | None) -> dict[str, Any]:
    for attempt in (False, True):  # retry once with a fresh fetch to pick up rotated keys
        raw_keys = _get_jwks(force=attempt).get("keys", [])
        if not isinstance(raw_keys, list):
            raise JWTError("JWKS response has an invalid keys field")
        for key in raw_keys:
            if isinstance(key, dict) and (kid is None or key.get("kid") == kid):
                return cast(dict[str, Any], key)
    raise JWTError("no matching signing key for token")


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Decode a Supabase-issued JWT and return its claims.

    Supports both signing schemes a Supabase project can use: the legacy shared secret
    (HS256, ``SUPABASE_JWT_SECRET``) and asymmetric signing keys (ES256/RS256, verified against
    the project's JWKS). The algorithm comes from a whitelist, never blindly from the token.

    Supabase access tokens carry ``aud: "authenticated"``; python-jose rejects
    any token with an ``aud`` claim unless the expected audience is passed.

    Raises ``JWTError`` on invalid/expired tokens.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")
    if alg == JWT_ALGORITHM:
        if not settings.SUPABASE_JWT_SECRET:
            raise JWTError("HS256 token but SUPABASE_JWT_SECRET is not configured")
        key: Any = get_jwt_secret()
        algorithms = [JWT_ALGORITHM]
    elif alg in _ASYMMETRIC_ALGORITHMS:
        key = _signing_key(header.get("kid"))
        algorithms = [alg]
    else:
        raise JWTError(f"unsupported token algorithm: {alg!r}")
    claims = jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience=settings.SUPABASE_JWT_AUDIENCE,
    )
    if "sub" not in claims:
        raise JWTError("missing 'sub' claim in JWT")
    return claims
