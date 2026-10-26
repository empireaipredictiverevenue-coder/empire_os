"""Evidence-only Google index change detector for original SEO timer.

Takes an original five-URL indexed-version + site-crawl review; does not
submit/index/fetch Google itself, send messages or write the database.
"""
from __future__ import annotations
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

URLS = (
    "https://empire-ai.co.uk/",
    "https://empire-ai.co.uk/commercial",
    "https://empire-ai.co.uk/industries/roofing",
    "https://empire-ai.co.uk/industries/solar",
    "https://empire-ai.co.uk/predictive-revenue",
)
VALID = {
    "GOOGLE_INDEXED_VERSION_VERIFIED",
    "GOOGLE_HAS_NO_URL_RECORD",
    "GOOGLE_INDEX_STATUS_NEEDS_REVIEW",
}


class IndexChangeEvidenceHeld(ValueError):
    pass


def summarize_verified_google_index(
    review: Mapping[str, Any], previous: Mapping[str, Any] | None = None,
    *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise IndexChangeEvidenceHeld("UTC_CLOCK_REQUIRED")
    if (not isinstance(review, Mapping)
        or review.get("schema_version") != "empire.search.google_indexed_truth_review.v1"
        or review.get("mode") != "OBSERVE"
        or review.get("source") != "ORIGINAL_FIVE_URL_GSC_INSPECTION_PLUS_LIVE_CRAWL"
        or review.get("execution_authority") != "none"
        or review.get("database_writes") is not False
        or review.get("automatic_index_submissions_authorized") is not False
        or review.get("full_site_indexation_verified") is not False
        or review.get("scope_google_urls_checked") != 5):
        raise IndexChangeEvidenceHeld("EXACT_EXISTING_GOOGLE_REVIEW_REQUIRED")
    try:
        obs = datetime.fromisoformat(review["provider_receipt_observed_at"])
        if obs.tzinfo is None:
            raise ValueError("missing timezone")
        age = (now.astimezone(timezone.utc) -
               obs.astimezone(timezone.utc)).total_seconds()
    except (KeyError,TypeError,ValueError) as exc:
        raise IndexChangeEvidenceHeld("DATED_PROVIDER_EVIDENCE_REQUIRED") from exc
    if not -300 <= age <= 36*3600:
        raise IndexChangeEvidenceHeld("GOOGLE_INDEX_OBSERVATION_NOT_FRESH")

    entries=review.get("findings")
    if (not isinstance(entries,list) or len(entries)!=5 or
        [x.get("url") for x in entries if isinstance(x, Mapping)]!=list(URLS)):
        raise IndexChangeEvidenceHeld("ALL_FIVE_ORIGINAL_URLS_REQUIRED")
    states={}
    for entry in entries:
        state=entry.get("state")
        if state not in VALID:
            raise IndexChangeEvidenceHeld("UNSUPPORTED_GOOGLE_STATE")
        if (entry.get("external_search_rank_attested") is not False or
            entry.get("ai_answer_citation_attested") is not False or
            entry.get("lead_or_sale_attested") is not False):
            raise IndexChangeEvidenceHeld("INFERRED_COMMERCIAL_EVIDENCE_FORBIDDEN")
        states[entry["url"]]=state
    indexed=sum(s=="GOOGLE_INDEXED_VERSION_VERIFIED" for s in states.values())
    unknown=sum(s=="GOOGLE_HAS_NO_URL_RECORD" for s in states.values())
    if (review.get("indexed_version_exact_verified")!=indexed or
        review.get("google_url_unknown_count")!=unknown):
        raise IndexChangeEvidenceHeld("PROVIDER_COUNTS_INCONSISTENT")
    changes=[]
    if previous is not None:
        if (not isinstance(previous,Mapping) or
            previous.get("schema_version") != "empire.search.google_index_daily_watch.v1"
            or previous.get("status")!="GOOGLE_INDEX_WATCH_RECORDED"
            or previous.get("scope_checked")!=5 or
            previous.get("google_indexing_submissions")!=0
            or previous.get("database_writes") is not False
            or previous.get("website_changed") is not False
            or previous.get("outbound_sent") is not False
            or previous.get("execution_authority")!="none"):
            raise IndexChangeEvidenceHeld("PREVIOUS_DATED_WATCH_RECEIPT_INVALID")
        prev=previous.get("exact_url_states")
        if not isinstance(prev,Mapping) or set(prev)!=set(URLS) or any(x not in VALID for x in prev.values()):
            raise IndexChangeEvidenceHeld("PREVIOUS_EXACT_URL_STATES_INVALID")
        for url in URLS:
            if prev[url]!=states[url]:
                changes.append({
                    "url":url,"previous":prev[url],"current":states[url],
                    "google_indexed_newly_verified":(
                        prev[url]!="GOOGLE_INDEXED_VERSION_VERIFIED" and
                        states[url]=="GOOGLE_INDEXED_VERSION_VERIFIED"
                    ),
                })
    return {
        "schema_version":"empire.search.google_index_daily_watch.v1",
        "status":"GOOGLE_INDEX_WATCH_RECORDED",
        "mode":"OBSERVE",
        "observed_at":now.astimezone(timezone.utc).isoformat(),
        "original_google_observed_at":review["provider_receipt_observed_at"],
        "provider_observation_age_seconds":int(age),
        "scope_checked":5,
        "indexed_verified":indexed,
        "unknown_to_google":unknown,
        "other_review":5-indexed-unknown,
        "exact_url_states":states,
        "changes_since_previous_review":changes,
        "previous_watch_exists":previous is not None,
        "change_count":len(changes),
        "site_critical_issues":review.get("site_audit_critical_issue_count"),
        "full_site_indexation_verified":False,
        "google_indexing_submissions":0,
        "ranking_uplift_verified":False,
        "external_ai_citations_verified":False,
        "qualified_buyers_verified":False,
        "revenue_verified":False,
        "database_writes":False,
        "website_changed":False,
        "outbound_sent":False,
        "execution_authority":"none",
    }
