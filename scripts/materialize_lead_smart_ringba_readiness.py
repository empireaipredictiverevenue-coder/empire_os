#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.lead_smart_ringba_evidence import (
    evidence_contract,
)


OUT = Path(
    "runtime/revenue/lead_smart/"
    "ringba/readiness/latest.json"
)


def main() -> int:
    result = {
        "schema_version":
            "empire.lead_smart."
            "ringba_readiness.v1",

        "mode": "OBSERVE",

        "buyer": "Lead Smart",

        "vertical": "Roofing",

        "provider": "Ringba",

        "evidence_contract":
            evidence_contract(),

        "current_state": {
            "authenticated_ringba_ingress":
                "PENDING",

            "real_provider_call_event_count":
                0,

            "payable_probability_calibrated":
                False,

            "provider_payout_observed":
                False,

            "network_cash_settlement_observed":
                False,

            "recognized_revenue":
                False,

            "economic_memory_outcome_ready":
                False,
        },

        "next_evidence_required": [
            "authenticated_ringba_call_details",
            "provider_finalized_call_state",
            "call_zip",
            "route_class",
            "connected_seconds",
            "appointment_event",
            "duplicate_within_30d",
            "provider_payout_amount",
            "provider_payout_observed_at",
        ],

        "truth_boundaries": {
            "call_duration_alone_means_payable":
                False,

            "provider_payout_means_cash_settled":
                False,

            "provider_payout_means_"
            "recognized_revenue":
                False,

            "provider_payout_may_train_"
            "payability_in_shadow":
                True,

            "economic_memory_requires_"
            "canonical_terminal_outcome":
                True,
        },

        "authority": {
            "db_write":
                False,

            "revenue_recognition":
                False,

            "economic_memory_write":
                False,

            "model_weight_mutation":
                False,

            "tracking_verified_change":
                False,

            "routing_verified_change":
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

    tmp = OUT.with_suffix(
        ".tmp"
    )

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

    print(payload, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
