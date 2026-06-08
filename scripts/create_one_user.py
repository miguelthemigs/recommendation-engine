"""
scripts/create_one_user.py
───────────────────────────
Create or reset a single regular Supabase user for testing.
Writes USER_EMAIL / USER_PASSWORD to .env.
"""

import os
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from supabase import create_client, Client

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _strong_password(length: int = 20) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))


def find_user_id(client: Client, email: str) -> str | None:
    page = 1
    while True:
        resp = client.auth.admin.list_users(page=page, per_page=200)
        users = resp if isinstance(resp, list) else getattr(resp, "users", []) or []
        if not users:
            return None
        for u in users:
            ue = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
            if ue and ue.lower() == email.lower():
                return getattr(u, "id", None) or u.get("id")
        if len(users) < 200:
            return None
        page += 1


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_one_user.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    password = _strong_password()
    client = create_client(SUPABASE_URL, SERVICE_KEY)

    user_id = find_user_id(client, email)
    if user_id:
        client.auth.admin.update_user_by_id(user_id, {"password": password})
        print(f"  reset password for existing user {email} (id={user_id})")
    else:
        res = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        user = getattr(res, "user", None) or res
        user_id = getattr(user, "id", None) or user["id"]
        print(f"  created user {email} (id={user_id})")

    # Ensure profiles row exists with role=user
    client.table("profiles").upsert(
        {"id": user_id, "role": "user"},
        on_conflict="id",
    ).execute()

    # Also wipe any prior cold_start_jobs for this user so quota window is clean
    delete_resp = (
        client.table("cold_start_jobs").delete().eq("user_id", user_id).execute()
    )
    print(f"  cleared {len(delete_resp.data) if delete_resp.data else 0} prior cold_start_jobs")

    # Update .env
    text = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    keys_to_set = {"USER_EMAIL": email, "USER_PASSWORD": password}
    out, seen = [], set()
    for line in text:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=", 1)[0].strip()
            if k in keys_to_set:
                out.append(f"{k}={keys_to_set[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in keys_to_set.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("  wrote USER_EMAIL/USER_PASSWORD to .env")


if __name__ == "__main__":
    main()
