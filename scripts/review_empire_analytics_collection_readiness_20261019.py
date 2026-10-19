#!/usr/bin/env python3
"""One-shot source-health audit for future first-party Empire Analytics.

Uses only the EXISTING local Tag Intelligence monitor's bounded snapshot.
Never requests live web pages, opens a collector or enables tracking.
"""
from __future__ import annotations
import argparse
import json

from empire_os.analytics.measurement_readiness import review_existing_monitor


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args(argv)
    report=review_existing_monitor()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD" else 2

if __name__=="__main__":
    raise SystemExit(main())
