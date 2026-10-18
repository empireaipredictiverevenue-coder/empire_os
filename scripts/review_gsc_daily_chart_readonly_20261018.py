#!/usr/bin/env python3
"""Bounded GSC date-dimension series for later Empire-branded charts.

Use the existing Search Intelligence loopback reader; no new Google auth.
Missing days are unknown, not zero. No added traffic to page-level totals.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json

from empire_os.search_intelligence.gsc_daily_series import (
    GscDailyEvidenceHeld, read_daily,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.add_argument("--start-date",type=date.fromisoformat)
    parser.add_argument("--end-date",type=date.fromisoformat)
    args=parser.parse_args(argv)
    if bool(args.start_date)!=bool(args.end_date):
        parser.error("specify start and end dates together")
    end=args.end_date or date.today()-timedelta(days=2)
    start=args.start_date or end-timedelta(days=12)
    try:
        result=read_daily(start=start,end=end)
    except GscDailyEvidenceHeld:
        parser.error("date window must be past and 31 days or less")
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="DATE_DIMENSION_ROWS_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
