"""Private read-only inventory preview from EXISTING canonical Exchange snapshot.

Shows timestamped inventory by market, evidence hold and capacity waitlist.
Not a live web endpoint, customer catalogue, binding lead purchase or full
EmpireDB census. The Founder Lead Supply API mounts this at /inventory
after its own authenticated/loopback-only release.

Example:
 python -m scripts.review_lead_exchange_live_inventory_20261019 --read-only \
  --snapshot /srv/empire_os/runtime/commercial_exchange/latest.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory

MAX_JSON_BYTES = 5_000_000


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        file = args.snapshot
        if not file.is_file() or file.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("unbounded_or_missing_exchange_snapshot")
        raw = json.loads(file.read_text(encoding="utf-8"))
        result = build_lead_exchange_live_inventory(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        result = {
            "schema_version": "empire.lead_exchange_live_inventory_preview.v1",
            "mode": "READ_ONLY_EXCHANGE_SNAPSHOT",
            "state": "HOLD",
            "reason": type(exc).__name__,
            "delivery_ready_now": 0,
            "public_inventory_claim_allowed": False,
            "outbound_authorized": False,
            "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "FRESH_CANONICAL_SNAPSHOT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
