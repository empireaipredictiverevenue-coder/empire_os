"""One-call TypeSafe Jev SEO shadow inference, via Empire's EXISTING OpenRouter.

Never called by the request-serving Search API. No automatic loops, publishing,
outbound, canonical writes, billable customer data or provider fallback.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Callable, Mapping

import requests

from .department_snapshot import read_department_snapshot
from .jev_department_review import review_jev_department_portfolio

SCHEMA = "empire.search.jev_real_one_shot_pilot.v1"
ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
MAX_COST_USD = 0.0005
MAX_INPUT_TOKENS = 3000
MAX_STATE_BYTES = 1400
LANE_ID = "GSC_404_RECOVERY"
LABELS = {
    "SOURCE_AUDIT": "Source and data provenance need independent verification first.",
    "TECHNICAL_REPAIR_REVIEW": "A human should investigate the original 404 URLs and technical repair alternatives.",
    "EDITORIAL_REVIEW": "A human should review the missing pages' relevance and original content opportunities.",
    "MONITOR": "There is not enough reason for immediate change; keep observing.",
    "ABSTAIN": "The sample is insufficient or contradictory; do not rank any action.",
}
SCORE_TIERS = [
    "HOLD: source provenance is contradictory or missing",
    "LOW: retain monitoring, no actionable source evidence",
    "MEDIUM: focused original-source investigation is justified",
    "HIGH: investigate promptly, without authorising any fix",
]


class JevPilotHeld(RuntimeError):
    """Fail-closed safety gate; never include API response or secrets."""


def _nonnegative(value: Any, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 100_000:
        raise JevPilotHeld(f"invalid_{name}")
    return value


def _prob(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise JevPilotHeld(f"invalid_{field}")
    v = float(value)
    if not math.isfinite(v) or not 0 <= v <= 1:
        raise JevPilotHeld(f"invalid_{field}")
    return v


def build_jev_one_shot_plan(
    department: Mapping[str, Any] | None = None,
    quora: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Only limited numeric aggregates; never raw GSC queries, URLs or users."""
    snapshot = read_department_snapshot() if department is None else department
    reviewed = review_jev_department_portfolio(snapshot=snapshot, quora=quora)
    if (reviewed.get("schema_version") != "empire.search.jev_department_portfolio.v1"
            or reviewed.get("execution_authority") != "NONE"
            or reviewed.get("jev_inference_calls") != 0
            or reviewed.get("database_writes") is not False
            or reviewed.get("publication_authority") is not False):
        raise JevPilotHeld("department_not_safe_for_inference")
    try:
        lane = next(x for x in reviewed["task_board"] if x["task_id"] == LANE_ID)
    except (KeyError, StopIteration) as exc:
        raise JevPilotHeld("approved_lane_missing") from exc
    if (lane["evidence_state"] != "AGGREGATE_REVIEW_AVAILABLE"
            or lane["risk_class"] != "medium"
            or lane["automatic_execution_authorized"] is not False):
        raise JevPilotHeld("approved_lane_no_aggregate")
    row = lane["aggregate_scalar_evidence"]
    if set(row) != {
        "legacy_missing_404_count_in_returned_page_sample",
        "legacy_missing_404_impressions_in_returned_page_sample",
        "legacy_404_core_topic_editorial_review_count",
    }:
        raise JevPilotHeld("aggregate_scope_drift")
    window = reviewed["source_sample_window"]
    if (not isinstance(window, list) or len(window) != 2
            or any(not isinstance(v, str) or len(v) != 10 for v in window)):
        raise JevPilotHeld("unverified_window")
    safe = {
        "source_type": "FIRST_PARTY_GSC_PAGE_DIMENSION_AGGREGATE",
        "observation_limit": "SAMPLE_ONLY_NOT_SITEWIDE",
        "window": window,
        "sample_page_rows": _nonnegative(
            snapshot["gsc_returned_page_rows"], "sample_page_rows"),
        "missing_page_rows_in_sample": _nonnegative(
            row["legacy_missing_404_count_in_returned_page_sample"], "missing_page_rows"),
        "missing_page_impressions_in_sample": _nonnegative(
            row["legacy_missing_404_impressions_in_returned_page_sample"], "impressions"),
        "core_topic_editorial_candidates": _nonnegative(
            row["legacy_404_core_topic_editorial_review_count"], "core_candidates"),
        "actual_rank_positions_verified": False,
        "actual_buyer_conversion_verified": False,
        "publisher_permission": False,
    }
    if (safe["missing_page_rows_in_sample"] > safe["sample_page_rows"]
            or safe["core_topic_editorial_candidates"] > safe["missing_page_rows_in_sample"]):
        raise JevPilotHeld("inconsistent_sample_counts")
    questions = {
        "next_review": {
            "type": "choice",
            "instructions": "Select the best HUMAN REVIEW workstream based only on these sampled GSC aggregates. Do not assume ranked positions, conversions, verified redirects or publish authority.",
            "criteria": LABELS,
        },
        "investigation_priority": {
            "type": "score",
            "instructions": "Rate urgency for an evidence-only investigation, NOT implementation priority or commercial value.",
            "criteria": SCORE_TIERS,
        },
        "requires_human": {
            "type": "noul",
            "instructions": "Does any proposed repair, redirect, content publication or customer-impacting SEO change require original URL evidence and human approval?",
        },
    }
    request = {"model": MODEL, "state": safe, "questions": questions}
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    if len(json.dumps(safe).encode()) > MAX_STATE_BYTES or len(encoded) > 4000:
        raise JevPilotHeld("request_size_exceeded")
    return {
        "schema_version": SCHEMA,
        "source_sha256": sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest(),
        "state": safe,
        "request": request,
        "expected_endpoint": ENDPOINT,
        "expected_model": MODEL,
        "max_expected_request_count": 1,
        "max_accepted_cost_usd": MAX_COST_USD,
        "mode": "READ_ONLY_SHADOW",
        "actual_question_pages_verified": False,
        "raw_query_or_customer_data_sent": False,
        "outbound_or_publication_authorized": False,
        "execution_authority": "NONE",
    }


def evaluate_jev_one_shot(
    plan: Mapping[str, Any],
    *,
    key: str,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Explicit one-shot only. Transport and schema failures are held."""
    if (plan.get("schema_version") != SCHEMA
            or plan.get("mode") != "READ_ONLY_SHADOW"
            or plan.get("execution_authority") != "NONE"
            or plan.get("raw_query_or_customer_data_sent") is not False
            or plan.get("outbound_or_publication_authorized") is not False
            or plan.get("request", {}).get("model") != MODEL
            or plan.get("request", {}).get("questions", {}) .keys()
                != {"next_review", "investigation_priority", "requires_human"}):
        raise JevPilotHeld("invalid_one_shot_contract")
    if not isinstance(key, str) or len(key) < 20 or "\n" in key:
        raise JevPilotHeld("openrouter_key_not_configured")
    # Re-validate the exact allowed outbound payload, not caller-provided data.
    state = plan["request"]["state"]
    if state != plan["state"] or sha256(
        json.dumps(state, sort_keys=True).encode()
    ).hexdigest() != plan["source_sha256"]:
        raise JevPilotHeld("one_shot_state_modified")
    if set(state) != {
        "source_type", "observation_limit", "window", "sample_page_rows",
        "missing_page_rows_in_sample", "missing_page_impressions_in_sample",
        "core_topic_editorial_candidates", "actual_rank_positions_verified",
        "actual_buyer_conversion_verified", "publisher_permission",
    } or state["publisher_permission"] is not False:
        raise JevPilotHeld("outbound_state_not_allowlisted")
    if len(json.dumps(state).encode()) > MAX_STATE_BYTES:
        raise JevPilotHeld("state_size_exceeded")

    try:
        resp = post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json=dict(plan["request"]),
            timeout=12,
            allow_redirects=False,
        )
        if resp.status_code != 200:
            # No response body or vendor error text in logs.
            raise JevPilotHeld(f"jev_http_{resp.status_code}")
        packet = resp.json()
    except JevPilotHeld:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise JevPilotHeld("jev_gateway_unavailable_or_invalid") from exc
    if not isinstance(packet, Mapping):
        raise JevPilotHeld("jev_response_shape")
    model = packet.get("model")
    answers = packet.get("answers")
    usage = packet.get("usage")
    if (not isinstance(model, str) or not model.startswith("typesafe/jev-1.13")
            or not isinstance(answers, Mapping)
            or set(answers) != {"next_review", "investigation_priority", "requires_human"}
            or not isinstance(usage, Mapping)):
        raise JevPilotHeld("jev_response_model_or_answers")
    selected = answers["next_review"]
    priority = answers["investigation_priority"]
    human = answers["requires_human"]
    if (not isinstance(selected, Mapping) or selected.get("type") != "choice"
            or selected.get("choice") not in LABELS
            or not isinstance(selected.get("probabilities"), Mapping)
            or set(selected["probabilities"]) != set(LABELS)
            or not isinstance(priority, Mapping) or priority.get("type") != "score"
            or not isinstance(human, Mapping) or human.get("type") != "noul"):
        raise JevPilotHeld("jev_response_type_or_labels")
    distribution = {name: _prob(selected["probabilities"][name], name)
                    for name in LABELS}
    if abs(sum(distribution.values()) - 1) > 0.03:
        raise JevPilotHeld("jev_choice_probabilities_inconsistent")
    if type(priority.get("score")) not in (int, float) or not math.isfinite(priority["score"]) or not 0 <= priority["score"] <= 3:
        raise JevPilotHeld("jev_score_out_of_range")
    confidence = _prob(selected.get("confidence"), "confidence")
    score_confidence = _prob(priority.get("confidence"), "score_confidence")
    human_prob = _prob(human.get("noul"), "requires_human")
    tokens = _nonnegative(usage.get("input_tokens"), "input_tokens")
    if tokens > MAX_INPUT_TOKENS:
        raise JevPilotHeld("jev_billed_input_exceeded")
    cost = usage.get("cost")
    if (type(cost) not in (int, float) or not math.isfinite(cost)
            or not 0 <= cost <= MAX_COST_USD):
        raise JevPilotHeld("jev_cost_not_verified_or_over_budget")
    return {
        "schema_version": "empire.search.jev_real_one_shot_result.v1",
        "provider_key": "openrouter_typesafe_jev",
        "model": model,
        "actual_jev_inference_calls": 1,
        "jev_decision_observed": True,
        "decision_label": selected["choice"],
        "decision_confidence": confidence,
        "decision_probabilities": distribution,
        "review_priority_score": round(float(priority["score"]), 4),
        "review_priority_confidence": score_confidence,
        "human_review_yes_probability": human_prob,
        "input_tokens": tokens,
        "cost_usd_reported": float(cost),
        "source_sha256": plan["source_sha256"],
        "ground_truth_or_accuracy_verified": False,
        "decision_controls_live_traffic": False,
        "external_provider_received": "BOUNDED_GSC_PAGE_SAMPLE_AGGREGATES",
        "buyer_or_personal_data_sent": False,
        "database_writes": False,
        "publishing_authorized": False,
        "buyer_routing_authorized": False,
        "execution_authority": "NONE",
    }
