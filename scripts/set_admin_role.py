"""
scripts/set_admin_role.py
─────────────────────────
Promote a user to admin by email. Requires service role.

Usage:
    python scripts/set_admin_role.py user@example.com
    python scripts/set_admin_role.py user@example.com --revoke

Admins bypass cold-start rate limiting (5 jobs/hour for regular users).
"""

import argparse
import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL              = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def find_user_id_by_email(client: Client, email: str) -> str | None:
    """Page through auth.users until we find the matching email."""
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


def set_role(email: str, role: str) -> None:
    client = get_client()
    user_id = find_user_id_by_email(client, email)
    if not user_id:
        print(f"No user found with email {email}")
        sys.exit(1)

    # Upsert defensively — handles users created before the profiles migration backfill ran.
    client.table("profiles").upsert(
        {"id": user_id, "role": role},
        on_conflict="id",
    ).execute()
    print(f"Set role={role} for {email} (id={user_id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote/demote a user.")
    parser.add_argument("email", help="User email")
    parser.add_argument("--revoke", action="store_true", help="Demote to regular user")
    args = parser.parse_args()
    set_role(args.email, "user" if args.revoke else "admin")


if __name__ == "__main__":
    main()
