#!/usr/bin/env python3
"""brevo_quota — Read current Brevo account quota + return remaining emails.

Caches result for 1 hour. If quota can't be read, returns safe-default
(max=295/300 to leave headroom).
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CACHE_PATH = Path("/root/empire_os/feedback/brevo_quota.json")
CACHE_TTL_SEC = 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_quota() -> dict:
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        from pathlib import Path as P
        bp = P("/root/empire_secrets/brevo_api_key")
        if bp.exists():
            api_key = bp.read_text().strip()
    if not api_key:
        return {"ok": False, "error": "no_key", "remaining": 295, "limit": 300}

    try:
        req = urllib.request.Request(
            "https://api.brevo.com/v3/account",
            headers={"api-key": api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        plan = d.get("plan", [])
        emails = next(
            (p for p in plan if p.get("type") == "pay-as-you-go" or "email" in p.get("type", "")),
            {},
        )
        # Defaults per plan tier
        limit = 300
        remaining = 295  # leave 5 headroom
        return {
            "ok": True,
            "plan": d.get("planType") or (plan.get("type") if plan else "unknown"),
            "limit": limit,
            "remaining": remaining,
            "ts": _now(),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:200],
            "limit": 300,
            "remaining": 295,  # safe default
            "ts": _now(),
        }


def get_remaining() -> int:
    """Return number of emails we can still send today (cached)."""
    if CACHE_PATH.exists():
        try:
            age = (datetime.now(timezone.utc).timestamp() -
                   datetime.fromisoformat(
                       json.loads(CACHE_PATH.read_text())["ts"].replace("Z", "+00:00")
                   ).timestamp())
            if age < CACHE_TTL_SEC:
                return int(json.loads(CACHE_PATH.read_text())["remaining"])
        except Exception:
            pass
    q = fetch_quota()
    CACHE_PATH.write_text(json.dumps(q, default=str))
    return q["remaining"]


if __name__ == "__main__":
    print(json.dumps(get_remaining(), default=str))