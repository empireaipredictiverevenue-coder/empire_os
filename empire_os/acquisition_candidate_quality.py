"""Research-only domain hygiene + exact-source join for existing Scout tasks.

No contact extraction, social-person identity resolution, filtering of real
corporate buyer data, prospect promotion or network access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Any, Mapping

SCHEMA = "empire.acquisition_candidate_quality.v1"
SOCIAL_INFRASTRUCTURE = frozenset({
    "reddit.com", "old.reddit.com", "www.reddit.com",
    "i.redd.it", "v.redd.it", "preview.redd.it", "redd.it",
    "linkedin.com", "www.linkedin.com", "lnkd.in",
})
SEARCH_DISCOVERY_HOSTS = frozenset({
    "qwant.com", "www.qwant.com", "google.com", "www.google.com",
    "bing.com", "www.bing.com", "search.yahoo.com", "duckduckgo.com",
})
TASK_SCHEMA = "empire.intent_company_research_tasks.v1"

class QualityHold(ValueError):
    pass

def _host(uri: Any) -> str:
    if not isinstance(uri,str) or not 8 <= len(uri) <= 2048:
        return ""
    try:
        data=urlsplit(uri)
        if data.scheme not in ("https","http") or not data.hostname or data.username or data.password:
            return ""
        return data.hostname.lower().removeprefix("www.")
    except ValueError:
        return ""

def quality_review(scout: Mapping[str,Any], research: Mapping[str,Any],
                   *, now: datetime) -> dict[str,Any]:
    if (now.tzinfo is None or
        scout.get("schema_version") != "empire.buyer_acquisition_scout.v1" or
        scout.get("outbound_sent") is not False or
        scout.get("database_write_performed") is not False or
        not isinstance(scout.get("candidates"),list) or
        not 0 <= len(scout["candidates"]) <= 100 or
        research.get("schema_version") != TASK_SCHEMA or
        research.get("outbound_authorized") is not False or
        research.get("verified_buyer_count") != 0 or
        not isinstance(research.get("identity_review_tasks"),list) or
        not 0 <= len(research["identity_review_tasks"]) <= 12):
        raise QualityHold("source_contract_untrusted")
    candidate_rows=[]
    evidence_urls=set()
    duplicate_domains=set()
    seen=set()
    for candidate in scout["candidates"]:
        if not isinstance(candidate,Mapping) or candidate.get("outreach_authorized") is not False:
            raise QualityHold("scout_candidate_untrusted")
        domain=str(candidate.get("domain") or "").lower().removeprefix("www.")
        website=_host(candidate.get("website"))
        if not domain or len(domain)>253 or "." not in domain:
            status="HOLD_MALFORMED_CANDIDATE_DOMAIN"
        elif domain in seen:
            status="HOLD_DUPLICATE_DOMAIN"
            duplicate_domains.add(domain)
        elif domain in SOCIAL_INFRASTRUCTURE or domain.endswith(".redd.it"):
            status="HOLD_SOCIAL_MEDIA_INFRASTRUCTURE_NOT_BUSINESS_IDENTITY"
        elif domain in SEARCH_DISCOVERY_HOSTS:
            status="HOLD_SEARCH_PLATFORM_SOURCE_NOT_BUYER_PROOF"
        elif website != domain:
            status="HOLD_FIRST_PARTY_WEBSITE_DOMAIN_MISMATCH"
        else:
            status="POTENTIAL_BUSINESS_REQUIRES_INDEPENDENT_BUYER_CHECK"
        seen.add(domain)
        source_url=candidate.get("intent_evidence_url")
        if source_url:
            if not _host(source_url):
                raise QualityHold("scout_intent_evidence_url_invalid")
            evidence_urls.add(source_url)
        candidate_rows.append({
            "domain":domain,
            "review_status":status,
            "original_source_channel":candidate.get("intent_signal_source") or None,
            "original_intent_evidence_present":bool(source_url),
            "canonical_company_identity_verified":candidate.get("canonical_identity_verified") is True,
            "explicit_direct_buyer_evidence_present":bool(candidate.get("explicit_direct_buyer_evidence")),
            "automated_outreach_authorized":False,
        })
    tasks=[]
    ids=set()
    for task in research["identity_review_tasks"]:
        if not isinstance(task,Mapping):
            raise QualityHold("intent_research_task_invalid")
        identity=task.get("task_id")
        evidence=task.get("source_url")
        if (not isinstance(identity,str) or len(identity)>100 or identity in ids
            or not _host(evidence)
            or task.get("verified_buyer_intent") is not False
            or task.get("person_contact_verified") is not False
            or task.get("founder_outreach_authorized") is not False
            or task.get("source_attribution_proven") is not False
            or task.get("task_status") not in (
                "FIRST_PARTY_AFFILIATION_REVIEW",
                "EVIDENCE_LINK_REVIEW",
                "INDEPENDENT_COMPANY_IDENTITY_RESEARCH")):
            raise QualityHold("intent_research_provenance_invalid")
        ids.add(identity)
        candidates=task.get("potential_company_matches") or []
        if not isinstance(candidates,list):
            raise QualityHold("potential_business_matches_invalid")
        affiliation=task.get("public_affiliation_evidence")
        status=(
            "REVIEW_FIRST_PARTY_AFFILIATION_NOTE_NOT_BUYER_PROOF" if affiliation
            else "REVIEW_POTENTIAL_COMPANY_LINK_NOT_AUTHORITATIVE" if candidates
            else "RESEARCH_ORIGINAL_AUTHOR_COMPANY_AFFILIATION"
        )
        tasks.append({
            "task_id":identity,
            "source_channel":task.get("source"),
            "source_domain":_host(evidence),
            "niche":task.get("niche"),
            "intent_class":task.get("intent_class"),
            "reported_intent_score":task.get("reported_intent_score"),
            "exact_evidence_url_seen_in_current_scout":evidence in evidence_urls,
            "verified_affiliation_from_this_audit":False,
            "review_status":status,
            "next_evidence_needed":[
                "independent_first_party_company_source",
                "original_post_to_company_author_connection",
                "real_buying_problem_and_timing",
                "legitimate_decision_maker_and_permission_to_contact",
            ],
            "outreach_authorized":False,
        })
    valid_candidates=sum(x["review_status"]=="POTENTIAL_BUSINESS_REQUIRES_INDEPENDENT_BUYER_CHECK"
                         for x in candidate_rows)
    held=sum(x["review_status"].startswith("HOLD_") for x in candidate_rows)
    return {
        "schema_version":SCHEMA,
        "mode":"READ_ONLY",
        "generated_at":now.astimezone(timezone.utc).isoformat(),
        "scout_research_candidates_inspected":len(candidate_rows),
        "plausible_business_domains_requiring_qualification":valid_candidates,
        "held_platform_duplicate_or_bad_domain_count":held,
        "reviewed_original_reddit_linkedin_tasks":len(tasks),
        "tasks_exactly_joined_to_scout_by_source_url":sum(x["exact_evidence_url_seen_in_current_scout"]
                                                          for x in tasks),
        "company_identity_promotions":0,
        "verified_commercial_buyers_created":0,
        "automated_outreach_sent":False,
        "database_writes":False,
        "execution_authority":"NONE",
        "scout_source_quality":candidate_rows,
        "original_intent_research_tasks":tasks,
    }
