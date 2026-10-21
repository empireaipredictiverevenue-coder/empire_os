"""Combine public GET-only intake canary with existing tenant CRM counts."""
from __future__ import annotations

import argparse
import json

from empire_os.predictive_existing_founder_crm_bridge import run_existing_founder_crm_review
from empire_os.predictive_existing_sales_path_review import review_sales_path
from scripts.probe_first_party_sales_http_readonly import inspect


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    report = review_sales_path(inspect(), run_existing_founder_crm_review())
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
