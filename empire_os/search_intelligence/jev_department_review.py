"""High-level Jev decision tasks from existing aggregate SEO department evidence.

Catalogue and deterministic evidence triage only. Zero Jev calls, rankings,
customer-level records, model-generated scores, external requests or writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.typed_decision_provider import TypedDecisionRequest
from empire_os.jev_strategy import review_jev_use_case

from .department_snapshot import read_department_snapshot
from .quora_intelligence import review_quora_research

SCHEMA = "empire.search.jev_department_portfolio.v1"
CHOICES = ("SOURCE_AUDIT", "TECHNICAL_REPAIR_REVIEW", "EDITORIAL_REVIEW",
           "MEASUREMENT_REVIEW", "MONITOR", "ABSTAIN")
CHOICE_CRITERIA = {
    "SOURCE_AUDIT": "Check original source provenance and freshness before ranking work.",
    "TECHNICAL_REPAIR_REVIEW": "Inspect actual pages or code before proposing a repair.",
    "EDITORIAL_REVIEW": "Prepare original, rights-cleared content for human review.",
    "MEASUREMENT_REVIEW": "Validate measurement and attribution with original receipts.",
    "MONITOR": "Continue observation without claiming a commercial result.",
    "ABSTAIN": "Not enough evidence for a supported recommendation.",
}
SECTOR_COUNTS = {"roofing": 16, "hvac": 8, "solar": 8,
                 "dental": 8, "legal": 8, "b2b": 8}
SCALAR_FIELDS = {
    "gsc_returned_page_rows", "gsc_returned_page_sample_clicks",
    "gsc_returned_page_sample_impressions",
    "legacy_missing_404_count_in_returned_page_sample",
    "legacy_missing_404_impressions_in_returned_page_sample",
    "legacy_404_core_topic_editorial_review_count",
    "legacy_404_off_core_retain_404_count",
    "semantic_live_priority_pages_checked",
    "semantic_editorial_review_candidates",
    "search_fabric_cache_files_observed",
    "search_fabric_cache_fresh_candidates_24h",
    "search_fabric_cache_stale_candidates",
    "search_fabric_cache_invalid_envelopes",
    "growth_specialist_desks", "research_campaigns",
}
EVIDENCE_FLAGS = {
    "search_rankings_verified", "external_ai_answer_citation_verified",
    "external_geo_mentions_verified", "buyer_enquiries_verified",
    "realised_revenue_verified", "independent_google_rank_positions_verified",
}


class JevDepartmentEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class Lane:
    task_id: str
    title: str
    existing_owner: str
    evidence_keys: tuple[str, ...]
    readiness_key: str
    decision_goal: str
    next_action: str
    risk_class: str = "medium"


LANES = (
    Lane("SEO_PORTFOLIO_ALLOCATION", "Department opportunity allocation",
         "marketing_growth", ("growth_specialist_desks", "research_campaigns"),
         "research_campaigns", "Select the best evidence-backed editorial research priority.",
         "REVIEW_EXISTING_NINE_CAMPAIGN_RESEARCH_PORTFOLIO"),
    Lane("GSC_404_RECOVERY", "Legacy organic visibility recovery",
         "search_intelligence.indexation",
         ("legacy_missing_404_count_in_returned_page_sample",
          "legacy_missing_404_impressions_in_returned_page_sample",
          "legacy_404_core_topic_editorial_review_count"),
         "legacy_missing_404_count_in_returned_page_sample",
         "Choose which observed missing URLs deserve source and editorial investigation.",
         "REVIEW_EXISTING_404_LEDGER_NO_AUTOMATIC_REDIRECT"),
    Lane("SEARCH_FABRIC_FRESHNESS", "Search Fabric source reliability",
         "search_fabric",
         ("search_fabric_cache_files_observed", "search_fabric_cache_stale_candidates",
          "search_fabric_cache_fresh_candidates_24h",
          "search_fabric_cache_invalid_envelopes"),
         "search_fabric_cache_stale_candidates",
         "Identify which provider/cache faults should be reviewed first.",
         "AUDIT_STALE_SEARCH_CACHE_AND_PROVIDER_PARSERS"),
    Lane("ORIGINAL_CONTENT_QUALITY", "Original editorial quality remediation",
         "search_intelligence.semantic_opportunity_review",
         ("semantic_editorial_review_candidates",
          "semantic_live_priority_pages_checked"),
         "semantic_editorial_review_candidates",
         "Identify substantive content gaps for original editorial repairs.",
         "REVIEW_ALREADY_FLAGGED_CONTENT_NO_AUTO_PUBLISH"),
    Lane("GSC_SEARCH_PERFORMANCE", "Search demand and content portfolio review",
         "search_intelligence.search_console",
         ("gsc_returned_page_rows", "gsc_returned_page_sample_impressions",
          "gsc_returned_page_sample_clicks"),
         "gsc_returned_page_rows",
         "Decide which observed GSC page trends justify deeper query-level validation.",
         "REVIEW_GSC_PAGE_ONLY_SAMPLE_NOT_RANKS"),
    Lane("AEO_CITATION_COVERAGE", "AEO independent citation evidence",
         "search_intelligence.ai_visibility", (),
         "external_ai_answer_citation_verified",
         "Evaluate verified citations, not hypothetical AI answer visibility.",
         "COLLECT_INDEPENDENT_AI_CITATION_RECEIPTS"),
    Lane("GEO_ENTITY_VISIBILITY", "GEO brand and entity reference accuracy",
         "search_intelligence.ai_visibility", (),
         "external_geo_mentions_verified",
         "Decide how to address independently observed entity-reference gaps.",
         "COLLECT_INDEPENDENT_GEO_MENTIONS_WITH_SOURCE"),
    Lane("INDEPENDENT_SERP_COMPETITION", "Competitive SERP position intelligence",
         "search_intelligence.rank_history", (),
         "independent_google_rank_positions_verified",
         "Compare observed rank movement only from independently verified positions.",
         "VERIFY_INDEPENDENT_GOOGLE_RANK_POSITION_SOURCE"),
    Lane("CONTENT_DECAY_INTERVENTION", "Content decay and refresh portfolio",
         "search_intelligence.content_decay", (),
         "not_in_aggregate",
         "Select decay interventions based on longitudinal same-page evidence.",
         "COLLECT_MULTIWINDOW_URL_LEVEL_PERFORMANCE"),
    Lane("INTERNAL_LINK_ARCHITECTURE", "Internal linking and topical authority",
         "search_intelligence.internal_links", (),
         "not_in_aggregate",
         "Prioritise link-graph repair from actual page-to-page crawl evidence.",
         "COLLECT_LIVE_SITE_LINK_GRAPH_AND_CRAWL_CONTEXT"),
    Lane("TECHNICAL_SEO_TRIAGE", "Technical and structured-data QA",
         "search_intelligence.technical_audit", (),
         "not_in_aggregate",
         "Route crawl failures, canonical problems and schema violations to engineering.",
         "COLLECT_FRESH_TECHNICAL_AND_SCHEMA_AUDIT_RECEIPTS"),
    Lane("SEO_MARKET_EXPANSION", "UK/US multisector organic allocation",
         "marketing_growth", ("research_campaigns",),
         "not_in_aggregate",
         "Compare market niches only after equivalent regional demand and rights evidence.",
         "COLLECT_MARKET_SCOPED_DEMAND_COMPETITION_AND_PAGE_READINESS"),
    Lane("QUORA_EDITORIAL_OPERATIONS", "Quora six-market original answer opportunities",
         "search_intelligence.quora_intelligence", (),
         "quora_origin_verified",
         "Prioritise verified original questions by usefulness and policy suitability.",
         "VERIFY_ORIGINAL_QUORA_QUESTION_PAGES_AND_DISCLOSURES", "high"),
    Lane("ORGANIC_COMMERCIAL_ATTRIBUTION", "Organic enquiries to verified revenue",
         "search_intelligence.attribution", (),
         "buyer_enquiries_verified",
         "Inspect first-party sessions and buyer-accepted conversion receipts.",
         "COLLECT_REAL_OPTED_IN_ENQUIRY_AND_BUYER_PAYMENT_PROOF", "high"),
)

def _validate_department(snapshot: Mapping[str, Any]) -> dict[str, int]:
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("schema_version") != "empire.search_growth.department_integration.v1"
            or snapshot.get("status") != "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "NONE"
            or snapshot.get("customer_identifiers_disclosed") is not False
            or snapshot.get("publisher_mutation_authorized") is not False
            or snapshot.get("independent_google_rank_positions_verified") is not False):
        raise JevDepartmentEvidenceError("DEPARTMENT_SAFE_SOURCE_CONTRACT_FAILED")
    counters: dict[str, int] = {}
    for key in SCALAR_FIELDS:
        value = snapshot.get(key)
        if type(value) is not int or not 0 <= value <= 100_000:
            raise JevDepartmentEvidenceError("DEPARTMENT_SCALAR_INVALID")
        counters[key] = value
    for key in EVIDENCE_FLAGS:
        if snapshot.get(key) is not False:
            raise JevDepartmentEvidenceError("DEPARTMENT_UNVERIFIED_FLAG_ESCALATION")
    if (counters["legacy_missing_404_count_in_returned_page_sample"]
            > counters["gsc_returned_page_rows"]
            or counters["search_fabric_cache_stale_candidates"]
            > counters["search_fabric_cache_files_observed"]):
        raise JevDepartmentEvidenceError("INCONSISTENT_DEPARTMENT_COUNTS")
    if (not isinstance(snapshot.get("gsc_final_page_window"), list)
            or len(snapshot["gsc_final_page_window"]) != 2
            or any(not isinstance(t, str) or len(t) != 10
                   for t in snapshot["gsc_final_page_window"])):
        raise JevDepartmentEvidenceError("INVALID_GSC_WINDOW")
    return counters


def review_jev_department_portfolio(
    snapshot: Mapping[str, Any] | None = None,
    quora: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read existing source aggregates, create bounded typed *plans*, never call Jev."""
    department = read_department_snapshot() if snapshot is None else snapshot
    counters = _validate_department(department)
    quora = review_quora_research() if quora is None else quora
    if (not isinstance(quora, Mapping)
            or quora.get("schema_version") != "empire.search_intelligence.quora_research.v1"
            or quora.get("mode") != "OBSERVE"
            or quora.get("execution_authority") != "NONE"
            or quora.get("topic_count") != 56
            or quora.get("vertical_topic_counts") != SECTOR_COUNTS
            or quora.get("verified_quora_questions") != 0
            or quora.get("published_answers_verified") != 0
            or quora.get("automated_posting_authorized") is not False):
        raise JevDepartmentEvidenceError("QUORA_SOURCE_CONTRACT_FAILED")
    queue = []
    for lane in LANES:
        inputs = {key: counters[key] for key in lane.evidence_keys}
        observed = (
            counters.get(lane.readiness_key, 0) > 0
            if lane.readiness_key in counters else False
        )
        request = TypedDecisionRequest(
            task_key=lane.task_id.lower(),
            decision_schema_ref="empire.search.jev_department_choice.v1",
            state_ref="seo-department:" + lane.task_id.lower(),
            state={"source_class": "REVIEWED_AGGREGATE_ONLY",
                   "aggregate_scalar_evidence": inputs,
                   "independent_case_evidence_verified": False},
            allowed_labels=CHOICES,
            risk_class=lane.risk_class,
            label_criteria=CHOICE_CRITERIA,
        )
        request.validate()
        use_case = review_jev_use_case({
            "task_key": "research_triage" if lane.risk_class == "medium"
                        else "policy_risk_triage",
            "risk_class": lane.risk_class,
            "decision_schema_ref": request.decision_schema_ref,
            "baseline_ref": lane.existing_owner,
            "evaluation_dataset_refs": [],
            "deterministic_possible": True,
        })
        queue.append({
            "task_id": lane.task_id,
            "title": lane.title,
            "existing_owner": lane.existing_owner,
            "risk_class": lane.risk_class,
            "evidence_state": "AGGREGATE_REVIEW_AVAILABLE" if observed
                              else "ORIGINAL_EVIDENCE_REQUIRED",
            "aggregate_scalar_evidence": inputs,
            "next_evidence_action": lane.next_action,
            "jev_decision_goal": lane.decision_goal,
            "questions": {
                "recommended_queue": {"type": "choice", "options": list(CHOICES)},
                "review_priority": {
                    "type": "score",
                    "levels": ["HOLD", "LOW", "MEDIUM", "HIGH"],
                },
                "human_review_required": {
                    "type": "noul",
                    "criteria": {"true": "A reviewer must independently verify source evidence.",
                                 "false": "Evidence can be observed without new reviewer action."},
                },
            },
            "state_ref": request.state_ref,
            "schema_ref": request.decision_schema_ref,
            "labeled_real_cases": 0,
            "jev_prediction": None,
            "jev_score": None,
            "jev_confidence": None,
            "model_evaluation_authorized": False,
            "automatic_execution_authorized": False,
            "publishing_authorized": False,
        })
        if use_case["provider_activation"] is not False:
            raise JevDepartmentEvidenceError("UNEXPECTED_PROVIDER_ACTIVATION")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "scope": "EXISTING_SEO_DEPARTMENT",
        "task_count": len(queue),
        "aggregate_observed_lane_count": sum(
            x["evidence_state"] == "AGGREGATE_REVIEW_AVAILABLE" for x in queue),
        "independent_case_evaluation_ready_count": 0,
        "origin_quora_questions_verified": 0,
        "jev_provider": "disabled",
        "jev_inference_calls": 0,
        "jev_scores_generated": 0,
        "provider_keys_accessed": False,
        "external_requests_performed_by_review": False,
        "estimated_business_value": None,
        "revenue_observed_from_jev": False,
        "typed_decision_plan_only": True,
        "task_board": queue,
        "source_sample_window": list(department["gsc_final_page_window"]),
        "database_writes": False,
        "publication_authority": False,
        "buyer_outreach_authority": False,
        "payment_authority": False,
        "execution_authority": "NONE",
    }
