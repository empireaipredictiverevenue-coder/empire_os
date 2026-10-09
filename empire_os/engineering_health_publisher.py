"""Persist read-only engineering health evidence for founder/agent consumption."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from empire_os.engineering_health_bridge import build_engineering_health_report


def publish(log_path: str | Path, output_path: str | Path) -> dict:
    """Write one atomic evidence snapshot; never initiate remediation."""
    result = build_engineering_health_report(log_path)
    result["observed_at"] = datetime.now(timezone.utc).isoformat()
    result["source_log"] = str(Path(log_path))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".engineering-health-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--output", default="/srv/empire_os/runtime/engineering_health/latest.json")
    args = parser.parse_args()
    report = publish(args.log, args.output)
    print(json.dumps({"healthy": report["healthy"], "regression_status": report["regression_status"],
                      "incident_count": report["incident_report"]["incident_count"],
                      "output": args.output}))
    return 0 if report["healthy"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
