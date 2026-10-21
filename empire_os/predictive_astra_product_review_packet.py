"""Reproducible, fail-closed ASTRA GPT-6 review INPUT, never self-approval.

Uses only existing, bounded original catalogue and OBSERVE comparison records.
Product activation and independent revenue are never inferred from a price,
policy ceiling, version flag, vendor benchmark or a local source hash.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any

SCHEMA = "empire.predictive_revenue.astra_gpt6_review_input.v1"
SOURCE_SHA_LEN = 64
REVIEW_TASKS = (
    "VERIFY_EXACT_IMMUTABLE_COMMIT_AND_ORIGINAL_SOURCE_ISSUER",
    "AUDIT_TENANT_SEPARATION_AND_ORIGINAL_PREDICTION_CUSTODY",
    "REPRODUCE_SCIENTIFIC_TEMPORAL_AND_CALIBRATION_TESTS",
    "CHALLENGE_PRODUCT_SCOPE_LICENSE_DATA_RIGHTS_AND_CUSTOMER_ACCEPTANCE",
    "RECONCILE_PRICE_CURRENCY_UNIT_ORIGINAL_COSTS_AND_SETTLEMENT",
    "CHECK_VENDOR_BENCHMARK_UNIT_FEATURES_AND_REAL_CONTRACT_EQUIVALENCE",
    "ASSESS_SECURITY_MODEL_QUOTAS_ROLLBACK_AND_RECOVERY",
    "PROVIDE_EVIDENCED_PER_SKU_RISKS_AND_PRICE_JUSTIFICATION_HOLDS",
)


class AstraReviewPacketHold(ValueError):
    """Original packet evidence is missing, inconsistent or unsafe."""


def _clean_clock(stamp: Any) -> bool:
    return (type(stamp) is str and 15 <= len(stamp) <= 80
            and stamp[0:4].isdigit() and "T" in stamp)


def build_astra_product_review_packet(
    original_catalogue: Mapping[str, Any],
    comparison: Mapping[str, Any],
    *,
    snapshot_sha256: str,
) -> dict[str, Any]:
    if (not isinstance(original_catalogue, Mapping)
            or not isinstance(comparison, Mapping)
            or type(snapshot_sha256) is not str
            or len(snapshot_sha256) != SOURCE_SHA_LEN
            or any(char not in "0123456789abcdef" for char in snapshot_sha256)
            or comparison.get("catalogue_product_count") != 86
            or original_catalogue.get("product_count") != 86
            or comparison.get("original_catalogue_source_authenticated") is not False
            or comparison.get("source_approval_is_independent_customer_acceptance") is not False
            or comparison.get("astra_gpt6_independent_review") != "NOT_EXECUTED"
            or comparison.get("price_change_authority") != "none"
            or comparison.get("commercial_predicted_outcomes_verified") is not False
            or comparison.get("approved_cost_ceiling_scenario_is_actual_margin") is not False):
        raise AstraReviewPacketHold("source or reviewer authority inconsistent")
    originals=original_catalogue.get("products")
    rows=comparison.get("products")
    if (type(originals) is not list or type(rows) is not list
            or len(originals) != 86 or len(rows) != 86):
        raise AstraReviewPacketHold("original inventory missing")
    from_original={}
    for p in originals:
        if type(p) is not dict or type(p.get("product_code")) is not str:
            raise AstraReviewPacketHold("original product identity invalid")
        code=p["product_code"]
        if code in from_original:
            raise AstraReviewPacketHold("duplicate original product identity")
        from_original[code]=p
    from_compare={}
    for r in rows:
        if type(r) is not dict or type(r.get("product_code")) is not str:
            raise AstraReviewPacketHold("comparison product identity invalid")
        code=r["product_code"]
        if code in from_compare:
            raise AstraReviewPacketHold("duplicate comparison product")
        from_compare[code]=r
    if set(from_original) != set(from_compare):
        raise AstraReviewPacketHold("comparison is not same source inventory")

    counts: Counter[str] = Counter()
    packet_rows=[]
    for code in sorted(from_original):
        p=from_original[code]
        row=from_compare[code]
        basis=p.get("price_basis")
        policy=row.get("founder_policy_cost_ceiling_scenario")
        if (not isinstance(basis, Mapping) or not isinstance(policy, Mapping)
                or p.get("product_family")!=row.get("product_family")
                or p.get("product_name")!=row.get("product_name")
                or basis.get("amount_cents")!=row.get("catalogue_listed_price_minor_units")
                or basis.get("unit")!=row.get("catalogue_unit")
                or basis.get("currency")!=row.get("catalogue_currency")
                or type(p.get("active")) is not bool
                or type(p.get("binding_terms_ready")) is not bool
                or type(p.get("actual_revenue")) is not bool
                or not isinstance(p.get("readiness_blockers"),list)
                or any(type(s) is not str or len(s)>120
                       for s in p["readiness_blockers"])
                or p.get("catalog_state") not in ("VERIFIED","UNKNOWN")
                or p.get("version_state") not in ("VERIFIED","PENDING")
                or p.get("actual_revenue") is not False
                or row.get("customer_value_independently_measured") is not False
                or row.get("evidence_backed_price_justified") is not False
                or row.get("terms_independently_authenticated") is not False
                or row.get("economic_delivery_cost_verified") is not False
                or row.get("automatic_price_changes_authorized") is not False):
            raise AstraReviewPacketHold("original SKU contradicts source hold")

        conflict=row.get("catalogue_price_original_custody")=="LEGACY_CONFLICT_NEEDS_FOUNDER_RESOLUTION"
        candidate=None
        if conflict:
            if (basis.get("state")!="CONFLICT"
                    or type(basis.get("metadata_candidate_cents")) is not int
                    or type(basis.get("pricing_candidate_cents")) is not int
                    or basis["metadata_candidate_cents"]<=0
                    or basis["pricing_candidate_cents"]<=0
                    or basis["metadata_candidate_cents"]==basis["pricing_candidate_cents"]
                    or not _clean_clock(basis.get("metadata_updated_at"))
                    or not _clean_clock(basis.get("pricing_updated_at"))):
                raise AstraReviewPacketHold("conflicted history not independently resolvable")
            candidate={
                "metadata_candidate_minor_units": basis["metadata_candidate_cents"],
                "metadata_observed_at": basis["metadata_updated_at"],
                "pricing_candidate_minor_units": basis["pricing_candidate_cents"],
                "pricing_observed_at": basis["pricing_updated_at"],
                "candidate_difference_minor_units": abs(
                    basis["metadata_candidate_cents"]-basis["pricing_candidate_cents"]
                ),
                "either_candidate_approved": False,
            }
            counts["price_conflicts"] += 1
        if p["catalog_state"]!="VERIFIED" or p["version_state"]!="VERIFIED":
            counts["catalogue_or_version_unverified"]+=1
        if p["active"] and (p["catalog_state"]!="VERIFIED" or p["version_state"]!="VERIFIED"):
            counts["active_but_unverified_catalogue"]+=1
        if not p["active"]:
            counts["inactive"]+=1
        if p["binding_terms_ready"]:
            counts["source_reported_binding_terms_ready"]+=1
        if policy.get("policy_ceiling_scenario_available") is True:
            counts["scenario_cost_policies"]+=1
        if not row.get("competitor_categories"):
            counts["missing_vendor_reference"]+=1
        if basis.get("source_type")=="founder_approved":
            counts["founder_price_source"]+=1
        blockers=sorted(set(p["readiness_blockers"]))
        item={
            "product_code": code,
            "product_family": p["product_family"],
            "product_name": p["product_name"],
            "product_active_original_snapshot": p["active"],
            "catalogue_original_state": p["catalog_state"],
            "version_original_state": p["version_state"],
            "original_readiness_blockers": blockers,
            "original_terms_ready_flag_not_legal_acceptance": p["binding_terms_ready"],
            "price_source_custody": row["catalogue_price_original_custody"],
            "listed_price_minor_units": row["catalogue_listed_price_minor_units"],
            "currency": row["catalogue_currency"],
            "billing_unit": row["catalogue_unit"],
            "conflicting_historical_prices_research_only": candidate,
            "internal_cost_ceiling_scenario_available": policy["policy_ceiling_scenario_available"],
            "internal_cost_ceiling_scenario_pass": policy["policy_ceiling_passes"],
            "actual_delivery_cost_verified": False,
            "actual_customer_value_verified": False,
            "original_forecast_outcome_pair_verified": False,
            "vendor_adjacent_reference_count": len(row["competitor_categories"]),
            "vendor_contract_or_feature_parity_verified": False,
            "review_disposition": "EVIDENCE_HOLD_NO_CUSTOMER_APPROVAL",
        }
        packet_rows.append(item)
    if (counts["price_conflicts"] != 5
            or counts["catalogue_or_version_unverified"] != 60
            or counts["active_but_unverified_catalogue"] != 9
            or counts["scenario_cost_policies"] != 26
            or counts["founder_price_source"] != 35
            or counts["missing_vendor_reference"] != 25
            or counts["source_reported_binding_terms_ready"] != 26):
        raise AstraReviewPacketHold("review packet totals are not original catalogue")
    payload={
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "ASTRA_GPT6_INDEPENDENT_REVIEW_INPUT_READY_NOT_EXECUTED",
        "input_original_snapshot_sha256": snapshot_sha256,
        "source_inventory_count": 86,
        "reviewed_source_counts": dict(sorted(counts.items())),
        "challenge_requirements": list(REVIEW_TASKS),
        "products": packet_rows,
        "not_proof_of_db_source_authenticity": True,
        "cannot_review_model_accuracy_without_real_outcomes": True,
        "review_authority": "none",
        "independent_astra_gpt6_invocation_executed": False,
        "independent_reviewer_signature_verified": False,
        "prices_approved_by_this_packet": False,
        "customer_forecasts_or_revenue_verified": False,
        "live_customer_product_activation": False,
        "model_weights_changed": False,
        "database_writes": False,
        "execution_authority": "none",
    }
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False)
    payload["review_packet_sha256"]=sha256(canonical.encode()).hexdigest()
    return payload
