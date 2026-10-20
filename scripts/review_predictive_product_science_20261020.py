"""One-shot product-level scientific readiness for original EmpireOS sources."""
from __future__ import annotations
import argparse
import json
from empire_os.predictive_catalog_readiness_bridge import ProductContractHold
from empire_os.predictive_product_science_readiness import SCHEMA, review_existing_product_science


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--all-products", action="store_true")
    args = p.parse_args(argv)
    try:
        result = review_existing_product_science()
        if not args.all_products:
            result = {k: v for k, v in result.items() if k != "product_science_workbench"}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ProductContractHold, OSError, ValueError, TypeError):
        print(json.dumps({
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "ORIGINAL_PRODUCT_SCIENCE_SOURCE_HELD",
            "forecast_eligible_for_customer": False,
            "original_source_issuer_authenticated": False,
            "original_forecast_registry_readback_authenticated": False,
            "economic_memory_update_eligible": False,
            "database_writes": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
