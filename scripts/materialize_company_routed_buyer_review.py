#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.company_routed_buyer_review import (
    build_company_routed_review_queue,
)


ROOT = Path("/srv/empire_os")
SOURCE = ROOT / "runtime/hunter/buyer_deferred_enrichment.json"
OUTPUT = ROOT / "runtime/buyer_acquisition/company_routed_review_latest.json"


def main() -> int:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = [
        row
        for row in data.values()
        if isinstance(row, dict)
    ] if isinstance(data, dict) else []
    payload = build_company_routed_review_queue(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUTPUT)
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "review_ready_count": payload["review_ready_count"],
        "ambiguous_person_count": payload["ambiguous_person_count"],
        "outbound_authorized": False,
        "founder_gate_required": True,
        "output": str(OUTPUT),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
