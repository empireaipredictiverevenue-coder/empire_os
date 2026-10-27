#!/usr/bin/env python3
"""Original EmpireOS Awin joined-programme transaction count observer."""
import argparse
import json
from empire_os.awin_publisher_transaction_counts import review

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args=parser.parse_args()
    result=review(write=args.write)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"] in (
        "AWIN_JOINED_PROGRAMME_TRANSACTION_COUNTS_OBSERVED",
        "AWIN_TRANSACTIONS_WAITING_FOR_JOINED_PROGRAMME",
    ) else 2

if __name__=="__main__":
    raise SystemExit(main())
