#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.enterprise_contact_intelligence import (
    sync_enterprise_activation,
)


ACTIVATION = Path(
    "/srv/empire_os/runtime/predictive_revenue/"
    "enterprise_activation_latest.json"
)
OUTPUT = Path(
    "/srv/empire_os/runtime/predictive_revenue/"
    "enterprise_contact_intelligence_latest.json"
)


def main() -> int:
    try:
        activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}:{str(exc)[:240]}",
            "live_outbound_send": False,
            "actual_revenue": False,
        }, indent=2, sort_keys=True))
        return 2

    if not isinstance(activation, dict):
        print(json.dumps({
            "ok": False,
            "error": "activation_root_not_object",
            "live_outbound_send": False,
            "actual_revenue": False,
        }, indent=2, sort_keys=True))
        return 2

    result = sync_enterprise_activation(activation)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUTPUT)

    print(json.dumps({
        "ok": result["error_count"] == 0,
        "proposed_review_count": result["proposed_review_count"],
        "targeted_retry_queued_count": (
            result["targeted_retry_queued_count"]
        ),
        "skipped_count": result["skipped_count"],
        "error_count": result["error_count"],
        "live_outbound_send": False,
        "actual_revenue": False,
    }, indent=2, sort_keys=True))
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
