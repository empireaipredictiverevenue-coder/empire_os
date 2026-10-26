"""One bounded first-party keyword-to-offer review for the EXISTING weekly GSC owner.

No new service/timer, Google credential, provider subscription, CRM, outreach or
publication. One allowlisted local GSC query-page GET is shared across markets.
Receipts live beside the original read-only weekly SEO report.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec, prepare_public_intent_offer_review,
)
from empire_os.public_intent_gsc_evidence_bridge import (
    LOOPBACK, MAX_BODY, MAX_ROWS, review_gsc_keyword_ideas,
)
from empire_os.public_intent_evidence_triage import build_intent_evidence_review_queue
from empire_os.search_intelligence.semantic_opportunity_review import review_semantic_opportunity

ROOT=Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
SCHEMA="empire.search.weekly_keyword_intent_evidence.v1"

# Explicitly approved *internal research* themes, not accounts or live offers.
# Each root remains stable from one review to the next for useful comparisons.
SEEDS=(
    IntentOfferSpec(
        market_key="us-commercial-roofing",
        seed_keyword="commercial roof repair",
        icp_key="commercial-roofing-operator",
        buyer_problem="Decide whether a leaking commercial roof needs repair or replacement",
        glossary_terms=("TPO roofing","PVC roofing","roof coating"),
    ),
    IntentOfferSpec(
        market_key="uk-heat-pump",
        seed_keyword="air source heat pump",
        icp_key="heat-pump-installer",
        buyer_problem="Understand installer requirements before a permitted survey",
        glossary_terms=("MCS certificate","heat loss survey"),
    ),
    IntentOfferSpec(
        market_key="b2b-revenue-assessment",
        seed_keyword="revenue operations audit",
        icp_key="b2b-saas-revenue-leader",
        buyer_problem="Reconcile marketing qualification proposals and settled sales",
        glossary_terms=("quote to cash","pipeline attribution"),
    ),
    IntentOfferSpec(
        market_key="b2b-tam-buyer-readiness",
        seed_keyword="how do i know which accounts in my tam are actually ready to buy right now",
        icp_key="enterprise-revenue-operator",
        buyer_problem="Identify buyer readiness based on evidence rather than market estimates",
    ),
)


def _read_gsc_packet(start: date, end: date, *, transport=None) -> dict:
    url=LOOPBACK+"?"+urlencode({
        "start_date":start.isoformat(),
        "end_date":end.isoformat(),
        "limit":MAX_ROWS,
    })
    if transport is None:
        def transport(target: str) -> bytes:
            req=Request(target,headers={"Accept":"application/json"},method="GET")
            with urlopen(req,timeout=10) as resp:
                if resp.status!=200:
                    raise ValueError("search_console_loopback_unavailable")
                return resp.read(MAX_BODY+1)
    body=transport(url)
    if not isinstance(body,bytes) or len(body)>MAX_BODY:
        raise ValueError("untrusted_gsc_response_size_or_type")
    data=json.loads(body)
    if not isinstance(data,dict):
        raise ValueError("gsc_source_must_be_object")
    return data


def build_weekly_keyword_intent_review(
    *, as_of: date, transport: Callable[[str],bytes] | None=None,
) -> dict[str, Any]:
    if type(as_of) is not date:
        raise ValueError("review_as_of_must_be_date")
    end=as_of-timedelta(days=3)  # Source-finalization margin.
    start=end-timedelta(days=6)
    themes=[]
    unmatched_first_party_rows = {}
    sensitive_query_pairs = set()
    matched_query_strings = set()
    observed_new_queries = []
    unmatched_count = None
    try:
        packet=_read_gsc_packet(start,end,transport=transport)
        # Validate real source through original GSC bridge before any result.
        for spec in SEEDS:
            research=prepare_public_intent_offer_review(spec)
            evidence=review_gsc_keyword_ideas(
                research,packet,start=start,end=end,today=as_of,
            )
            priority=build_intent_evidence_review_queue(research,evidence)
            evidence_rows=[
                {"keyword":row["keyword"],
                 "page_evidence":row["observed_query_page_rows"]}
                for row in priority["priority_ordered_candidates"]
                if row["observed_first_party_query"]
            ]
            # All four market themes use the same original query/page GSC GET.
            # Preserve unmatched *real* queries without inventing search demand.
            matched_query_strings.update(row["keyword"] for row in evidence_rows)
            for row in evidence["observed_other_queries"]:
                key=(row["query"],row["page_url"])
                if len(row["query"])>180 or "@" in row["query"]:
                    sensitive_query_pairs.add(key)
                else:
                    unmatched_first_party_rows[key]=row
            themes.append({
                "market_key":spec.market_key,
                "seed_keyword":spec.seed_keyword,
                "candidate_keyword_ideas":priority["candidate_count"],
                "first_party_exact_query_matches":priority["first_party_exact_match_count"],
                "observed_exact_query_page_evidence":evidence_rows,
                "next_research_priorities":[
                    {
                        "keyword":row["keyword"],
                        "review_priority":row["priority"],
                        "next_action":row["next_action"],
                    }
                    for row in priority["priority_ordered_candidates"][:5]
                ],
                "real_market_keyword_volume":None,
                "buyer_willingness_to_pay_verified":False,
            })
        unmatched_rows = [
            row for (query,_),row in unmatched_first_party_rows.items()
            if query not in matched_query_strings
        ]
        unmatched_count=len(unmatched_rows)
        for row in sorted(unmatched_rows,
                          key=lambda item:(item["query"],item["page_url"]))[:12]:
            semantic=review_semantic_opportunity(
                row["query"],source_kind="GSC_QUERY_PAGE",
                evidence_refs=(row["evidence_ref"],),
            )
            observed_new_queries.append({
                "query":row["query"],
                "owned_page_url":row["page_url"],
                "evidence_ref":row["evidence_ref"],
                "source_kind":"GSC_QUERY_PAGE",
                "matched_original_seed":False,
                "intent_label_heuristic":semantic["intent_label"],
                "semantic_sector_status":semantic["sector_review"]["status"],
                "owner_review_action":semantic["recommended_review_action"],
                "market_search_volume":None,
                "independent_serp_rank_verified":False,
                "ai_answer_citation_verified":False,
                "qualified_buyer_verified":False,
            })
        gsc_status="FIRST_PARTY_GSC_QUERY_PAGE_OBSERVED"
        count=packet["count"]
        reason=None
    except (OSError,ValueError,TypeError,TimeoutError,UnicodeError) as exc:
        # No fabricated zeros. Still provide a useful review of missing source.
        gsc_status="HELD_GSC_QUERY_PAGE_SOURCE_UNAVAILABLE_OR_UNVERIFIED"
        count=None
        reason=type(exc).__name__
        for spec in SEEDS:
            research=prepare_public_intent_offer_review(spec)
            triage=build_intent_evidence_review_queue(research)
            themes.append({
                "market_key":spec.market_key,
                "seed_keyword":spec.seed_keyword,
                "candidate_keyword_ideas":triage["candidate_count"],
                "first_party_exact_query_matches":None,
                "observed_exact_query_page_evidence":[],
                "next_research_priorities":[],
                "real_market_keyword_volume":None,
                "buyer_willingness_to_pay_verified":False,
            })
    return {
        "schema_version":SCHEMA,
        "mode":"READ_ONLY",
        "owner":"empire_os.search_intelligence.search_console",
        "existing_service_unit":"empire-seo-two-page-gsc-weekly.service",
        "as_of":as_of.isoformat(),
        "gsc_window":[start.isoformat(),end.isoformat()],
        "source_status":gsc_status,
        "source_error_type":reason,
        "original_query_page_rows_returned":count,
        "market_research_count":len(themes),
        "market_reviews":themes,
        "unmatched_first_party_query_page_rows":unmatched_count,
        "unmatched_first_party_semantic_review_preview":observed_new_queries,
        "source_query_rows_redacted_for_privacy":(
            len(sensitive_query_pairs) if unmatched_count is not None else None
        ),
        "semantic_intent_is_heuristic_not_verified_demand":True,
        "market_search_volume":None,
        "customer_leads_qualified":None,
        "sale_or_revenue_verified":False,
        "query_page_data_not_market_volume":True,
        "one_original_loopback_get_max":True,
        "paid_provider_calls":0,
        "search_fabric_calls":0,
        "new_external_model_calls":0,
        "database_writes":False,
        "outbound_sent":False,
        "payment_action":False,
        "publishing_authorized":False,
        "execution_authority":"none",
    }


def run_weekly_keyword_intent_review(
    *, as_of: date,
    write_private: bool=False,
    transport: Callable[[str],bytes] | None=None,
    root: Path=ROOT,
) -> dict[str, Any]:
    report=build_weekly_keyword_intent_review(as_of=as_of,transport=transport)
    if not write_private:
        return report
    # Same private receipt owner/path as existing SEO weekly report; no new unit.
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077 or root.stat().st_uid!=os.geteuid():
        raise ValueError("SEO_WEEKLY_OWNER_DIRECTORY_UNSAFE")
    lock_fd=os.open(root/".keyword-intent.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lock_fd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        target=root/f"weekly_keyword_intent_{as_of.isoformat()}.json"
        if target.exists() or target.is_symlink():
            raise ValueError("WEEKLY_KEYWORD_RECEIPT_EXISTS_NO_OVERWRITE")
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,"w",encoding="utf8") as out:
                json.dump(report,out,sort_keys=True,indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return {
        "status":"PRIVATE_WEEKLY_KEYWORD_REVIEW_WRITTEN",
        "as_of":as_of.isoformat(),
        "receipt":str(target),
        "receipt_sha256":sha256(target.read_bytes()).hexdigest(),
        "gsc_status":report["source_status"],
        "market_count":len(report["market_reviews"]),
        "outbound_sent":False,
        "database_writes":False,
        "execution_authority":"none",
    }
