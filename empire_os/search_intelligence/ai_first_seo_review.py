"""AI-first SEO investigation over pinned genuine first-party URL observations.

Uses the EXISTING local Laya typed-choice service, not Jev paid calls. AI
hypotheses are never human ground-truth labels, page-copy evidence or authority
for a redirect, publication, revenue recognition, outreach or customer action.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.laya_typed_decision import LayaTypedDecisionError
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
    review_typed_decision_result,
)

from .jev_evidence_intake import SCHEMA as SOURCE_SCHEMA
from .jev_intake_receipt import (
    EXPECTED_SHA256, RECEIPT_PATH, read_verified_original_page_summary,
)

SCHEMA = "empire.search.ai_first_original_page_shadow.v1"
TASK = "seo_original_missing_page_investigation"
LABELS = (
    "SOURCE_AUDIT",
    "TECHNICAL_REPAIR_REVIEW",
    "EDITORIAL_REVIEW",
    "MONITOR",
    "ABSTAIN",
)
CRITERIA = {
    "SOURCE_AUDIT": "First investigate original page, historical content, publisher rights, and provenance. No redirect.",
    "TECHNICAL_REPAIR_REVIEW": "Investigate 404 status, current replacement pages and canonical equivalence; no automatic repair.",
    "EDITORIAL_REVIEW": "Research the topic and original content before considering new useful copy; no publishing.",
    "MONITOR": "Leave status unchanged, observe first-party search evidence; no revenue assumption.",
    "ABSTAIN": "Insufficient evidence for a reliable action; request deeper source research.",
}
RESEARCH_NEXT = {
    "SOURCE_AUDIT": "FIND_ORIGINAL_CONTENT_AND_RIGHTS_RECEIPT",
    "TECHNICAL_REPAIR_REVIEW": "COMPARE_LIVE_CRAWL_CANONICAL_AND_EQUIVALENT_PAGE",
    "EDITORIAL_REVIEW": "RESEARCH_TOPIC_AND_ORIGINAL_PUBLISHING_RIGHTS",
    "MONITOR": "COLLECT_COMPARABLE_FUTURE_GSC_PAGE_EVIDENCE",
    "ABSTAIN": "DEEPER_SOURCE_AND_HISTORICAL_CONTENT_RESEARCH",
}
CONFIDENCE_THRESHOLD = 0.80


class SeoAiFirstHeld(ValueError):
    pass


class ShadowProvider(Protocol):
    def evaluate(self, request: TypedDecisionRequest) -> TypedDecisionResult: ...


def validated_cases(
    receipt_path: Path = RECEIPT_PATH,
    expected_sha256: str = EXPECTED_SHA256,
) -> list[dict[str, Any]]:
    checked = read_verified_original_page_summary(receipt_path, expected_sha256)
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = data.get("deduplicated_original_cases")
    if (data.get("schema_version") != SOURCE_SCHEMA
            or not isinstance(rows, list)
            or len(rows) != checked["observed_url_case_count"]
            or len(rows) != 30):
        raise SeoAiFirstHeld("PINNED_ORIGINAL_CASES_INVALID")
    for row in rows:
        if (row.get("human_label_verified") is not False
                or row.get("proposed_human_review_label") is not None
                or row.get("independent_jev_case_evaluation_ready") is not False
                or row.get("original_publisher_rights_verified") is not False
                or row.get("current_equivalent_content_verified") is not False
                or row.get("observed_origin_http_status") not in (404, 410)
                or row.get("gsc_property") != "sc-domain:empire-ai.co.uk"
                or not isinstance(row.get("path"), str)
                or not row["path"].startswith("/aeo/")):
            raise SeoAiFirstHeld("CASE_TRUTH_OR_RIGHTS_ESCALATED")
    return rows


def request_for_case(row: Mapping[str, Any]) -> TypedDecisionRequest:
    """Minimal existing model input: owned path, verified status, counts, taxonomy."""
    state = {
        "source_type": "OWNED_FIRST_PARTY_GSC_PAGE_ONLY_OBSERVATION",
        "source_scope": "HISTORICAL_SAMPLE_NOT_SITEWIDE",
        "owned_url_path": row["path"],
        "sample_window": list(row["window"]),
        "origin_http_status": row["observed_origin_http_status"],
        "sample_impressions": row["observed_page_dimension_impressions"],
        "sample_clicks": row["observed_page_dimension_clicks"],
        "existing_rule_category_not_ground_truth": row["deterministic_review_category"],
        "original_content_recovered": False,
        "publisher_rights_verified": False,
        "current_equivalent_page_verified": False,
        "buyer_conversion_verified": False,
    }
    if len(json.dumps(state).encode()) > 1000:
        raise SeoAiFirstHeld("MODEL_STATE_TOO_LARGE")
    request = TypedDecisionRequest(
        task_key=TASK,
        decision_schema_ref="empire.search.ai_first_original_page_choice.v1",
        state_ref=row["case_id"],
        state=state,
        allowed_labels=LABELS,
        risk_class="medium",
        instructions=(
            "Choose only the best NEXT READ-ONLY SEO INVESTIGATION for this "
            "observed first-party 404 page. An observed status does NOT prove "
            "historic page contents, current equivalent destination, publisher "
            "rights, buyer intent, search ranking or lost revenue. Existing "
            "taxonomy is a deterministic research hint, not truth. When evidence "
            "is insufficient, select SOURCE_AUDIT or ABSTAIN. Never recommend "
            "automatic redirects, publication, money or outreach."
        ),
        label_criteria=CRITERIA,
    )
    request.validate()
    return request


def review_cases_with_local_ai(
    rows: list[dict[str, Any]],
    *,
    provider: ShadowProvider | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    if not isinstance(rows, list) or len(rows) != 30 or limit != 30:
        raise SeoAiFirstHeld("EXPECTED_PINNED_30_CASE_COHORT")
    model = provider or LayaHttpTypedDecisionProvider(
        base_url="http://127.0.0.1:8769", timeout_s=8.0
    )
    outputs: list[dict[str, Any]] = []
    for row in rows:
        req = request_for_case(row)
        template = {
            "case_id": row["case_id"],
            "source_ref": row["source_ref"],
            "baseline_research_category": row["deterministic_review_category"],
            "candidate_label": None,
            "confidence": None,
            "model_inference_attempted": True,
            "inference_accepted_as_ground_truth": False,
            "automatic_seo_change_authorized": False,
            "human_approval_required_for_public_change": True,
            "source_content_verified_by_ai": False,
        }
        try:
            result = model.evaluate(req)
            audit = review_typed_decision_result(
                request=req, result=result,
                confidence_threshold=CONFIDENCE_THRESHOLD,
            )
            if (result.provider_key not in {"laya_http", "laya"}
                    or result.shadow_only is not True
                    or result.execution_authority != "none"
                    or audit["controls_live_route"] is not False
                    or audit["execution_performed"] is not False
                    or result.label not in LABELS):
                raise SeoAiFirstHeld("MODEL_AUTHORITY_OR_SCHEMA_FAILURE")
            label = result.label
            confidence = round(float(result.confidence), 4)
            if audit["requires_escalation"]:
                status = "DEEPER_AI_SOURCE_RESEARCH_REQUIRED"
            else:
                status = "UNVERIFIED_AI_ADVISORY_FOR_REVIEW"
            outputs.append({
                **template,
                "candidate_label": label,
                "confidence": confidence,
                "provider_key": result.provider_key,
                "model_key": result.model_key,
                "decision_status": status,
                "next_ai_research_task": RESEARCH_NEXT[label],
            })
        except (LayaTypedDecisionError, SeoAiFirstHeld, ValueError, TypeError,
                OSError, TimeoutError, RuntimeError):
            outputs.append({
                **template,
                "provider_key": "laya_http",
                "model_key": "convaiinnovations/laya:onnx",
                "decision_status": "MODEL_FAILURE_ESCALATE_TO_DEEPER_AI_RESEARCH",
                "next_ai_research_task": "REVERIFY_LOCAL_MODEL_AND_SOURCE_CONTEXT",
            })
    count = Counter(x["decision_status"] for x in outputs)
    return {
        "schema_version": SCHEMA,
        "mode": "LOCAL_AI_SHADOW_REVIEW",
        "source_receipt_sha256": EXPECTED_SHA256,
        "cohort_size": len(outputs),
        "inference_attempt_count": len(outputs),
        "local_inference_only": True,
        "external_paid_jev_calls": 0,
        "estimated_external_inference_cost_usd": 0,
        "review_status_counts": dict(count),
        "ai_candidate_count": sum(x["candidate_label"] is not None for x in outputs),
        "case_reviews": outputs,
        "human_ground_truth_labels_created": 0,
        "independent_accuracy_verified": False,
        "original_page_copy_recovered": False,
        "automated_source_research_complete": False,
        "database_writes": False,
        "publication_or_redirect_authorized": False,
        "buyer_outreach_authorized": False,
        "execution_authority": "NONE",
    }


def public_safe_ai_summary(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Even on private loopback, do not release original paths or raw model state."""
    if (packet.get("schema_version") != SCHEMA
            or packet.get("mode") != "LOCAL_AI_SHADOW_REVIEW"
            or packet.get("source_receipt_sha256") != EXPECTED_SHA256
            or packet.get("cohort_size") != 30
            or packet.get("inference_attempt_count") != 30
            or packet.get("local_inference_only") is not True
            or packet.get("external_paid_jev_calls") != 0
            or packet.get("human_ground_truth_labels_created") != 0
            or packet.get("independent_accuracy_verified") is not False
            or packet.get("publication_or_redirect_authorized") is not False
            or packet.get("execution_authority") != "NONE"):
        raise SeoAiFirstHeld("UNTRUSTED_AI_SHADOW_RECEIPT")
    rows=packet.get("case_reviews")
    if (not isinstance(rows,list) or len(rows)!=30
            or len({r.get("case_id") for r in rows})!=30
            or any(r.get("inference_accepted_as_ground_truth") is not False
                   or r.get("automatic_seo_change_authorized") is not False
                   or r.get("human_approval_required_for_public_change") is not True
                   for r in rows)):
        raise SeoAiFirstHeld("UNTRUSTED_AI_CASE_STATUS")
    return {
        "schema_version": "empire.search.ai_first_seo_summary.v1",
        "mode": "OBSERVE",
        "observed_cases_reviewed": 30,
        "local_model_inference_attempts": 30,
        "model_candidates_returned": packet["ai_candidate_count"],
        "deep_ai_research_queue_count": sum(
            r["decision_status"] != "UNVERIFIED_AI_ADVISORY_FOR_REVIEW"
            for r in rows
        ),
        "human_labels_created": 0,
        "benchmark_accuracy_measured": False,
        "original_content_verified": False,
        "automatic_jev_inference_enabled": False,
        "external_paid_jev_calls": 0,
        "source_paths_exposed": False,
        "publication_authority": False,
        "execution_authority": "NONE",
    }
