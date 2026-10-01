#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.buyer_capacity_readiness import summarize_buyer_capacity
from empire_os.buyer_allocation_repository import BuyerAllocationDataRepository
from empire_os.canonical_data_gateway import empiredb_gateway_from_environment as gateway_from_environment
from empire_os.runtime_env import load_runtime_env

ROOT = Path("/srv/empire_os")
OUT = ROOT / "runtime" / "buyer_capacity_readiness" / "latest.json"

def fetch_all_buyers(
    repository: BuyerAllocationDataRepository | None = None,
    *,
    page_size: int = 1000,
    max_rows: int = 10000,
) -> list[dict]:
    if repository is None:
        repository = BuyerAllocationDataRepository(
            gateway_from_environment(load_runtime_env("/etc/empire_os.env"))
        )
    size = max(1, min(int(page_size), 1000))
    cap = max(size, min(int(max_rows), 50000))
    rows: list[dict] = []
    offset = 0
    while offset < cap:
        page = repository.buyer_page(page_size=size, offset=offset)
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
