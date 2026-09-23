#!/usr/bin/env python3
"""Verify Phase 4 Buyer Acquisition Team production automation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SAFE_SYSTEM_UNITS = (
    "empire-qualification-booster.timer",
    "empire-buyer-review-materializer.timer",
    "empire-buyer-deferred-enrichment.timer",
    "empire-buyer-capacity-readiness.timer",
    "empire-commercial-evidence-auto-verifier.timer",
    "empire-commercial-product-catalog.timer",
    "empire-commercial-exchange.timer",
    "empire-buyer-acquisition-team.timer",
    "empire-buyer-acquisition-scout.timer",
)

LIVE_EXTERNAL_UNITS = (
    "empire-outbound-governor.timer",
    "empire-outbound-followup.timer",
    "empire-voice-outbound.timer",
)

REQUIRED_ARTIFACTS = (
    "runtime/commercial_catalog/latest.json",
    "runtime/commercial_exchange/latest.json",
    "runtime/buyer_acquisition/latest.json",
    "runtime/buyer_acquisition/scout_latest.json",
    "runtime/buyer_acquisition/reconciliation_latest.json",
    "runtime/buyer_acquisition/persistence_latest.json",
    "runtime/buyer_acquisition/review_readiness_latest.json",
    "runtime/buyer_acquisition/promotion_plan_latest.json",
    "runtime/commercial_catalog/pricing_verification_latest.json",
)


def _run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode, (result.stdout or "").strip()


def _unit_state(unit: str) -> dict[str, Any]:
    enabled_rc, enabled = _run(["systemctl", "is-enabled", unit])
    active_rc, active = _run(["systemctl", "is-active", unit])
    return {
        "unit": unit,
        "enabled": enabled_rc == 0 and enabled == "enabled",
        "enabled_state": enabled or "unknown",
        "active": active_rc == 0 and active == "active",
        "active_state": active or "unknown",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    safe_units = [_unit_state(unit) for unit in SAFE_SYSTEM_UNITS]
    external_units = [_unit_state(unit) for unit in LIVE_EXTERNAL_UNITS]

    artifacts = {
        relative: (root / relative).is_file()
        for relative in REQUIRED_ARTIFACTS
    }
    buyer_plan = _read_json(root / "runtime/buyer_acquisition/latest.json")
    scout = _read_json(
        root / "runtime/buyer_acquisition/scout_latest.json"
    )
    reconciliation = _read_json(
        root / "runtime/buyer_acquisition/reconciliation_latest.json"
    )
    persistence = _read_json(
        root / "runtime/buyer_acquisition/persistence_latest.json"
    )
    review_readiness = _read_json(
        root / "runtime/buyer_acquisition/review_readiness_latest.json"
    )
    promotion_plan = _read_json(
        root / "runtime/buyer_acquisition/promotion_plan_latest.json"
    )
    pricing = _read_json(
        root / "runtime/commercial_catalog/pricing_verification_latest.json"
    )
    exchange = _read_json(root / "runtime/commercial_exchange/latest.json")

    safe_automation_ready = all(
        row["enabled"] and row["active"]
        for row in safe_units
    )
    live_external_automation_detected = any(
        row["enabled"] or row["active"]
        for row in external_units
    )
    artifacts_ready = all(artifacts.values())

    plan_safe = (
        buyer_plan.get("mode") == "OBSERVE"
        and buyer_plan.get("outbound_sent") is False
        and buyer_plan.get("execution_authority") == "none"
        and (
            buyer_plan.get("automation") or {}
        ).get("live_outbound_send") is False
    )
    scout_safe = (
        scout.get("mode") == "OBSERVE"
        and scout.get("database_write_performed") is False
        and scout.get("outbound_sent") is False
        and scout.get("execution_authority") == "none"
    )
    reconciliation_safe = (
        reconciliation.get("mode") == "OBSERVE"
        and reconciliation.get("database_write_performed") is False
        and reconciliation.get("automatic_ingest_authorized") is False
        and reconciliation.get("outbound_sent") is False
        and reconciliation.get("execution_authority") == "none"
    )
    persistence_safe = (
        persistence.get("mode") == "OBSERVE"
        and persistence.get("holding_area_only") is True
        and persistence.get("canonical_promotion_performed") is False
        and persistence.get("automatic_ingest_authorized") is False
        and persistence.get("outbound_sent") is False
        and persistence.get("execution_authority") == "none"
    )
    review_readiness_safe = (
        review_readiness.get("mode") == "OBSERVE"
        and review_readiness.get("canonical_promotion_performed") is False
        and review_readiness.get("outbound_sent") is False
        and review_readiness.get("execution_authority") == "none"
    )
    promotion_plan_safe = (
        promotion_plan.get("mode") == "OBSERVE"
        and promotion_plan.get("database_write_performed") is False
        and promotion_plan.get("canonical_promotion_performed") is False
        and promotion_plan.get("buy_signal_score_policy") == "UNKNOWN_NULL"
        and promotion_plan.get("outbound_sent") is False
        and promotion_plan.get("execution_authority") == "none"
    )
    pricing_safe = (
        pricing.get("pricing_matches_approved_policy") is True
        and int(pricing.get("drift_count") or 0) == 0
        and pricing.get("execution_authority") == "none"
    )
    exchange_safe = (
        exchange.get("mode") == "OBSERVE"
        and exchange.get("automatic_external_delivery") is False
        and exchange.get("execution_authority") == "none"
    )

    production_ready = all((
        safe_automation_ready,
        artifacts_ready,
        plan_safe,
        scout_safe,
        reconciliation_safe,
        persistence_safe,
        review_readiness_safe,
        promotion_plan_safe,
        pricing_safe,
        exchange_safe,
    ))

    payload = {
        "schema_version": "empire.buyer_acquisition_automation.v1",
        "production_ready": production_ready,
        "safe_internal_automation_ready": safe_automation_ready,
        "required_artifacts_present": artifacts_ready,
        "buyer_plan_safe": plan_safe,
        "buyer_scout_safe": scout_safe,
        "buyer_scout_reconciliation_safe": reconciliation_safe,
        "buyer_scout_persistence_safe": persistence_safe,
        "buyer_scout_review_readiness_safe": review_readiness_safe,
        "buyer_scout_promotion_plan_safe": promotion_plan_safe,
        "pricing_policy_safe": pricing_safe,
        "commercial_exchange_safe": exchange_safe,
        "live_external_automation_detected": (
            live_external_automation_detected
        ),
        "live_external_automation_is_separate_gate": True,
        "safe_internal_units": safe_units,
        "live_external_units": external_units,
        "artifacts": artifacts,
        "buyer_pool_count": len(buyer_plan.get("buyer_pools") or []),
        "demand_gap_count": int(
            buyer_plan.get("demand_gap_count") or 0
        ),
        "product_demand_count": int(
            buyer_plan.get("product_demand_count") or 0
        ),
        "sellable_product_demand_count": int(
            buyer_plan.get("sellable_product_demand_count") or 0
        ),
        "scout_candidate_count": int(
            scout.get("candidate_count") or 0
        ),
        "explicit_direct_buyer_candidate_count": int(
            scout.get("explicit_direct_buyer_candidate_count") or 0
        ),
        "existing_buyer_match_count": int(
            reconciliation.get("existing_buyer_count") or 0
        ),
        "existing_prospect_match_count": int(
            reconciliation.get("existing_prospect_count") or 0
        ),
        "new_external_buyer_candidate_count": int(
            reconciliation.get("new_external_candidate_count") or 0
        ),
        "persisted_holding_candidate_count": int(
            persistence.get("persisted_candidate_count") or 0
        ),
        "review_ready_candidate_count": int(
            review_readiness.get("review_ready_count") or 0
        ),
        "promotion_proposal_count": int(
            promotion_plan.get("proposal_count") or 0
        ),
        "market_validate_product_count": int(
            buyer_plan.get("market_validate_product_count") or 0
        ),
        "outbound_sent": False,
        "terms_accepted": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if production_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
