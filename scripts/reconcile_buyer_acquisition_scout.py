#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

from empire_os.buyer_scout_reconciliation import (
    reconcile_scout_candidates,
    write_reconciliation,
)
from empire_os.qualification_worker_v2 import request_json


def _get(path: str, params: dict[str, str]):
    return request_json(
        "GET",
        path + "?" + urllib.parse.urlencode(params),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    try:
        scout = json.loads(
            (
                root / "runtime/buyer_acquisition/scout_latest.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        scout = {}

    limit = max(1, min(int(args.limit), 5000))
    prospects = _get(
        "/rest/v1/prospects",
        {
            "select": "id,business_name,website,status,niche,metro",
            "website": "not.is.null",
            "limit": str(limit),
        },
    )
    buyers = _get(
        "/rest/v1/buyers",
        {
            "select": "id,buyer_name,website,status,is_active",
            "website": "not.is.null",
            "limit": str(limit),
        },
    )

    payload = reconcile_scout_candidates(
        scout if isinstance(scout, dict) else {},
        prospects=[
            row for row in (prospects or [])
            if isinstance(row, dict)
        ],
        buyers=[
            row for row in (buyers or [])
            if isinstance(row, dict)
        ],
    )
    write_reconciliation(root, payload)

    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "existing_buyer_count": payload["existing_buyer_count"],
        "existing_prospect_count": payload["existing_prospect_count"],
        "new_external_candidate_count": payload[
            "new_external_candidate_count"
        ],
        "database_write_performed": False,
        "automatic_ingest_authorized": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
