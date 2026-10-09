#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.buyer_supply_policy import (
    lead_smart_confirmed_roofing_policy,
)

from empire_os.lead_smart_coverage_reader import (
    change_intelligence,
    freshness,
    load_snapshot,
    payout_contract_drift,
    rank_observed_zips,
)

from empire_os.lead_smart_predictive_revenue_adapter import (
    realised_outcome_feature_contract,
)


OUT = Path(
    "runtime/revenue/lead_smart/"
    "coverage/intelligence/latest.json"
)


def main() -> int:
    snapshot = load_snapshot()

    now = datetime.now(timezone.utc)

    policy = (
        lead_smart_confirmed_roofing_policy(
            source_ref="gmail:1a10c6b2530f2951"
        )
    )

    routing = policy["routing"]

    canonical_min = float(
        routing["observed_payout_min"]
    )

    canonical_max = float(
        routing["observed_payout_max"]
    )

    freshness_state = freshness(
        snapshot,
        now=now,
    )

    result = {
        "schema_version":
            "empire.lead_smart."
            "coverage_intelligence.v1",

        "mode": "OBSERVE",

        "generated_at":
            now.isoformat(),

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "freshness":
            freshness_state,

        "coverage": {
            "row_count":
                snapshot["coverage"][
                    "row_count"
                ],

            "unique_zip_count":
                snapshot["coverage"][
                    "unique_zip_count"
                ],

            "source_hash":
                snapshot["source_hash"],
        },

        "commercial_contract": {
            "offer_screen_min":
                canonical_min,

            "offer_screen_max":
                canonical_max,

            "payout_model":
                routing["payout_model"],

            "payout_currency":
                routing["payout_currency"],

            "rtb_enabled":
                routing["rtb_enabled"],
        },

        "payout_contract_drift":
            payout_contract_drift(
                snapshot,
                canonical_min=canonical_min,
                canonical_max=canonical_max,
            ),

        "coverage_change":
            change_intelligence(
                snapshot
            ),

        "highest_observed_payout_priors":
            rank_observed_zips(
                snapshot,
                limit=25,
                now=now,
            ),

        "predictive_calibration":
            realised_outcome_feature_contract(),

        "prediction_state": {
            "payable_probability_calibrated":
                False,

            "expected_revenue_available":
                False,

            "reason":
                "AWAITING_REALISED_RINGBA_OUTCOMES",
        },

        "authority": {
            "targeting_analysis_allowed":
                freshness_state[
                    "fresh_for_targeting_analysis"
                ],

            "zip_coverage_activation_verified":
                False,

            "tracking_verified":
                False,

            "routing_verified":
                False,

            "routing_enabled":
                False,

            "traffic_enabled":
                False,

            "execution_authority":
                "NONE",
        },
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUT.with_suffix(".tmp")

    payload = (
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    tmp.write_text(payload)
    tmp.replace(OUT)

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
