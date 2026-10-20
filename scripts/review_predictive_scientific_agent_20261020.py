"""Read-only Scientific Research Agent protocol for Predictive Revenue products."""
from __future__ import annotations

import argparse
import json

from empire_os.predictive_product_scientific_agent_review import (
    SCHEMA, ScientificProtocolHold, review_product_scientific_agent_protocol
)
from empire_os.predictive_product_science_readiness import review_existing_product_science
from empire_os.predictive_catalog_readiness_bridge import ProductContractHold


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    args = p.parse_args(argv)
    try:
        result = review_product_scientific_agent_protocol(
            science_source=review_existing_product_science()
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ScientificProtocolHold, ProductContractHold, OSError, ValueError, TypeError):
        print(json.dumps({
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "SCIENTIFIC_AGENT_PROTOCOL_SOURCE_OR_SKILL_CUSTODY_HELD",
            "existing_scientific_research_agent_skill_custody_verified": False,
            "original_forecast_experiment_registered": False,
            "customer_model_validated": False,
            "scientific_model_promotion_approved": False,
            "production_activated": False,
            "database_writes": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
