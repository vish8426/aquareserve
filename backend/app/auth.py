"""Authentication for the product app

A self-contained auth gate with no external service and no database server: a file-based user store (``data/users.jsonl``), salted PBKDF2 password hashing and stateless HMAC-signed bearer tokens, all from the Python standard library.
Customer accounts self-register; an admin account is seeded from environment variables.

This is a lightweight implementation - for commercial deployments, a real database and a proper auth service (e.g. Keycloak) are recommended.
On an ephemeral host the user file resets on redeploy (like the leads file); a later version would graduate to a real PostgreSQL user table, where bcrypt/argon2 and refresh tokens would also be appropriate.
Set ``AQUARESERVE_SECRET`` in production so tokens are unforgeable.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, Header, HTTPException

from .store import REPO_ROOT

USERS_PATH = Path(os.environ.get("AQUARESERVE_USERS_PATH", REPO_ROOT / "data" / "users.jsonl"))
SECRET = os.environ.get("AQUARESERVE_SECRET", "dev-insecure-secret-change-me").encode()
TOKEN_TTL_SECONDS = 7 * 24 * 3600
PBKDF2_ITERATIONS = 200_000


# -- password hashing -------------------------------------------------------
def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()


def verify_password(user: dict[str, Any], password: str) -> bool:
    expected = _hash_password(password, user["salt"])
    return hmac.compare_digest(expected, user["password_hash"])


# -- user store (JSONL) -------------------------------------------------------
def _all_users() -> list[dict[str, Any]]:
    if not USERS_PATH.exists():
        return []
    return [json.loads(ln) for ln in USERS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


def find_user_by_email(email: str) -> dict[str, Any] | None:
    email = email.strip().lower()
    return next((u for u in _all_users() if u["email"] == email), None)


def find_user_by_id(uid: str) -> dict[str, Any] | None:
    return next((u for u in _all_users() if u["id"] == uid), None)


def create_user(email: str, password: str, name: str, farm: str | None = None,
                role: str = "customer") -> dict[str, Any]:
    email = email.strip().lower()
    name = (name or "").strip()
    if not email or "@" not in email:
        raise ValueError("A valid email is required.")
    if not name:
        raise ValueError("Your name is required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if find_user_by_email(email):
        raise ValueError("An account with that email already exists.")
    salt = os.urandom(16).hex()
    user = {
        "id": uuid.uuid4().hex[:12],
        "email": email,
        "name": name,
        "farm": farm,
        "role": role,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USERS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(user) + "\n")
    return user


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {k: user.get(k) for k in ("id", "email", "name", "role", "farm")}


# -- tokens (HMAC-signed, stateless) ------------------------------------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: dict[str, Any]) -> str:
    payload = {"sub": user["id"], "email": user["email"], "role": user["role"],
               "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(body))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


# -- FastAPI dependencies -----------------------------------------------------
def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization[7:])
    user = find_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def ensure_admin() -> None:
    """Seed the admin account from AQUARESERVE_ADMIN_EMAIL / AQUARESERVE_ADMIN_PASSWORD if set and not already present.
    A no-op when the variables are absent.
    """
    email = os.environ.get("AQUARESERVE_ADMIN_EMAIL")
    password = os.environ.get("AQUARESERVE_ADMIN_PASSWORD")
    if email and password and not find_user_by_email(email):
        create_user(email, password, name="Administrator", role="admin")
