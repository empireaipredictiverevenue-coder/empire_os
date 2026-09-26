#!/usr/bin/env python3
"""Refresh canonical Market Sweeps / Revenue GPS snapshot."""
from __future__ import annotations

import json
from pathlib import Path

from empire_os.market_sweep_revenue_gps import (
    fetch_market_sweep_postgres,
    write_market_sweep_snapshot,
)
from empire_os.runtime_env import load_runtime_env


ROOT = Path("/srv/empire_os")


def main() -> int:
    env = load_runtime_env(
        ROOT / "runtime/secrets/intelligence_materializer.env",
        required=("EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",),
    )
    payload = fetch_market_sweep_postgres(
        env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"],
        window_days=7,
        limit=100,
    )
    path = write_market_sweep_snapshot(payload, ROOT)

    print(json.dumps({
        "ok": True,
        "path": str(path),
        "market_count": payload["market_count"],
        "commercial_demand_market_count": (
            payload["commercial_demand_market_count"]
        ),
        "competitive_evidence_market_count": (
            payload["competitive_evidence_market_count"]
        ),
        "top_research_markets": payload["research_queue"][:5],
        "execution_authority": payload["execution_authority"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
