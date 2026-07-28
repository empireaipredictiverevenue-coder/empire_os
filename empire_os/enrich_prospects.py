#!/usr/bin/env python3
"""enrich_prospects — Fill missing emails in si_buyer_outreach using Hunter.io.

Iterates si_buyer_outreach rows where:
  - active=1
  - email IS NULL OR email = ''
  - url is present (Hunter needs a domain to look up)

Calls Hunter domain-search API → first result with confidence > 50 →
writes back to email column. Tracks rate-limit usage.

Reads HUNTER_API_KEY from /root/empire_secrets/hunter_api_key (preferred)
or HUNTER_API_KEY env var.

Tables touched: si_buyer_outreach (UPDATE only)
Logs: /root/empire_os/feedback/hunter_enrich.jsonl
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "hunter_enrich.jsonl"

DEFAULT_BATCH = int(os.getenv("HUNTER_BATCH", "100"))
MIN_CONFIDENCE = int(os.getenv("HUNTER_MIN_CONFIDENCE", "50"))
DELAY_BETWEEN_CALLS = float(os.getenv("HUNTER_DELAY", "1.5"))  # seconds


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_key() -> str:
    key = os.environ.get("HUNTER_API_KEY", "").strip()
    if not key:
        from pathlib import Path as P
        bp = P("/root/empire_secrets/hunter_api_key")
        if bp.exists():
            key = bp.read_text().strip()
    return key


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _domain_from_url(url: str) -> str:
    """Extract clean domain from URL."""
    if not url:
        return ""
    u = urllib.parse.urlparse(url if "://" in url else f"http://{url}")
    domain = u.netloc or u.path
    domain = domain.lower().replace("www.", "")
    return domain.split(":")[0]


def hunter_domain_search(api_key: str, domain: str) -> dict:
    """Call Hunter domain-search API. Returns parsed JSON or error."""
    url = (
        f"https://api.hunter.io/v2/domain-search?domain={urllib.parse.quote(domain)}"
        f"&api_key={urllib.parse.quote(api_key)}&limit=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "empire-os/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"error": "rate_limited", "_domain": domain}
        return {"error": f"http_{e.code}", "_domain": domain}
    except Exception as e:
        return {"error": str(e)[:200], "_domain": domain}


def pick_best_email(payload: dict) -> str:
    """From Hunter response, return best email meeting MIN_CONFIDENCE."""
    data = payload.get("data") or {}
    emails = data.get("emails") or []
    for e in emails:
        if e.get("confidence", 0) >= MIN_CONFIDENCE and e.get("value"):
            return str(e["value"]).lower().strip()
    return ""


def fetch_pending_prospects(c: sqlite3.Connection, batch: int) -> list:
    """Get prospects with missing email but known URL/business_name."""
    rows = c.execute("""
        SELECT prospect_id, business_name, url, niche
        FROM si_buyer_outreach
        WHERE active = 1
          AND (email IS NULL OR email = '' OR email LIKE 'tenant:%')
          AND url IS NOT NULL AND url != ''
          AND business_name IS NOT NULL AND business_name != ''
        ORDER BY prospect_id DESC
        LIMIT ?
    """, (batch,)).fetchall()
    return [dict(r) for r in rows]


def update_email(c: sqlite3.Connection, prospect_id: str, email: str) -> None:
    c.execute(
        "UPDATE si_buyer_outreach SET email=?, last_touch_at=datetime('now') "
        "WHERE prospect_id=?",
        (email, prospect_id),
    )
    c.commit()


def run(batch: int = DEFAULT_BATCH, dry_run: bool = False) -> dict:
    api_key = _load_key()
    summary = {"ts": _now(), "batch": batch, "dry_run": dry_run,
               "scanned": 0, "enriched": 0, "no_email": 0,
               "rate_limited": 0, "errors": 0, "key_loaded": bool(api_key)}

    if not api_key:
        summary["error"] = "no_api_key"
        _log({"ts": _now(), "event": "no_key"})
        return summary

    c = sqlite3.connect(DB_PATH, timeout=15)
    try:
        prospects = fetch_pending_prospects(c, batch)
        summary["scanned"] = len(prospects)

        for p in prospects:
            domain = _domain_from_url(p.get("url", ""))
            if not domain:
                summary["no_email"] += 1
                continue
            payload = hunter_domain_search(api_key, domain)
            if "error" in payload:
                if payload["error"] == "rate_limited":
                    summary["rate_limited"] += 1
                    _log({"ts": _now(), "event": "rate_limit_hit",
                          "domain": domain, "scanned_so_far": summary["enriched"]})
                    break
                summary["errors"] += 1
                _log({"ts": _now(), "event": "error",
                      "domain": domain, "error": payload["error"]})
                continue

            email = pick_best_email(payload)
            if email:
                if not dry_run:
                    update_email(c, p["prospect_id"], email)
                summary["enriched"] += 1
                _log({"ts": _now(), "event": "enriched",
                      "prospect_id": p["prospect_id"],
                      "domain": domain, "email": email,
                      "business": p.get("business_name")})
            else:
                summary["no_email"] += 1
                _log({"ts": _now(), "event": "no_email_found",
                      "prospect_id": p["prospect_id"], "domain": domain})

            time.sleep(DELAY_BETWEEN_CALLS)
    finally:
        c.close()

    _log({"ts": _now(), "event": "tick_end", "summary": summary})
    return summary


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    batch = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else DEFAULT_BATCH
    print(json.dumps(run(batch=batch, dry_run=dry), indent=2))