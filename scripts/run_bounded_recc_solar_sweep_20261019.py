"""One bounded approved UK Solar B2B source sweep, private internal research.

NO canonical EmpireDB write, no web scraping outside registered RECC member
pages, no raw-directory resale, no outreach, no payments, no private consumer
data exports. Rotates up to 40 visible member links, 8 per sweep, <=32/day.

Output: private evidence ledger and aggregate latest.json for ops only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from empire_os.recc_supply_sweep import sweep_recc_members

DEFAULT_PRIVATE_DIR = Path(
    "/srv/empire_os/runtime/lead_supply/private_recc_sweeps"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-founder-approved", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_PRIVATE_DIR)
    parser.add_argument("--max-details", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        report = sweep_recc_members(args.root, batch_size=args.max_details)
    except Exception as exc:
        report = {
            "schema_version": "empire.recc_solar_supply_sweep.v1",
            "state": "HOLD",
            "reason_type": type(exc).__name__,
            "canonical_empiredb_writes": False,
            "outbound_authorized": False,
            "execution_authority": "none",
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] in ("COMPLETED", "DAILY_SOURCE_BUDGET_EXHAUSTED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
