#!/usr/bin/env python3
"""Original Predictive Revenue audit and optional authenticated source preflight."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from empire_os.predictive_revenue_forecast_separation import write_report
from empire_os.predictive_revenue_source_preflight import review_authenticated_sources


def _save_report(destination: Path, payload: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="/srv/empire_os/runtime")
    parser.add_argument("--output", default="/srv/empire_os/runtime/predictive_revenue_control/forecast_separation_latest.json")
    parser.add_argument("--authenticated-source-preflight", action="store_true")
    args = parser.parse_args()
    if args.authenticated_source_preflight:
        result = review_authenticated_sources(
            tenant_id=os.environ.get("EMPIRE_PREDICTIVE_TENANT_ID"),
            registry_dsn=os.environ.get("EMPIRE_PREDICTIVE_REGISTRY_READER_DSN"),
            census_dsn=os.environ.get("EMPIRE_PREDICTIVE_CENSUS_READER_DSN"),
            as_of=datetime.now(timezone.utc),
        )
        destination = Path(args.output)
        if str(destination) == "/srv/empire_os/runtime/predictive_revenue_control/forecast_separation_latest.json":
            destination = destination.with_name("authenticated_source_preflight_latest.json")
        _save_report(destination, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if (result["registry_reader_authenticated_session"] and
                     result["census_reader_authenticated_session"]) else 2
    result = write_report(Path(args.runtime), Path(args.output))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
