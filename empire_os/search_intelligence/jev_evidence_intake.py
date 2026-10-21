"""Review candidates from REAL first-party page-only GSC 404 evidence.

Cases are not human labels. Accepted ground truth needs authenticated reviewer
provenance outside this data-only module; this read-only intake cannot create it.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SOURCE_SCHEMA = "empire.organic_search.gsc_page_legacy_404_review.v1"
SCHEMA = "empire.search.jev_original_page_review_intake.v1"
LABELS = ("SOURCE_AUDIT", "TECHNICAL_REPAIR_REVIEW", "EDITORIAL_REVIEW",
          "MONITOR", "ABSTAIN")
CATEGORIES = {
    "BUYER_INTENT_EDITORIAL_REVIEW",
    "EMPIRE_PRODUCT_TOPIC_REVIEW",
    "ROOFING_RESEARCH_REVIEW",
    "OFF_CORE_RETAIN_404_PENDING_EVIDENCE",
}
_ALLOWED_PATH = re.compile(r"^/aeo/[a-z0-9_-]{2,36}/[A-Za-z0-9_-]{1,96}/?$")


class JevEvidenceIntakeHeld(ValueError):
    pass


def _positive_int(value: Any, *, limit: int = 100_000) -> int:
    if type(value) is not int or not 0 <= value <= limit:
        raise JevEvidenceIntakeHeld("UNVERIFIED_PAGE_SAMPLE_SCALAR")
    return value


def _window(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) != 2:
        raise JevEvidenceIntakeHeld("INVALID_GSC_PAGE_ONLY_WINDOW")
    for entry in value:
        if not isinstance(entry, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry):
            raise JevEvidenceIntakeHeld("INVALID_GSC_PAGE_ONLY_WINDOW")
    try:
        first, last = (date.fromisoformat(s) for s in value)
    except ValueError as exc:
        raise JevEvidenceIntakeHeld("INVALID_GSC_PAGE_ONLY_WINDOW") from exc
    if last < first or (last-first).days > 31:
        raise JevEvidenceIntakeHeld("INVALID_GSC_PAGE_ONLY_WINDOW")
    return list(value)


def build_original_page_review_intake(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Turn existing trusted GSC + origin HTTP observations into reviewer tasks.

    Not a ranked queue, not a labelled dataset, not an indexation claim.
    Caller owns original packet provenance and safe same-origin probes.
    """
    if (not isinstance(packet, Mapping)
            or packet.get("schema_version") != SOURCE_SCHEMA
            or packet.get("status") != "REVIEW_MISSING_LEGACY_URLS"
            or packet.get("mode") != "OBSERVE"
            or packet.get("source") != "google_search_console_page_dimension_final"
            or packet.get("site_url") != "sc-domain:empire-ai.co.uk"
            or packet.get("returned_page_totals_are_sitewide") is not False
            or packet.get("query_page_rows_joined_or_added") is not False
            or packet.get("redirect_authorized") is not False
            or packet.get("publication_authorized") is not False
            or packet.get("buyer_conversion_verified") is not False
            or packet.get("revenue_verified") is not False
            or packet.get("outbound_sent") is not False
            or packet.get("database_writes") is not False
            or packet.get("execution_authority") != "none"):
        raise JevEvidenceIntakeHeld("UNVERIFIED_FIRST_PARTY_SOURCE_CONTRACT")
    window = _window(packet.get("window"))
    count = _positive_int(packet.get("missing_legacy_page_count"), limit=250)
    sample_count = _positive_int(packet.get("returned_page_rows"), limit=250)
    if not 1 <= count <= sample_count:
        raise JevEvidenceIntakeHeld("NO_OBSERVED_MISSING_PAGE_CASES")
    queue = packet.get("missing_review_queue")
    if not isinstance(queue, list) or len(queue) != count:
        raise JevEvidenceIntakeHeld("MISSING_CASE_ROWS_OR_COUNT_MISMATCH")
    categories = packet.get("missing_review_categories")
    if (not isinstance(categories, dict)
            or not set(categories).issubset(CATEGORIES)
            or any(_positive_int(v, limit=250) > 250 for v in categories.values())
            or sum(categories.values()) != count):
        raise JevEvidenceIntakeHeld("INVALID_MISSING_PAGE_CATEGORIES")

    safe_cases: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    total_impressions = 0
    total_clicks = 0
    normalized_seen: set[str] = set()
    for row in queue:
        if not isinstance(row, Mapping):
            raise JevEvidenceIntakeHeld("INVALID_GSC_CASE_ROW")
        path = row.get("path")
        if (not isinstance(path, str) or not _ALLOWED_PATH.fullmatch(path)
                or "?" in path or "#" in path or "\\" in path or "//" in path):
            raise JevEvidenceIntakeHeld("URL_NOT_ALLOWLISTED_OR_UNSAFE")
        normalized = path.rstrip("/")
        if path in seen_paths or normalized in normalized_seen:
            raise JevEvidenceIntakeHeld("DUPLICATE_CANONICAL_PATH")
        seen_paths.add(path)
        normalized_seen.add(normalized)
        impressions = _positive_int(row.get("page_dimension_impressions"))
        clicks = _positive_int(row.get("page_dimension_clicks"))
        http = row.get("origin_http_status")
        category = row.get("review_category")
        if (clicks > impressions or type(http) is not int or http not in {404, 410}
                or category not in CATEGORIES
                or row.get("publisher_rights_verified") is not False
                or row.get("current_page_equivalence_verified") is not False
                or row.get("restore_authorized") is not False
                or row.get("redirect_authorized") is not False
                or row.get("revenue_verified") is not False
                or not isinstance(row.get("review_action"), str)
                or not re.fullmatch(r"[A-Z0-9_]{4,100}", row["review_action"])):
            raise JevEvidenceIntakeHeld("CASE_ORIGIN_OR_POLICY_UNVERIFIED")
        total_impressions += impressions
        total_clicks += clicks
        stable_id = sha256(("sc-domain:empire-ai.co.uk|page|final|"
                            + "|".join(window) + "|" + path).encode()).hexdigest()
        evidence_digest = sha256(
            json.dumps({
                "path": path, "window": window, "http": http,
                "category": category, "impressions": impressions,
                "clicks": clicks,
            }, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        safe_cases.append({
            "case_id": "gsc404:" + stable_id[:24],
            "path": path,  # Owned URL path only; retained in private evidence.
            "source_ref": "gsc-page-origin-sha256:" + evidence_digest,
            "gsc_property": "sc-domain:empire-ai.co.uk",
            "window": window,
            "observed_origin_http_status": http,
            "observed_page_dimension_impressions": impressions,
            "observed_page_dimension_clicks": clicks,
            "deterministic_review_category": category,
            "deterministic_next_research_action": row["review_action"],
            "proposed_human_review_label": None,
            "human_label_verified": False,
            "reviewer_identity_authenticated": False,
            "original_publisher_rights_verified": False,
            "current_equivalent_content_verified": False,
            "independent_jev_case_evaluation_ready": False,
            "allowed_human_review_labels": list(LABELS),
            "next_gate": "AUTHENTICATED_INDEPENDENT_REVIEW_WITH_ORIGINAL_URL_PROOF",
        })
    if (Counter(x["deterministic_review_category"] for x in safe_cases) != categories
            or total_impressions != _positive_int(packet.get("missing_legacy_page_impressions"))
            or total_clicks != _positive_int(packet.get("missing_legacy_page_clicks"))):
        raise JevEvidenceIntakeHeld("GSC_SAMPLE_AGGREGATE_MISMATCH")
    return {
        "schema_version": SCHEMA,
        "status": "ORIGINAL_OBSERVATIONS_AWAITING_AUTHENTICATED_HUMAN_LABELS",
        "mode": "OBSERVE",
        "sample_window": window,
        "source_property": "sc-domain:empire-ai.co.uk",
        "sample_page_rows": sample_count,
        "observed_missing_case_count": len(safe_cases),
        "observed_missing_case_impressions": total_impressions,
        "observed_missing_case_clicks": total_clicks,
        "deduplicated_original_cases": safe_cases,
        "accepted_human_ground_truth_labels": 0,
        "independently_labelled_case_count": 0,
        "benchmark_ready_case_count": 0,
        "comparison_with_aggregate_jev_one_shot_permitted": False,
        "input_source_rights_to_train_verified": False,
        "external_jev_inference_performed": False,
        "publication_authorized": False,
        "automatic_redirects_authorized": False,
        "outreach_authorized": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }


def intake_summary_only(intake: Mapping[str, Any]) -> dict[str, Any]:
    """No URL path, observation text or third-party reviewer data in summary."""
    if (intake.get("schema_version") != SCHEMA
            or intake.get("status") != "ORIGINAL_OBSERVATIONS_AWAITING_AUTHENTICATED_HUMAN_LABELS"
            or intake.get("accepted_human_ground_truth_labels") != 0
            or intake.get("benchmark_ready_case_count") != 0
            or intake.get("database_writes") is not False
            or intake.get("execution_authority") != "NONE"):
        raise JevEvidenceIntakeHeld("REVIEW_INTAKE_STATUS_DRIFT")
    return {
        "schema_version": "empire.search.jev_original_page_review_summary.v1",
        "mode": "OBSERVE",
        "observed_url_case_count": intake["observed_missing_case_count"],
        "observed_impressions_from_sample": intake["observed_missing_case_impressions"],
        "reviewed_human_labels": 0,
        "benchmark_ready_cases": 0,
        "original_page_evidence_required": True,
        "authenticated_human_review_required": True,
        "training_rights_verified": False,
        "automatic_model_calls": False,
        "publication_authority": False,
        "execution_authority": "NONE",
    }
