"""Evidence-led research order, never a numeric ranking or demand forecast.

Reuses original Keyword Universe records and verified GSC exact observations.
A keyword with no GSC row may still be a good market research candidate;
it cannot be labelled commercially proven, traffic-ready, or profitable.
"""
from __future__ import annotations
from typing import Any, Mapping
from empire_os.public_intent_offer_method_bridge import SCHEMA as IDEA_SCHEMA

HIGH_INTENT={"commercial","comparison","product","territory","agency_white_label","enterprise_api"}


def build_intent_evidence_review_queue(
    research: Mapping[str, Any],
    gsc_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if research.get("schema_version")!=IDEA_SCHEMA:
        raise ValueError("original_keyword_research_required")
    canonical=research.get("universe",{}).get("keywords",[])
    if not isinstance(canonical,list):
        raise ValueError("original_keyword_universe_required")
    observed={}
    if gsc_review is not None:
        if (gsc_review.get("schema_version")!="empire.search.original_public_method_gsc_query_review.v1"
                or gsc_review.get("owner")!="empire_os.search_intelligence.search_console"
                or gsc_review.get("site_url")!="sc-domain:empire-ai.co.uk"
                or not isinstance(gsc_review.get("ideas"),list)):
            raise ValueError("verified_canonical_gsc_review_required")
        observed={row["keyword"]:row for row in gsc_review["ideas"]}
    rows=[]
    for entry in canonical:
        record=entry["record"]
        keyword=record["keyword"]
        assert keyword
        g=observed.get(keyword,{})
        first_party=g.get("status")=="EXACT_QUERY_PAGE_OBSERVED"
        commercial=record["intent_class"] in HIGH_INTENT
        priority=(
            "P1_REVIEW_FIRST_PARTY_QUERY_MATCH" if first_party
            else "P2_REVIEW_BUYER_INTENT_HYPOTHESIS" if commercial
            else "P3_REVIEW_EDUCATIONAL_HYPOTHESIS"
        )
        rows.append({
            "keyword":keyword,
            "cluster_key":record["cluster_key"],
            "intent_class":record["intent_class"],
            "product_key":record["product_key"],
            "asset_type":record["asset_type"],
            "cta_key":record["cta_key"],
            "priority":priority,
            "observed_first_party_query":first_party,
            "gsc_observed_query_page_count":len(g.get("observed_query_page_rows",[])),
            "observed_query_page_rows":g.get("observed_query_page_rows",[]),
            "search_volume":None,
            "keyword_difficulty":None,
            "commercial_buyer_verified":False,
            "content_publish_approved":False,
            "next_action":(
                "REVIEW_ACTUAL_QUERY_AND_PAGE_INTENT_WITH_OWNER"
                if first_party else
                "OBTAIN_ORIGINAL_SERP_OR_FIRST_PARTY_QUERY_EVIDENCE"
            ),
        })
    rows.sort(key=lambda r:(
        0 if r["priority"].startswith("P1") else
        1 if r["priority"].startswith("P2") else 2,
        r["keyword"],
    ))
    return {
        "schema_version":"empire.search.intent_evidence_triage.v1",
        "owner":"empire_os.keyword_universe",
        "mode":"OBSERVE",
        "candidate_count":len(rows),
        "source_gsc_review_available":gsc_review is not None,
        "first_party_exact_match_count":sum(x["observed_first_party_query"] for x in rows),
        "research_priority_kind":"EVIDENCE_REVIEW_QUEUE_NOT_SERP_RANK",
        "priority_ordered_candidates":rows,
        "economic_priority_score":None,
        "search_volume_claimed":False,
        "seo_difficulty_claimed":False,
        "revenue_claimed":False,
        "auto_publish":False,
        "auto_outbound":False,
        "database_writes":False,
        "execution_authority":"none",
    }
