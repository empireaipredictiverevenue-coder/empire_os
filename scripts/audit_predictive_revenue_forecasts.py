#!/usr/bin/env python3
"""Source inventory only; no DB or revenue-recognition operations."""
import argparse
import json
from pathlib import Path
from empire_os.predictive_revenue_forecast_separation import write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="/srv/empire_os/runtime")
    parser.add_argument("--output", default="/srv/empire_os/runtime/predictive_revenue_control/forecast_separation_latest.json")
    args = parser.parse_args()
    result = write_report(Path(args.runtime), Path(args.output))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
