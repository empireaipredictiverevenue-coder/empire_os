#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.predictive_revenue_enterprise_targets import (
    build_enterprise_target_review,
)

OUTPUT = Path("/srv/empire_os/runtime/predictive_revenue/enterprise_targets_latest.json")


def main() -> int:
    payload = build_enterprise_target_review()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True,
        "output": str(OUTPUT),
        "target_count": payload["target_count"],
        "status": payload["status"],
        "outreach_authorized": payload["outreach_authorized"],
        "payment_action": payload["payment_action"],
        "actual_revenue": payload["actual_revenue"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
