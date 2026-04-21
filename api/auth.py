"""
api/auth.py
───────────
FastAPI dependencies for JWT-based authentication via Supabase Auth.
Validates tokens using Supabase's JWKS (ES256 asymmetric keys).
"""

from typing import Optional
from fastapi import Request, HTTPException
from jose import jwt, JWTError, jwk
import requests
from config import SUPABASE_URL

# Fetch JWKS once at import time
_jwks: dict = {}

def _get_jwks() -> dict:
    global _jwks
    if not _jwks:
        resp = requests.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
        resp.raise_for_status()
        _jwks = resp.json()
        print(f"[auth] Loaded JWKS with {len(_jwks.get('keys', []))} key(s)")
    return _jwks


def _decode_token(token: str) -> dict:
    """Decode and verify a Supabase JWT using JWKS."""
    jwks = _get_jwks()
    # Get the key ID from the token header
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    # Find the matching key
    rsa_key = {}
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            rsa_key = key
            break

    if not rsa_key:
        raise JWTError(f"Key {kid} not found in JWKS")

    return jwt.decode(
        token,
        rsa_key,
        algorithms=[header.get("alg", "ES256")],
        options={"verify_aud": False},
    )


def _extract_token(request: Request) -> Optional[str]:
    """Pull the Bearer token from the Authorization header, if present."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:]


def get_current_user(request: Request) -> dict:
    """FastAPI dependency — requires a valid JWT. Returns decoded payload."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token.")
    try:
        payload = _decode_token(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload


def get_optional_user(request: Request) -> Optional[dict]:
    """FastAPI dependency — returns decoded payload if valid JWT, else None."""
    token = _extract_token(request)
    if not token:
        return None
    try:
        return _decode_token(token)
    except JWTError:
        return None
