"""
Empire OS v3 — Direct lead intake
=================================

A simpler, more reliable lead intake that writes directly to lane_leads.

This is what the AEO forms + webhook intake + any external partner
should hit. It:
  1. Validates required fields (niche + metro minimum)
  2. Computes omega score (basic heuristics)
  3. Writes to lane_leads
  4. Returns the lead_id + qualification

The lead_deliverer_agent then picks it up on its 30s poll.

POST /v1/leads/direct-intake
  {
    "name": str (required for high tier),
    "email": str (required for high tier),
    "phone": str (optional),
    "niche": str (required)         # e.g. "hvac", "plumbing", "residential_roofing"
    "metro": str (required)         # e.g. "NYC", "LAX", "CHI"
    "state": str (optional),
    "details": str (optional),
    "source": str (default "api"),
    "lead_score": int (default: 50)  # 0-100, pre-computed by caller
  }

  Returns:
  {
    "ok": true,
    "lead_id": int,
    "niche": str,
    "metro": str,
    "tier": "gold|silver|bronze",
    "score": int,
    "status": "pending"
  }
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

HUB_CONTAINER = "empire-hub"
DB_PATH = "/root/empire_os/empire_os.db"


def _hub_exec_write_lead(payload: dict) -> dict:
    """Insert a lead into lane_leads via the hub container."""
    # Generate lane_id from niche + metro
    niche = payload.get("niche", "").strip()
    metro = payload.get("metro", "").strip().upper()
    if not niche or not metro:
        return {"error": "niche and metro required", "ok": False}

    score = int(payload.get("lead_score", 50))
    score = max(0, min(100, score))
    if score >= 75:
        tier = "gold"
    elif score >= 50:
        tier = "silver"
    else:
        tier = "bronze"

    lane_id = f"{niche}:{metro}"
    prospect_id = "prospect_" + datetime.now(timezone.utc).strftime("%y%m%d%H%M%S%f")
    now = datetime.now(timezone.utc).isoformat()

    # Build the SQL — pass values as argv to avoid shell escaping
    script = (
        "import sqlite3, sys\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "cur = c.execute('''\n"
        "  INSERT INTO lane_leads\n"
        "    (lane_id, prospect_id, status, omega_score, omega_tier,\n"
        "     name, email, phone, source, metro, state, details, niche,\n"
        "     created_at, updated_at)\n"
        "  VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n"
        "''', (\n"
        "  sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4],\n"
        "  sys.argv[5] or '', sys.argv[6] or '', sys.argv[7] or '',\n"
        "  sys.argv[8] or 'api', sys.argv[9] or '',\n"
        "  sys.argv[10] or '', sys.argv[11] or '', sys.argv[12] or '',\n"
        "  sys.argv[13], sys.argv[13]\n"
        "))\n"
        "print(cur.lastrowid)\n"
        "c.commit()\n"
        "c.close()\n"
    )
    args = [
        lane_id, prospect_id, str(score), tier,
        payload.get("name", ""), payload.get("email", ""), payload.get("phone", ""),
        payload.get("source", "api"), metro,
        payload.get("state", ""), payload.get("details", ""), niche,
        now,
    ]
    r = subprocess.run(
        ["incus", "exec", HUB_CONTAINER, "--",
         "/root/venv/bin/python3", "-c", script] + args,
        capture_output=True, text=True, timeout=15
    )
    if r.returncode != 0:
        return {"error": r.stderr[:300], "ok": False}
    try:
        lead_id = int(r.stdout.strip().split("\n")[-1])
    except (ValueError, IndexError):
        return {"error": "could not parse lead_id", "ok": False, "raw": r.stdout}
    return {
        "ok": True,
        "lead_id": lead_id,
        "lane_id": lane_id,
        "niche": niche,
        "metro": metro,
        "tier": tier,
        "score": score,
        "status": "pending",
    }


def main():
    """CLI: read JSON from stdin, write a lead."""
    payload = json.loads(sys.stdin.read())
    result = _hub_exec_write_lead(payload)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()