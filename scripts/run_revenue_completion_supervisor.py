#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.revenue_completion_supervisor import build_snapshot, write_snapshot


def main() -> int:
    payload = build_snapshot()
    path = write_snapshot(payload=payload)
    print(json.dumps({
        "ok": True,
        "path": str(path),
        "tam_state": payload["tam"]["state"],
        "tam_operational_state": payload["tam"]["operational_state"],
        "tam_canonical_runtime_available": payload["tam_runtime"]["available"],
        "tam_runtime_reason": payload["tam_runtime"]["reason_code"],
        "tam_next_evidence_task": payload["tam_next_evidence_task"],
        "genuine_review_ready_count": (
            payload["buyers"]["genuine_review_ready_count"]
        ),
        "next_action": payload["next_action"],
        "opportunity_handoffs_reviewed": payload["canonical_opportunity_handoffs"]["records_reviewed"],
        "canonical_handoffs_ready": payload["canonical_opportunity_handoffs"]["handoff_ready_count"],
        "next_opportunity_handoff_action": (
            payload["canonical_opportunity_handoffs"]["items"][0]["next_action"]
            if payload["canonical_opportunity_handoffs"]["items"] else None
        ),
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
