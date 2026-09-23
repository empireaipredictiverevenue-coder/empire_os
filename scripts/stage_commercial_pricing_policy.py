#!/usr/bin/env python3
"""Prepare or stage founder-approved commercial pricing versions.

Default mode is dry-run and performs no database mutation. Apply mode requires
an explicit founder approval reference and changes proposal basis source_type
from founder_approval_required to founder_approved before invoking the governed
proposal RPC.

This script never verifies a version; independent catalog verification remains
separate.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from empire_os.commercial_pricing_policy import (
    LAUNCH_PRICING,
    build_launch_pricing_proposal,
)
from empire_os.qualification_worker_v2 import request_json


def _rpc_payload(
    row: dict[str, Any],
    *,
    approval_reference: str,
) -> dict[str, Any]:
    return {
        "p_product_code": row["product_code"],
        "p_billing_model": row["billing_model"],
        "p_currency": row["currency"],
        "p_price_basis": row["price_basis"],
        "p_acquisition_cost_basis": row["acquisition_cost_basis"],
        "p_fulfilment_cost_basis": row["fulfilment_cost_basis"],
        "p_margin_policy": row["margin_policy"],
        "p_provenance": {
            "source": "founder_approved_launch_pricing_policy",
            "policy_reference": approval_reference,
            "actual_revenue": False,
            "market_benchmark_date": "2026-09-23",
            "market_benchmarks": [
                "https://ahrefs.com/pricing",
                (
                    "https://www.semrush.com/kb/"
                    "1547-seo-toolkit-pricing-and-plans"
                ),
                "https://www.localfalcon.com/pricing",
                "https://serpapi.com/pricing",
            ],
        },
        "p_evidence_refs": [
            approval_reference,
            "git:docs/COMMERCIAL_PRICING_LADDER_2026-09-23.md",
            "market_benchmark:official_vendor_pricing:2026-09-23",
        ],
        "p_effective_from": None,
        "p_effective_until": None,
        "p_actor": "empire_pricing_policy_stager",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply-pending",
        action="store_true",
        help="Create PENDING governed catalog versions.",
    )
    parser.add_argument(
        "--approval-reference",
        default="",
        help="Explicit founder approval reference required for apply.",
    )
    args = parser.parse_args()

    proposal = build_launch_pricing_proposal()
    products = [dict(row) for row in proposal["products"]]

    if not args.apply_pending:
        print(json.dumps({
            "mode": "DRY_RUN",
            "database_mutation": False,
            "binding_terms_created": False,
            "product_count": len(products),
            "products": products,
            "founder_approval_required": True,
            "execution_authority": "none",
        }, indent=2, sort_keys=True))
        return 0

    approval = args.approval_reference.strip()
    if not approval.startswith("founder_approval:"):
        raise SystemExit(
            "--apply-pending requires --approval-reference "
            "starting with founder_approval:"
        )

    results = []
    approved_rows = [
        policy.as_approved_dict(approval)
        for policy in LAUNCH_PRICING
    ]
    for approved in approved_rows:
        response = request_json(
            "POST",
            "/rest/v1/rpc/propose_commercial_product_version",
            payload=_rpc_payload(
                approved,
                approval_reference=approval,
            ),
        )
        results.append({
            "product_code": approved["product_code"],
            "proposal_result": response,
        })

    print(json.dumps({
        "mode": "PENDING_VERSIONS_STAGED",
        "database_mutation": True,
        "binding_terms_created": False,
        "independent_verification_required": True,
        "founder_approval_reference": approval,
        "results": results,
        "actual_revenue": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
