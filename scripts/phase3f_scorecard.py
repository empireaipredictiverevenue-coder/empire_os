#!/usr/bin/env python3
"""Print the canonical Phase 3F commercial figures from Supabase Postgres."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.outcome_role_transport import (
    OutcomeTransportError,
    PostgresOutcomeRpc,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire Phase 3F commercial scorecard")
    p.add_argument("--days", type=int, default=30)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.days < 1 or args.days > 3650:
        raise ValueError("days must be 1-3650")
    dsn = os.getenv("EMPIRE_OUTCOME_READER_DSN", "").strip()
    if not dsn:
        raise ValueError("EMPIRE_OUTCOME_READER_DSN is required")

    rpc = PostgresOutcomeRpc(dsn, "empire_outcome_reader")
    result = rpc(
        "get_phase3f_commercial_scorecard",
        {"p_days": args.days},
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OutcomeTransportError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
