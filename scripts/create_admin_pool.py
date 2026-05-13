"""
scripts/create_admin_pool.py
─────────────────────────────
Create a pool of N admin accounts for multi-user load testing.

Usage:
    python scripts/create_admin_pool.py 20

Writes:
  • Each account to Supabase (auth + profiles.role='admin')
  • A single JSON file at tests/load/admin_pool.json with
    {"accounts": [{"email": "...", "password": "..."}, ...]}
"""

import json
import os
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from supabase import create_client, Client

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
POOL_PATH = Path(__file__).resolve().parent.parent / "tests" / "load" / "admin_pool.json"

load_dotenv(ENV_PATH)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _strong_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
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


def ensure_user(client: Client, email: str, password: str) -> str:
    existing_id = find_user_id(client, email)
    if existing_id:
        client.auth.admin.update_user_by_id(existing_id, {"password": password})
        return existing_id
    res = client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    user = getattr(res, "user", None) or res
    return getattr(user, "id", None) or user["id"]


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    client = get_client()

    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if POOL_PATH.exists():
        try:
            data = json.loads(POOL_PATH.read_text(encoding="utf-8"))
            for a in data.get("accounts", []):
                existing[a["email"]] = a["password"]
        except Exception:
            pass

    accounts = []
    for i in range(1, n + 1):
        email = f"loadtest-admin-{i:02d}@example.com"
        password = existing.get(email) or _strong_password()
        print(f"  [{i}/{n}] {email}")
        user_id = ensure_user(client, email, password)
        client.table("profiles").upsert(
            {"id": user_id, "role": "admin"},
            on_conflict="id",
        ).execute()
        accounts.append({"email": email, "password": password, "user_id": user_id})

    POOL_PATH.write_text(
        json.dumps({"accounts": accounts}, indent=2),
        encoding="utf-8",
    )
    print(f"\nCreated/refreshed {len(accounts)} admin accounts → {POOL_PATH}")


if __name__ == "__main__":
    main()
