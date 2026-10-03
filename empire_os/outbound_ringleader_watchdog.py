"""Independent watchdog for the outbound Ringleader observer heartbeat."""
from __future__ import annotations

import json
import os
from pathlib import Path

from empire_os.outbound_observer_heartbeat import (
    DEFAULT_OBSERVER_HEARTBEAT_PATH,
    evaluate_observer_heartbeat,
)


def main() -> int:
    path = Path(
        os.getenv(
            "EMPIRE_OUTBOUND_OBSERVER_HEARTBEAT_PATH",
            str(DEFAULT_OBSERVER_HEARTBEAT_PATH),
        )
    )
    max_age_minutes = int(
        os.getenv("EMPIRE_OUTBOUND_OBSERVER_MAX_AGE_MINUTES", "15")
    )
    result = evaluate_observer_heartbeat(
        path=path,
        max_age_minutes=max_age_minutes,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "CURRENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
