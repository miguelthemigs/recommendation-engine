"""
scripts/create_loadtest_accounts.py
────────────────────────────────────
One-shot script to bootstrap Cycle 5 load testing.

Creates two test accounts via the Supabase admin API (skipping email
confirmation), promotes one to admin, and prints the credentials so the
caller can append them to .env.

Idempotent — if the accounts already exist it leaves them alone and reuses
the stored credentials from .env (if present).
"""

import os
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv, dotenv_values
from supabase import create_client, Client

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

ADMIN_EMAIL = "loadtest-admin@example.com"
USER_EMAIL = "loadtest-user@example.com"


def _strong_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_client() -> Client:
    if not SUPABASE_URL or not SERVICE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SERVICE_KEY)


def find_user_id(client: Client, email: str) -> str | None:
    page = 1
    while True:
        resp = client.auth.admin.list_users(page=page, per_page=200)
        users = resp if isinstance(resp, list) else getattr(resp, "users", []) or []
        if not users:
            return None
        for u in users:
            u_email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
            if u_email and u_email.lower() == email.lower():
                return getattr(u, "id", None) or u.get("id")
        if len(users) < 200:
            return None
        page += 1


def ensure_user(client: Client, email: str, password: str) -> tuple[str, str, bool]:
    """
    Returns (user_id, password_used, created_flag).
    If the user already exists, resets their password and returns existing id.
    """
    existing_id = find_user_id(client, email)
    if existing_id:
        # reset password so we always have the current one
        client.auth.admin.update_user_by_id(existing_id, {"password": password})
        return existing_id, password, False

    res = client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    user = getattr(res, "user", None) or res
    user_id = getattr(user, "id", None) or user["id"]
    return user_id, password, True


def set_role(client: Client, user_id: str, role: str) -> None:
    client.table("profiles").upsert(
        {"id": user_id, "role": role},
        on_conflict="id",
    ).execute()


def write_env_lines(creds: dict) -> None:
    """Append/replace ADMIN_*/USER_* keys in .env, preserving everything else."""
    existing = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    for k, v in creds.items():
        existing[k] = v

    # Re-read original to preserve key order and comments for keys we don't touch
    if ENV_PATH.exists():
        original_text = ENV_PATH.read_text(encoding="utf-8").splitlines()
    else:
        original_text = []

    touched_keys = set(creds.keys())
    out_lines: list[str] = []
    seen: set[str] = set()
    for line in original_text:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in touched_keys:
                out_lines.append(f"{key}={creds[key]}")
                seen.add(key)
                continue
        out_lines.append(line)

    for k, v in creds.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def main() -> None:
    client = get_client()

    admin_pw = os.getenv("ADMIN_PASSWORD") or _strong_password()
    user_pw = os.getenv("USER_PASSWORD") or _strong_password()

    print(f"Ensuring admin account: {ADMIN_EMAIL}")
    admin_id, admin_pw, admin_created = ensure_user(client, ADMIN_EMAIL, admin_pw)
    set_role(client, admin_id, "admin")
    print(f"  id={admin_id} created={admin_created} role=admin")

    print(f"Ensuring regular account: {USER_EMAIL}")
    user_id, user_pw, user_created = ensure_user(client, USER_EMAIL, user_pw)
    set_role(client, user_id, "user")
    print(f"  id={user_id} created={user_created} role=user")

    creds = {
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "ADMIN_PASSWORD": admin_pw,
        "USER_EMAIL": USER_EMAIL,
        "USER_PASSWORD": user_pw,
    }
    write_env_lines(creds)
    print("\nCredentials written to .env:")
    for k, v in creds.items():
        masked = v if k.endswith("EMAIL") else (v[:4] + "…" + v[-2:])
        print(f"  {k}={masked}")


if __name__ == "__main__":
    main()
