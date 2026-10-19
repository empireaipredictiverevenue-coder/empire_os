"""Offline code-edge review: no DB, service control, external HTTP or mail."""
import argparse
import json
from pathlib import Path

from empire_os.revenue_data_fabric_edges import inspect_code_edges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    if not args.read_only:
        raise SystemExit("READ_ONLY_REQUIRED")
    root = Path(__file__).resolve().parents[1]
    report = inspect_code_edges(root)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
