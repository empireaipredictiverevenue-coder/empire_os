#!/usr/bin/env python3
"""
Lane Activator — Empire OS v3

Activate 50+ empty lanes by:
  1. Selecting top empty lanes by seat_price
  2. Occupying a seat via lane_seats (multi-seat per lane supported)
  3. Creating a pay_url record for each via /v1/billing/subscribe
  4. Emitting outreach-ready payloads the buyer-hunter can push
  5. Logging activation to /root/feedback/lane_activation.jsonl

This is the Empire OS activation loop: vacant lanes get pay_urls,
buyer-hunter picks them up, outreach pushes to prospective contractors.
"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
VAULT = "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
LOG_PATH = Path("/root/feedback/lane_activation.jsonl")
TARGET = 50


def get_empty_lanes(limit: int = 60) -> list[dict]:
    """Get top empty lanes from container DB via the db_adapter."""
    try:
        from empire_os.db_adapter import get_empty_lanes as _adapter
        return _adapter(limit)
    except Exception as e:
        print(f"adapter err: {e}")
        return []


def lookup_tenant_by_email(email: str) -> str | None:
    """Look up tenant_id by email via container DB."""
    script = (
        "import sqlite3\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "row = c.execute('SELECT tenant_id FROM si_tenant WHERE email=?', ('" + email + "',)).fetchone()\n"
        "print(row[0] if row else '')\n"
    )
    out = subprocess.run(
        ["incus", "exec", "empire-hub", "--",
         "/root/venv/bin/python3", "-c", script],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return out or None


def _http_post_with_retry(url, body, timeout=10, retries=4):
    """POST with exponential backoff on 500/database-locked."""
    import urllib.request
    import urllib.error
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                last = (e.code, json.loads(e.read()))
            except Exception:
                last = (e.code, {"error": str(e)[:200]})
            if e.code == 500 and "database is locked" in str(last[1]):
                time.sleep(1 + attempt * 2)
                continue
            return last
        except Exception as e:
            last = (0, {"error": str(e)[:200]})
            time.sleep(1 + attempt)
    return last


def create_pay_url(niche: str, metro: str, lane_id: str, amount_usdc: float) -> dict | None:
    """Sign up a tenant for the lane and start a subscription to generate a pay_url."""
    import urllib.error
    tenant_email = f"lane-{lane_id.replace(':', '-')}@empire-ai.co.uk"
    tenant_name = f"Empire-{niche}-{metro}"
    tenant_id = None
    s, signup_data = _http_post_with_retry(
        f"{HUB_URL}/v1/tenants/signup",
        json.dumps({"name": tenant_name, "email": tenant_email, "plan": "starter"}).encode(),
    )
    if s == 200:
        tenant_id = signup_data.get("tenant_id")
    elif s == 409:
        tenant_id = lookup_tenant_by_email(tenant_email)
        if not tenant_id:
            return {"error": "tenant_exists_no_lookup", "tenant_email": tenant_email}
    else:
        return {"error": f"signup_http_{s}: {str(signup_data)[:160]}"}

    if not tenant_id:
        return {"error": "no_tenant_id"}

    # Occupy a seat via lane_seats (multi-seat per lane)
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.lane_seats import occupy_seat
        seat_result = occupy_seat(lane_id, tenant_id, tier="standard")
    except Exception as e:
        seat_result = {"ok": False, "error": str(e)[:200]}

    s2, data = _http_post_with_retry(
        f"{HUB_URL}/v1/billing/subscribe",
        json.dumps({
            "tenant_id": tenant_id,
            "plan": "starter",
            "billing_cycle": "monthly",
            "seats": 1,
            "payment_method": "crypto_usdc",
            "metadata": {
                "lane_id": lane_id,
                "niche": niche,
                "metro": metro,
                "source": "lane_activation_v2",
                "amount_usdc": amount_usdc,
            },
        }).encode(),
    )
    if s2 == 200:
        pay = data.get("payment") or {}
        if pay.get("payment_request_id"):
            pay["tenant_id"] = tenant_id
            pay["seat"] = seat_result
            return pay
        return {"error": "no_payment_in_response", "data": data}
    return {"error": f"sub_http_{s2}: {str(data)[:200]}"}


def emit_buyer_prospect(lane: dict, pay: dict) -> bool:
    """Register the lane as a buyer-prospect the buyer-hunter agent will pick up."""
    import urllib.request
    body = json.dumps({
        "lane_id": lane["id"],
        "niche": lane.get("niche") or lane.get("sub_niche") or "unknown",
        "metro": lane["metro"],
        "seat_price_usdc": lane["seat_price"],
        "payment_request_id": (pay or {}).get("payment_request_id"),
        "vault": VAULT,
        "memo": (pay or {}).get("memo"),
        "amount_usdc": (pay or {}).get("amount_usdc"),
        "source": "lane_activation_v2",
    }).encode()
    for path in ("/v1/lanes/activate", "/v1/buyers/apply"):
        try:
            req = urllib.request.Request(
                f"{HUB_URL}{path}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status < 300
        except urllib.error.HTTPError as e:
            if e.code in (404, 405):
                continue
            return False
        except Exception:
            return False
    return False


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"=== Lane Activator — target {TARGET} lanes ===\n")
    # Run lane_seats migration once on startup
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.lane_seats import migrate as _seats_migrate
        _seats_migrate()
    except Exception as e:
        print(f"lane_seats migrate: {e}")
    lanes = get_empty_lanes(limit=TARGET + 10)
    print(f"Fetched {len(lanes)} empty lanes from container DB\n")
    activated = 0
    failed = 0
    for lane in lanes:
        # Normalize once: db_adapter returns 'sub_niche'; rest of the script
        # uses 'niche'. Mutate the dict so all downstream accesses work.
        if "niche" not in lane and "sub_niche" in lane:
            lane["niche"] = lane["sub_niche"]
        amount = lane["seat_price"]
        # db_adapter returns 'sub_niche' for the niche field
        niche = lane.get("niche") or lane.get("sub_niche") or "unknown"
        metro = lane["metro"]
        pay = create_pay_url(niche, metro, lane["id"], amount)
        ok = bool(pay and pay.get("payment_request_id"))
        buyer_registered = emit_buyer_prospect(lane, pay or {})
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lane_id": lane["id"],
            "niche": lane.get("niche") or lane.get("sub_niche") or "unknown",
            "metro": lane["metro"],
            "seat_price_usdc": amount,
            "lane_number": lane["lane_number"],
            "pay_url": (pay or {}).get("payment_request_id"),
            "vault": (pay or {}).get("vault_wallet") or VAULT,
            "memo": (pay or {}).get("memo"),
            "buyer_registered": buyer_registered,
            "pay_url_generated": ok,
            "seat": (pay or {}).get("seat"),
        }
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
        if ok:
            activated += 1
        else:
            failed += 1
        marker = "✓" if ok else "✗"
        seats_info = (pay or {}).get("seat", {})
        print(f'  {marker} {lane["id"]:<30} {lane["niche"]:<20} {lane["metro"]:<6} '
              f'${amount:>7,.0f}  '
              f'pay_url={((pay or {}).get("payment_request_id") or "<none>")[:20]:<20}  '
              f'seats={seats_info.get("seats_used","?")}/{seats_info.get("seats_limit","?")}')
    print()
    print(f"=== Activated: {activated} / {TARGET} target ===")
    print(f"=== Failed: {failed} ===")
    return 0 if activated >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())