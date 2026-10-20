"""One-shot least privilege Predictive Revenue catalogue/SKU readiness inspection."""
from __future__ import annotations

import argparse
import json

from empire_os.predictive_catalog_readiness_bridge import (
    ProductContractHold, review_existing_local_catalogue, SCHEMA,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--all-products", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = review_existing_local_catalogue()
        if not args.all_products:
            report = {k: v for k, v in report.items() if k != "products"}
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ProductContractHold, OSError, ValueError, TypeError):
        print(json.dumps({
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "ORIGINAL_CATALOGUE_SOURCE_HELD",
            "product_count": None,
            "source_root_custody_verified": False,
            "source_original_db_receipt_authenticated": False,
            "forecasts_computed": False,
            "production_activated": False,
            "database_writes": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
