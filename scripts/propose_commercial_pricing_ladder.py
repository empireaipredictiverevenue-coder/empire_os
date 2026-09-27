#!/usr/bin/env python3
"""Propose the founder-approved launch pricing ladder to the governed catalog.

Dry-run is the default. --apply requires an explicit founder approval reference.
Even in apply mode this script only creates PENDING catalog versions. It does
not verify them, accept buyer terms, move funds or recognize revenue.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any

from empire_os.commercial_pricing_policy import LAUNCH_PRICING
from empire_os.qualification_worker_v2 import request_json


def build_rpc_payload(policy, approval_reference: str) -> dict[str, Any]:
    approved = policy.as_approved_dict(approval_reference)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "p_product_code": approved["product_code"],
        "p_billing_model": approved["billing_model"],
        "p_currency": approved["currency"],
        "p_price_basis": approved["price_basis"],
        "p_acquisition_cost_basis": approved["acquisition_cost_basis"],
        "p_fulfilment_cost_basis": approved["fulfilment_cost_basis"],
        "p_margin_policy": approved["margin_policy"],
        "p_provenance": {
            "source": "founder_approved_launch_pricing",
            "approval_reference": approval_reference,
            "proposal_doc": (
                "docs/COMMERCIAL_PRICING_LADDER_2026-09-23.md"
            ),
            "market_benchmark_date": "2026-09-23",
            "actual_revenue": False,
            "costs_are_policy_ceilings": True,
        },
        "p_evidence_refs": [
            approval_reference,
            "docs:COMMERCIAL_PRICING_LADDER_2026-09-23",
        ],
        "p_effective_from": now,
        "p_effective_until": None,
        "p_actor": "founder-approved-pricing-ladder",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-reference")
    args = parser.parse_args()

    reference = str(args.approval_reference or "").strip()
    if args.apply and not reference:
        parser.error("--apply requires --approval-reference")
    if args.apply and not reference.startswith("founder_approval:"):
        parser.error(
            "--approval-reference must start with founder_approval:"
        )

    if not args.apply:
        print(json.dumps({
            "mode": "DRY_RUN",
            "product_count": len(LAUNCH_PRICING),
            "products": [
                {
                    "product_code": row.product_code,
                    "billing_model": row.billing_model,
                    "unit": row.unit,
                    "amount_cents": row.amount_cents,
                    "policy_margin_bps": row.policy_margin_bps,
                }
                for row in LAUNCH_PRICING
            ],
            "database_mutation": False,
            "catalog_verification_performed": False,
            "actual_revenue": False,
        }, indent=2, sort_keys=True))
        return 0

    results = []
    for policy in LAUNCH_PRICING:
        payload = build_rpc_payload(policy, reference)
        response = request_json(
            "POST",
            "/rest/v1/rpc/propose_commercial_product_version",
            payload=payload,
        )
        results.append({
            "product_code": policy.product_code,
            "response": response,
        })

    print(json.dumps({
        "mode": "APPLY_PENDING_PROPOSALS",
        "approval_reference": reference,
        "product_count": len(results),
        "results": results,
        "catalog_verification_performed": False,
        "binding_terms_ready_claimed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
