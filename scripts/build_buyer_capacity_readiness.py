#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from empire_os.buyer_capacity_readiness import summarize_buyer_capacity
from empire_os.qualification_worker_v2 import request_json

ROOT = Path("/srv/empire_os")
OUT = ROOT / "runtime" / "buyer_capacity_readiness" / "latest.json"

SELECT = ",".join((
    "id","buyer_name","status","is_active","commercial_activation_state",
    "reviewed_at","commercial_activated_at",
    "commercial_terms_source","commercial_terms_reference",
    "commercial_terms_verified_at","capacity_verified_at",
    "delivery_verified_at","niche","metro","destination_phone",
    "webhook_url","daily_cap","calls_today","per_lead_rate",
    "base_payout","priority",
))


def fetch_all_buyers(
    request=request_json,
    *,
    page_size: int = 1000,
    max_rows: int = 10000,
) -> list[dict]:
    size = max(1, min(int(page_size), 1000))
    cap = max(size, min(int(max_rows), 50000))
    rows: list[dict] = []
    offset = 0
    while offset < cap:
        params = urllib.parse.urlencode({
            "select": SELECT,
            "order": "created_at.desc,id.desc",
            "limit": size,
            "offset": offset,
        })
        page = request("GET", f"/rest/v1/buyers?{params}") or []
        if not isinstance(page, list):
            raise RuntimeError("buyer projection must be a list")
        rows.extend(row for row in page if isinstance(row, dict))
        if len(page) < size:
            break
        offset += size
    return rows[:cap]


def main() -> int:
    rows = fetch_all_buyers()
    payload = summarize_buyer_capacity(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUT)
    print(json.dumps({
        key: payload[key]
        for key in (
            "buyers_seen","status_active","is_active_true",
            "commercially_activated","reviewed","terms_verified",
            "capacity_verified","delivery_verified","fully_activated",
            "highest_priority_blocker","allocation_ready",
        )
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
