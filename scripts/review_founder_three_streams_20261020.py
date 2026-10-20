"""A single read-only founder control checkpoint for three working chats.

Sources only: existing 5-minute Ops Control snapshot and checked-in owner
handoffs. No CRM lookup, outbound, payments, new jobs or model calls.
Historical/stale/malformed snapshots fail closed and cannot become sales.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "empire.founder.three_stream_checkpoint.v1"
OPS_SCHEMA = "empire.ops_control_cycle.v1"
FIRST_SALE_SCHEMA = "empire.commercial.first_sale_live_conversion_observer.v1"
OPS_RELATIVE = Path("runtime/ops_control/latest.json")
MAX_SNAPSHOT_BYTES = 2_000_000
MAX_SNAPSHOT_AGE_SECONDS = 1800

OWNER_REFERENCES = {
    "revenue_buyers": (
        "docs/commercial/FIRST_SALE_LIVE_SOURCE_OPS_INTEGRATION_20261020.md",
        "docs/commercial/FOUNDER_SINGLE_ORDER_READER_PROVISIONED_20261020.md",
        "docs/commercial/ADAPTIVE_SALES_DIRECTOR_EVIDENCE_HANDOFF_20261020.md",
    ),
    "website_growth": (
        "docs/commercial/DIRECT_BSC_INDEPENDENT_FIRST_BUYER_GATES_20261020.md",
        "docs/commercial/FIRST_SALE_LIVE_SOURCE_OPS_INTEGRATION_20261020.md",
    ),
    "empireos_core": (
        "docs/commercial/OPS_CONTROL_ADAPTIVE_COMMERCIAL_MEMORY_HANDOFF_20261020.md",
        "docs/handoffs/EMPIRE_AI_REVENUE_FIRST_MASTER_GIT_CLOSEOUT_20261017.md",
    ),
}


def _original_ops(root: Path, now: datetime) -> tuple[dict | None, str]:
    src = root / OPS_RELATIVE
    try:
        if src.is_symlink() or not src.is_file() or src.stat().st_size > MAX_SNAPSHOT_BYTES:
            return None, "OPS_SOURCE_UNAVAILABLE"
        source = json.loads(src.read_text(encoding="utf-8"))
        if (
            not isinstance(source, dict)
            or source.get("schema_version") != OPS_SCHEMA
            or source.get("mode") != "OBSERVE"
            or type(source.get("healthy")) is not bool
        ):
            return None, "OPS_SOURCE_UNTRUSTED"
        timestamp = datetime.fromisoformat(str(source.get("observed_at")).replace("Z", "+00:00"))
        if timestamp.utcoffset() is None:
            return None, "OPS_SOURCE_UNTRUSTED"
        age = (now.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
        if age < -120 or age > MAX_SNAPSHOT_AGE_SECONDS:
            return None, "OPS_SNAPSHOT_STALE"
        return source, "FRESH_ORIGINAL_OPS_SNAPSHOT"
    except (OSError, ValueError, TypeError, OverflowError):
        return None, "OPS_SOURCE_UNAVAILABLE_OR_INVALID"


def _original_first_sale(ops: Mapping[str, Any]) -> dict | None:
    sale = ops.get("first_sale_conversion_readiness")
    if (
        not isinstance(sale, dict)
        or sale.get("schema_version") != FIRST_SALE_SCHEMA
        or sale.get("mode") != "OBSERVE"
        or sale.get("execution_authority") != "none"
        or sale.get("outbound_sent") is not False
        or sale.get("payment_action") is not False
        or sale.get("database_writes") is not False
        or sale.get("canonical_order_or_settlement_evidence_checked") is not False
        or sale.get("verified_first_sale") is not None
        or sale.get("recognized_revenue_cents") is not None
    ):
        # The read-only FIRST SALE observer cannot itself verify buyer
        # settlements. Unexpected positive claims must never be propagated.
        return None
    counts = sale.get("canonical_sales_acquisition_counts")
    if not isinstance(counts, dict):
        return None
    keys = (
        "commercial_acquisition_rows", "predictive_acquisition_rows",
        "sales_acquisition_rows", "distinct_sales_prospects",
        "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
        "founder_binding_exact_one_rows",
        "founder_binding_missing_or_ambiguous_rows",
    )
    if any(type(counts.get(k)) is not int or not 0 <= counts[k] <= 20_000_000 for k in keys):
        return None
    n = counts["sales_acquisition_rows"]
    if (
        counts["commercial_acquisition_rows"] + counts["predictive_acquisition_rows"] != n
        or any(counts[k] > n for k in keys if k not in {
            "commercial_acquisition_rows", "predictive_acquisition_rows",
            "sales_acquisition_rows",
        })
        or counts["founder_binding_exact_one_rows"] +
           counts["founder_binding_missing_or_ambiguous_rows"] != n
    ):
        return None
    status = sale.get("status")
    if n == 0 and status != "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES":
        return None
    if n > 0 and status not in {
        "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED",
        "FIRST_PARTY_ENQUIRY_TO_FOUNDER_BINDING_HOLD",
    }:
        return None
    asset = sale.get("legacy_buy_ui_manifest_integrity_status")
    route = sale.get("public_conversion_route_status")
    if asset not in {
        "LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD",
        "LEGACY_BUY_UI_PINNED_ASSETS_AND_HTML_VERIFIED",
        "LEGACY_BUY_UI_MANIFEST_NOT_CHECKED",
    } or route not in {
        "PUBLIC_CONVERSION_GET_ROUTES_PRESENT_POST_UNTESTED",
        "PUBLIC_CONVERSION_ROUTE_REVIEW_REQUIRED",
        "PUBLIC_CONVERSION_GET_ROUTES_NOT_CHECKED",
    }:
        return None
    return {"first_party_sales_enquiry_count": n,
            "site_route_status": route,
            "buy_ui_release_status": asset}


def build_checkpoint(*, root: Path, now: datetime) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware read-only review required")
    ops, source_status = _original_ops(root, now)
    sale = _original_first_sale(ops) if ops is not None else None
    counts_known = sale is not None
    zero = counts_known and sale["first_party_sales_enquiry_count"] == 0
    positive = counts_known and sale["first_party_sales_enquiry_count"] > 0
    asset_held = counts_known and sale["buy_ui_release_status"] == (
        "LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD"
    )
    route_held = counts_known and sale["site_route_status"] == (
        "PUBLIC_CONVERSION_ROUTE_REVIEW_REQUIRED"
    )
    healthy = ops.get("healthy") if ops is not None else None
    topics = [
        {
            "chat": "Revenue & Buyers",
            "lane": "revenue_buyers",
            "current_state": (
                "FIRST_PARTY_ENQUIRY_OWNER_REVIEW" if positive
                else "ZERO_RECORDED_FIRST_PARTY_SALES_ENQUIRIES" if zero
                else "CANONICAL_SALES_EVIDENCE_UNAVAILABLE"
            ),
            "verified_first_party_sales_enquiries": (
                sale["first_party_sales_enquiry_count"] if counts_known else None
            ),
            "current_revenue_or_settlement_verified_by_this_checkpoint": False,
            "next_action": (
                "EXISTING_SALES_CRM_OWNER_REVIEW_REAL_OPTED_IN_REQUEST" if positive
                else "EXISTING_WEBSITE_AND_SALES_OWNER_CONVERT_REAL_FIRST_PARTY_VISIT" if zero
                else "REPAIR_EXISTING_FIRST_PARTY_EVIDENCE_READER"
            ),
            "completion_proof": "ORIGINAL_CUSTOMER_ORDER_ACCEPTED_TERMS_SETTLEMENT_COSTS",
            "original_handoffs": list(OWNER_REFERENCES["revenue_buyers"]),
        },
        {
            "chat": "Website & Growth",
            "lane": "website_growth",
            "current_state": (
                "PUBLIC_CONVERSION_ROUTE_HOLD" if route_held
                else "CHECKOUT_RELEASE_HTML_PROVENANCE_HOLD" if asset_held
                else "WEBSITE_CONVERSION_SOURCE_REVIEW_REQUIRED" if not counts_known
                else "NO_RECORDED_WEBSITE_ROUTE_OR_HTML_HOLD_IN_OPS"
            ),
            "public_get_routes_status": sale["site_route_status"] if counts_known else None,
            "legacy_buy_html_release_status": sale["buy_ui_release_status"] if counts_known else None,
            "next_action": (
                "EXISTING_WEBSITE_OWNER_REPAIR_PUBLIC_CONVERSION_ROUTE" if route_held
                else "EXISTING_WEBSITE_OWNER_REVIEW_CURRENT_BUILD_AND_VERSIONED_HTML_RECEIPT" if asset_held
                else "CHECK_ORIGINAL_WEBSITE_RELEASE_RECEIPTS"
            ),
            "completion_proof": "INDEPENDENT_CURRENT_SITE_BUILD_RECEIPT_AND_BUY_CHECKOUT_CANARY",
            "original_handoffs": list(OWNER_REFERENCES["website_growth"]),
        },
        {
            "chat": "EmpireOS Core & Operations",
            "lane": "empireos_core",
            "current_state": (
                "OPS_RUNNING_WITH_COMMERCIAL_HOLDS" if healthy is True
                else "OPS_REVIEW_REQUIRED" if healthy is False
                else "OPS_SOURCE_STALE_OR_UNAVAILABLE"
            ),
            "ops_healthy_on_original_snapshot": healthy,
            "next_action": (
                "PRESERVE_EXISTING_OPS_TIMER_AND_OWNER_ISOLATION" if healthy is True
                else "EXISTING_OPS_OWNER_REVIEW_ACTIVE_FINDINGS" if healthy is False
                else "EXISTING_OPS_OWNER_REPAIR_ORIGINAL_SNAPSHOT"
            ),
            "completion_proof": "SOURCE_BACKED_DEPLOYED_RELEASE_WITH_OWNER_TESTS_AND_NO_DIRTY_COLLISIONS",
            "original_handoffs": list(OWNER_REFERENCES["empireos_core"]),
        },
    ]
    return {
        "schema_version": SCHEMA,
        "as_of_utc": now.astimezone(timezone.utc).isoformat(),
        "original_ops_state": source_status,
        "original_ops_observed_at": (
            ops.get("observed_at") if ops is not None else None
        ),
        "stream_count": 3,
        "streams": topics,
        "parked_into_these_streams": {
            "revenue_buyers": ["CRM", "buyer follow-ups", "data brokerage", "Finance OS", "BSC settlement"],
            "website_growth": ["flagship Three.js", "SEO/AEO/GEO", "Search Analytics", "YouTube media"],
            "empireos_core": ["ASTRA", "Predictive Cloud", "A2A", "coding agents", "infrastructure/recovery"],
        },
        "existing_user_chats_deleted": False,
        "chat_closure_is_user_interface_action": True,
        "production_data_mutated": False,
        "buyer_outreach_sent": False,
        "payment_or_revenue_recorded": False,
        "new_scheduled_jobs_created": False,
        "scope": "CONSOLIDATED_CONTROL_OBSERVE_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Founder 3-chat read-only checkpoint")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    args = parser.parse_args(argv)
    if not args.read_only:
        parser.error("--read-only is required; no mutations supported")
    checkpoint = build_checkpoint(root=args.root, now=datetime.now(timezone.utc))
    if args.format == "json":
        print(json.dumps(checkpoint, sort_keys=True))
    else:
        print("# Empire AI — Three-Chat Current Control\n")
        print("Original Ops:", checkpoint["original_ops_state"],
              "at", checkpoint["original_ops_observed_at"] or "unknown")
        for stream in checkpoint["streams"]:
            print("\n##", stream["chat"])
            print("Status:", stream["current_state"])
            print("Next:", stream["next_action"])
            print("Closure proof:", stream["completion_proof"])
        print("\nNo chats deleted, no orders or payments created.")
    return 0 if checkpoint["original_ops_state"] == "FRESH_ORIGINAL_OPS_SNAPSHOT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
