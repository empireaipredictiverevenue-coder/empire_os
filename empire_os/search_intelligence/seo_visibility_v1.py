"""Semrush-style FIRST-PARTY visibility & keyword overlap, not a SERP rank crawler.

Read original GSC query/page observations in two disjoint finalized windows.
Do not invent traffic estimates, search volume, keyword difficulty, competitor
keywords, unique visitors, SERP rankings, conversion or revenue.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import math
from typing import Any, Mapping
from urllib.parse import urlsplit

SITE="sc-domain:empire-ai.co.uk"
ORIGIN="https://empire-ai.co.uk"
MAX_ROWS=250
MAX_QUERY_LENGTH=230
MAX_URL_LENGTH=480


class VisibilityEvidenceHeld(ValueError):
    pass


def _owned(url: Any) -> tuple[str,str]:
    if not isinstance(url,str) or len(url)>MAX_URL_LENGTH:
        raise VisibilityEvidenceHeld("GSC_PAGE_INVALID_URL")
    try:
        u=urlsplit(url)
    except ValueError as err:
        raise VisibilityEvidenceHeld("GSC_PAGE_INVALID_URL") from err
    if (u.scheme!="https" or u.netloc not in ("empire-ai.co.uk","www.empire-ai.co.uk")
        or u.username or u.password or u.query or u.fragment or not u.path.startswith("/")
        or "//" in u.path):
        raise VisibilityEvidenceHeld("GSC_PAGE_UNTRUSTED_SOURCE")
    # Query/page metrics for www and apex stay SEPARATE. This normalizes only
    # an intent-matching key; it does not rewrite historical canonical claims.
    path=u.path.rstrip("/") or "/"
    return u.netloc,path


def _validated(packet: Mapping[str,Any], period: tuple[date,date]) -> dict:
    if (not isinstance(packet,Mapping)
        or packet.get("available") is not True
        or packet.get("source")!="google_search_console"
        or packet.get("site_url")!=SITE
        or type(packet.get("count")) is not int
        or type(packet.get("limit")) is not int
        or packet["limit"]<1 or packet["limit"]>MAX_ROWS
        or not isinstance(packet.get("items"),list)
        or packet["count"]!=len(packet["items"])
        or packet["count"]>=packet["limit"]):
        raise VisibilityEvidenceHeld("BOUNDED_COMPLETE_GSC_QUERY_PAGE_SOURCE_REQUIRED")
    if period[1]<period[0] or (period[1]-period[0]).days>30:
        raise VisibilityEvidenceHeld("INVALID_GSC_WINDOW")
    cleaned={}
    for row in packet["items"]:
        if not isinstance(row,Mapping):
            raise VisibilityEvidenceHeld("INVALID_QUERY_PAGE_ROW")
        keys=row.get("keys")
        if (not isinstance(keys,list) or len(keys)!=2 or
            not isinstance(keys[0],str) or not 1<=len(keys[0].strip())<=MAX_QUERY_LENGTH):
            raise VisibilityEvidenceHeld("EXACT_QUERY_PAGE_DIMENSIONS_REQUIRED")
        domain,path=_owned(keys[1])
        clicks,imp,pos=row.get("clicks"),row.get("impressions"),row.get("position")
        if (type(clicks) is not int or type(imp) is not int or clicks<0
            or imp<1 or clicks>imp or isinstance(pos,bool)
            or not isinstance(pos,(int,float)) or not math.isfinite(pos)
            or pos<1 or pos>1000):
            raise VisibilityEvidenceHeld("GSC_QUERY_PAGE_METRICS_INVALID")
        key=(keys[0].casefold().strip(),keys[1])
        if key in cleaned:
            raise VisibilityEvidenceHeld("DUPLICATE_EXACT_GSC_QUERY_PAGE")
        cleaned[key]={
            "query":keys[0].strip(),"url":keys[1],"host":domain,
            "path":path,"impressions":imp,"clicks":clicks,
            "gsc_avg_position":float(pos),
        }
    return cleaned


def build_visibility_review(
    previous:Mapping[str,Any],current:Mapping[str,Any],
    *, previous_window:tuple[date,date],current_window:tuple[date,date],as_of:date,
) -> dict:
    if (type(as_of) is not date or current_window[1]>as_of
        or previous_window[1]>=current_window[0]
        or (current_window[0]-previous_window[1]).days!=1
        or (previous_window[1]-previous_window[0]).days!=
           (current_window[1]-current_window[0]).days):
        raise VisibilityEvidenceHeld("NONCONTIGUOUS_OR_MISMATCHED_GSC_WINDOWS")
    old=_validated(previous,previous_window)
    recent=_validated(current,current_window)
    grouped=defaultdict(lambda:{"old":[],"new":[]})
    for row in old.values():
        grouped[row["query"].casefold()]["old"].append(row)
    for row in recent.values():
        grouped[row["query"].casefold()]["new"].append(row)
    terms=[]
    for query,windows in grouped.items():
        before=windows["old"]
        after=windows["new"]
        def summary(rows):
            impressions=sum(r["impressions"] for r in rows)
            clicks=sum(r["clicks"] for r in rows)
            return {
                "visible_impressions":impressions if rows else None,
                "visible_clicks":clicks if rows else None,
                "gsc_impression_weighted_avg_position":(
                    round(sum(r["gsc_avg_position"]*r["impressions"] for r in rows)
                        /impressions,2) if rows else None),
                "exact_page_count":len(rows),
            }
        prev=summary(before)
        curr=summary(after)
        # Never declare missing sampled query/page data to mean zero searches.
        qtrend=("UNOBSERVED_IN_CURRENT_SAMPLE" if not after
                else "NEW_IN_CURRENT_SAMPLE" if not before
                else "MATCHED_WINDOWS")
        matching_paths=sorted({r["path"] for r in after})
        host_alias=any(len({r["host"] for r in after if r["path"]==path})>1
                       for path in matching_paths)
        historical_hosts=sorted({r["path"] for r in before})
        historical_alias=any(len({r["host"] for r in before if r["path"]==path})>1
                             for path in historical_hosts)
        same_query_pages=len(set(matching_paths))>1
        commercial_relevance=any(path in ("/commercial","/predictive-revenue")
            or path.startswith("/industries/")
            or path=="/aeo/accounting/TAM" for path in matching_paths)
        delta=(curr["visible_impressions"]-prev["visible_impressions"]
            if before and after else None)
        terms.append({
            "query":query,
            "previous":prev,"current":curr,
            "historical_sample_status":qtrend,
            "sampled_impression_difference":delta,
            "current_observed_exact_pages":[{
                "url":r["url"],"impressions":r["impressions"],
                "clicks":r["clicks"],"gsc_avg_position":round(r["gsc_avg_position"],2),
            } for r in sorted(after,key=lambda r:(-r["impressions"],r["url"]))],
            "multiple_hosts_same_path_in_sample":host_alias,
            "historical_hosts_same_path_in_previous_sample":historical_alias,
            "multiple_distinct_pages_for_query_in_sample":same_query_pages,
            "cannibalisation_verified":False,
            "commercial_topic_relevance_observed":commercial_relevance,
            "keyword_monthly_search_volume":None,
            "keyword_difficulty_score":None,
            "independent_live_serp_rank":None,
            "verified_organic_sessions":None,
            "qualified_enquiries":None,
            "verified_revenue":None,
            "next_original_owner_action":(
                "VERIFY_CURRENT_WWW_APEX_CANONICAL_NOT_HISTORICAL_ALIAS" if host_alias
                else "REVIEW_ORIGINAL_DISTINCT_PAGE_INTENTS_WITHOUT_AUTO_CANONICAL"
                     if same_query_pages
                else "CHECK_RELEVANT_EXISTING_PAGE_ORIGINAL_CONTENT_AND_INDEXING"
                     if commercial_relevance
                else "OBSERVE_WITHOUT_CREATING_SPECULATIVE_COMMERCIAL_PAGE"),
        })
    terms.sort(key=lambda x:(
        not x["commercial_topic_relevance_observed"],
        -int(x["current"]["visible_impressions"] or 0),
        x["query"],
    ))
    def totals(data):
        return {
            "returned_query_page_rows":len(data),
            "visible_query_page_impressions":sum(row["impressions"] for row in data.values()),
            "visible_query_page_clicks":sum(row["clicks"] for row in data.values()),
        }
    return {
        "schema_version":"empire.search.original_gsc_visibility_overlap.v1",
        "status":"REAL_GSC_QUERY_PAGE_VISIBILITY_OBSERVED",
        "source":"google_search_console",
        "site_url":SITE,
        "as_of":as_of.isoformat(),
        "previous_window":[x.isoformat() for x in previous_window],
        "current_window":[x.isoformat() for x in current_window],
        "previous_sample":totals(old),"current_sample":totals(recent),
        "observed_queries":len(terms),
        "commercial_relevant_queries_observed":sum(x["commercial_topic_relevance_observed"]
                                                   for x in terms),
        "multi_page_query_overlap_candidates":sum(
            x["multiple_distinct_pages_for_query_in_sample"] for x in terms),
        "historical_www_apex_overlap_candidates":sum(
            x["historical_hosts_same_path_in_previous_sample"] for x in terms),
        "current_www_apex_overlap_candidates":sum(
            x["multiple_hosts_same_path_in_sample"] for x in terms),
        "queries":terms,
        "original_rank_history_adapter_unchanged":True,
        "missing_query_is_not_zero_search_demand":True,
        "gsc_average_position_is_not_independent_rank_tracker":True,
        "entire_site_traffic_coverage_verified":False,
        "competitor_rankings_verified":False,
        "cannibalisation_auto_fix_authorized":False,
        "new_pages_authorized":False,
        "no_paid_provider_requests":True,
        "outbound_sent":False,"site_changed":False,
        "database_writes":False,"verified_revenue":None,
        "execution_authority":"OBSERVE_FIRST_PARTY_PROVENANCE",
    }
