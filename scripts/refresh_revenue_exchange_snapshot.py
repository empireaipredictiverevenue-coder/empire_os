#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.revenue_exchange_snapshot import (
    build_revenue_exchange_live_snapshot,
    write_revenue_exchange_live_snapshot,
)
from empire_os.revenue_exchange_transport import PostgresRevenueExchangeReader
from empire_os.runtime_env import load_runtime_env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    env = load_runtime_env("/etc/empire_os.env", required=("EMPIREDB_DSN",))
    reader = PostgresRevenueExchangeReader(env["EMPIREDB_DSN"])
    rows = reader(limit=args.limit)
    payload = build_revenue_exchange_live_snapshot(rows)
    output = write_revenue_exchange_live_snapshot(args.repo_root, payload)
    print(json.dumps({
        "ok": True,
        "output": str(Path(output)),
        "market_count": payload["market_count"],
        "invalid_row_count": payload["invalid_row_count"],
        "blockers": payload["blockers"],
        "read_only": True,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
