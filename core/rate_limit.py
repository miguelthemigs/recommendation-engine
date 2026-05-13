"""
core/rate_limit.py
──────────────────
Sliding-window rate limiter for cold-start LLM jobs.

Policy:
  - 5 non-failed cold_start_jobs per user per rolling hour.
  - Admins (profiles.role = 'admin') bypass the limit entirely.

The check is a pure read against Supabase — enforcement happens in the route
handler before publishing to RabbitMQ.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import Client

from config import (
    COLDSTART_RATE_LIMIT_COUNT,
    COLDSTART_RATE_LIMIT_WINDOW_SECONDS,
)


@dataclass
class QuotaState:
    is_admin:  bool
    used:      int
    limit:     int            # COLDSTART_RATE_LIMIT_COUNT for users; -1 = unlimited (admin)
    remaining: int            # max(limit - used, 0); -1 = unlimited (admin)
    reset_at:  Optional[str]  # ISO8601 UTC — when the OLDEST counted job ages out


def _is_admin(client: Client, user_id: str) -> bool:
    """Look up the user's role in the profiles table. Default: not admin."""
    resp = (
        client.table("profiles")
        .select("role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return bool(resp and resp.data and resp.data.get("role") == "admin")


def get_quota_state(client: Client, user_id: str) -> QuotaState:
    """Compute the user's current cold-start quota state."""
    if _is_admin(client, user_id):
        return QuotaState(is_admin=True, used=0, limit=-1, remaining=-1, reset_at=None)

    window_start = datetime.now(timezone.utc) - timedelta(
        seconds=COLDSTART_RATE_LIMIT_WINDOW_SECONDS
    )

    resp = (
        client.table("cold_start_jobs")
        .select("created_at")
        .eq("user_id", user_id)
        .neq("status", "failed")
        .gte("created_at", window_start.isoformat())
        .order("created_at", desc=False)  # oldest first → row 0 is the next to age out
        .execute()
    )
    rows = resp.data or []
    used = len(rows)
    remaining = max(COLDSTART_RATE_LIMIT_COUNT - used, 0)

    reset_at: Optional[str] = None
    if rows:
        oldest = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
        reset_at = (oldest + timedelta(seconds=COLDSTART_RATE_LIMIT_WINDOW_SECONDS)).isoformat()

    return QuotaState(
        is_admin=False,
        used=used,
        limit=COLDSTART_RATE_LIMIT_COUNT,
        remaining=remaining,
        reset_at=reset_at,
    )
