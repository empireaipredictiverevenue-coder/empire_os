#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.buyer_scout_persistence import (
    persist_new_external_candidates,
    write_persistence,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()

    def read(relative):
        try:
            value = json.loads((root / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    scout = read("runtime/buyer_acquisition/scout_latest.json")
    reconciliation = read(
        "runtime/buyer_acquisition/reconciliation_latest.json"
    )

    payload = persist_new_external_candidates(
        scout,
        reconciliation,
        rpc_call=lambda method, path, body: request_json(
            method,
            path,
            payload=body,
        ),
    )
    write_persistence(root, payload)

    print(json.dumps({
        "ok": True,
        "persisted_candidate_count": payload[
            "persisted_candidate_count"
        ],
        "skipped_candidate_count": payload[
            "skipped_candidate_count"
        ],
        "holding_area_only": True,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
