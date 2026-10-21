"""Fast, fail-closed JEV-compatible research source triage over existing evidence.

Reuse the already-installed TypedDecisionProvider / Laya shadow interface.
Deterministic source and rights gates are authoritative. No original URLs,
titles, passages, identities or body content reach an optional model. Even a
model answer labelled EDITORIAL_REVIEW grants no source admission or actions.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite
from time import perf_counter
from typing import Any, Mapping
import json
import re

from empire_os.typed_decision_provider import (
    TypedDecisionRequest, review_typed_decision_result,
)

SCHEMA = "empire.research.jev_original_source_triage.v1"
INPUT_SCHEMA = "empire.research.official_multisector_original_candidates.v1"
LABELS = ("HOLD", "REINSPECT_SOURCE", "RIGHTS_REVIEW", "EDITORIAL_REVIEW")
SUPPORTED = {
    "ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED": "EDITORIAL_REVIEW",
    "ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED": "RIGHTS_REVIEW",
    "ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED": "REINSPECT_SOURCE",
    "ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD": "HOLD",
}
SECTORS = frozenset(("solar", "hvac", "legal", "property"))
MARKETS = frozenset(("GB", "US"))
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MAX_ROWS = 24


def triage_original_sources(
    evidence: Mapping[str, Any], *, provider: Any = None,
    max_shadow_calls: int = 0, confidence_threshold: float = 0.80,
) -> dict[str, Any]:
    """Advisory review order; model cannot change source gate or permissions."""
    if type(max_shadow_calls) is not int or not 0 <= max_shadow_calls <= 8:
        raise ValueError("bounded explicit Laya shadow-call limit required")
    if not isinstance(confidence_threshold, (int, float)) or (
        not isfinite(confidence_threshold)
        or not 0.5 <= confidence_threshold <= 1.0
    ):
        raise ValueError("invalid shadow confidence threshold")
    if max_shadow_calls and (provider is None
                             or not callable(getattr(provider, "evaluate", None))):
        raise ValueError("explicit installed typed-decision provider required")
    if not isinstance(evidence, Mapping) or evidence.get("schema_version") != INPUT_SCHEMA:
        raise ValueError("exact original-source ledger schema required")
    rows = evidence.get("rows")
    if (not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS
        or evidence.get("source_admissions") != 0
        or evidence.get("independent_editorial_signoffs") != 0
        or evidence.get("messages_or_customer_actions_sent") != 0
        or evidence.get("database_writes") is not False
        or evidence.get("money_moved") is not False):
        raise ValueError("unapproved bounded original-source ledger required")
    if evidence.get("total_exact_sources_checked") != len(rows):
        raise ValueError("original-source count mismatch")
    unique: set[str] = set()
    results: list[dict[str, Any]] = []
    attempted = 0
    started = perf_counter()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("source observation must be a record")
        sector, market, status = (
            row.get("sector"), row.get("market"), row.get("status"))
        label = row.get("label")
        if (sector not in SECTORS or market not in MARKETS
            or status not in SUPPORTED
            or not isinstance(label, str) or not re.fullmatch(r"[a-z0-9_]{3,60}", label)
            or label in unique
            or row.get("source_admitted") is not False
            or row.get("source_license_or_reuse_rights_verified") is not False
            or row.get("official_claim_independently_validated") is not False
            or row.get("editorial_owner_signed_off") is not False
            or row.get("customer_demand_verified") is not False
            or row.get("outbound_authorized") is not False
            or row.get("customer_delivery_authorized") is not False
            or row.get("db_or_finance_authorized") is not False
            or row.get("individual_property_or_person_records_fetched") != 0):
            raise ValueError("untrusted or unsafe original-source observation")
        unique.add(label)
        digest = row.get("source_body_sha256")
        observed = status != "ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD"
        if observed:
            if (not isinstance(digest, str) or not HEX64.fullmatch(digest)
                or type(row.get("source_body_bytes")) is not int
                or not 0 < row["source_body_bytes"] <= 600000):
                raise ValueError("original source checksum required")
        elif digest is not None:
            raise ValueError("held URL cannot claim inspected bytes")
        anchors = row.get("topic_anchor_count", 0)
        if (type(anchors) is not int or not 0 <= anchors <= 10000
            or (status == "ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED"
                and (anchors != 0
                     or row.get("substantive_original_passage_verified") is not False))):
            raise ValueError("invalid original-topic grounding")
        deterministic = SUPPORTED[status]
        item: dict[str, Any] = {
            "source_id_sha256": sha256(label.encode("utf8")).hexdigest(),
            "sector": sector, "market": market,
            "source_evidence_status": status,
            "deterministic_review_lane": deterministic,
            "proposed_model_lane": None,
            "model_advisory_status": "NOT_CALLED",
            "review_required": True,
            "source_admitted": False,
            "buyer_demand_verified": False,
            "outbound_authorized": False,
        }
        results.append(item)
    # Fail closed BEFORE any external/local provider interaction: the entire
    # evidence ledger must validate, including rows after the call budget.
    for row, item in zip(rows, results):
        sector, market = item["sector"], item["market"]
        status = item["source_evidence_status"]
        deterministic = item["deterministic_review_lane"]
        anchors = row.get("topic_anchor_count", 0)
        # Source-only, non-personal, numerical/enum state. No URLs, passages,
        # body, title, email, prospect ID, tenant ID, or original content.
        if (max_shadow_calls and attempted < max_shadow_calls
            and deterministic != "HOLD"):
            attempted += 1
            request = TypedDecisionRequest(
                task_key="source_quality",
                decision_schema_ref=SCHEMA,
                state_ref=item["source_id_sha256"],
                state={
                    "sector": sector, "market": market,
                    "observed_shape": status,
                    "topic_anchor_count": anchors,
                    "source_kind": row.get("source_kind"),
                    "licensed_for_reuse": False,
                    "editorial_approved": False,
                },
                allowed_labels=LABELS,
                risk_class="medium",
                instructions=(
                    "Suggest only which human evidence-review lane is useful. "
                    "This is an unapproved original-source observation; never "
                    "assume source rights, identity, buyer intent or permission."
                ),
            )
            try:
                proposed = provider.evaluate(request)
                review = review_typed_decision_result(
                    request=request, result=proposed,
                    confidence_threshold=confidence_threshold)
                if (proposed.shadow_only is not True
                    or proposed.execution_authority != "none"
                    or proposed.provider_key not in ("laya_http", "laya")
                    or not isfinite(proposed.latency_ms)):
                    raise ValueError("non-shadow or non-local Jev-compatible provider")
                item["proposed_model_lane"] = proposed.label
                item["model_advisory_status"] = (
                    "SHADOW_ESCALATE" if review["requires_escalation"]
                    else "SHADOW_COMPARISON_RECORDED"
                )
                item["provider_observed_latency_ms"] = proposed.latency_ms
                item["model_confidence"] = round(proposed.confidence, 4)
                item["model_disagrees_with_deterministic_gate"] = proposed.label != deterministic
            except Exception:
                # Fail closed on an optional model/sidecar outage. Never promote.
                item["model_advisory_status"] = "SHADOW_UNAVAILABLE_HELD"
    ms = (perf_counter()-started)*1000
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "JEV_LOCAL_SHADOW_RESEARCH_REVIEW_ONLY",
        "original_sources_reviewed": len(results),
        "deterministic_review_lane_counts": {
            label: sum(x["deterministic_review_lane"] == label for x in results)
            for label in LABELS
        },
        "shadow_model_calls_attempted": attempted,
        "local_shadow_only": True,
        "deterministic_and_shadow_elapsed_ms": round(ms, 3),
        "review_items": results,
        "source_rights_approved": 0,
        "trusted_research_sources_admitted": 0,
        "revenue_or_buyer_intent_verified": False,
        "manual_reviewer_required": True,
        "outbound_authorized": False,
        "database_writes": False,
        "customer_delivery_authorized": False,
        "external_paid_jev_api_called": False,
        "execution_authority": "none",
    }
