"""First-party Search Console query/page evidence for existing Keyword Universe ideas.

Only consumes the existing Search Intelligence loopback GSC reader and preserves
query/page-level evidence. It neither impersonates Google nor infers market
keyword volume, CPC, keyword difficulty, buyer intent, or realised revenue.
"""
from __future__ import annotations

from datetime import date, timedelta, datetime, timezone
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from empire_os.public_intent_offer_method_bridge import SCHEMA as IDEA_SCHEMA

PROPERTY = "sc-domain:empire-ai.co.uk"
LOOPBACK = "http://127.0.0.1:8771/v1/search/search-console/observations"
MAX_ROWS = 250
MAX_BODY = 150_000
MAX_DAYS = 31


class KeywordGscEvidenceError(ValueError):
    pass


def _safe_window(start: date, end: date, *, today: date) -> None:
    if (not isinstance(start, date) or not isinstance(end, date)
            or end < start or (end-start).days >= MAX_DAYS
            or end > today-timedelta(days=3)):
        raise KeywordGscEvidenceError("finalized_bounded_past_date_window_required")


def _owned_url(value: str) -> bool:
    try:
        p=urlsplit(value)
        return (p.scheme in ("https", "http")
                and (p.hostname or "").lower() in ("empire-ai.co.uk", "www.empire-ai.co.uk")
                and not p.username and not p.password
                and p.port in (None, 443 if p.scheme=="https" else 80)
                and not p.query and not p.fragment)
    except ValueError:
        return False


def _metric(value: Any, *, integer: bool = False) -> float | None:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    if integer and not float(value).is_integer():
        return None
    return float(value)


def review_gsc_keyword_ideas(
    research: Mapping[str, Any], packet: Mapping[str, Any],
    *, start: date, end: date, today: date,
) -> dict[str, Any]:
    """Match *exact* GSC query text to already-derived ideas, do not auto-score."""
    _safe_window(start,end,today=today)
    if (not isinstance(research, Mapping)
            or research.get("schema_version") != IDEA_SCHEMA
            or not isinstance(research.get("keyword_candidates"), list)):
        raise KeywordGscEvidenceError("existing_research_ideas_required")
    if (not isinstance(packet, Mapping)
            or packet.get("source")!="google_search_console"
            or packet.get("site_url")!=PROPERTY
            or packet.get("available") is not True
            or type(packet.get("count")) is not int
            or type(packet.get("limit")) is not int):
        raise KeywordGscEvidenceError("original_first_party_gsc_source_required")
    rows=packet.get("items")
    count,limit=packet["count"],packet["limit"]
    if (not isinstance(rows,list) or count!=len(rows)
            or not 1 <= limit <= MAX_ROWS or count>limit):
        raise KeywordGscEvidenceError("bounded_query_page_row_count_required")
    matches={s["keyword"]:[] for s in research["keyword_candidates"]}
    if len(matches)!=len(research["keyword_candidates"]):
        raise KeywordGscEvidenceError("duplicate_original_keyword_idea")
    seen=set()
    disclosed=[]
    for row in rows:
        if not isinstance(row,Mapping):
            raise KeywordGscEvidenceError("invalid_gsc_query_page_row")
        keys=row.get("keys")
        if (not isinstance(keys,list) or len(keys)!=2 or
                not all(isinstance(x,str) for x in keys)):
            raise KeywordGscEvidenceError("exact_query_and_page_dimensions_required")
        keyword=" ".join(keys[0].casefold().split())
        page=keys[1]
        if not keyword or not _owned_url(page):
            raise KeywordGscEvidenceError("non_first_party_or_empty_gsc_keys")
        pair=(keyword,page)
        if pair in seen:
            raise KeywordGscEvidenceError("duplicate_gsc_query_page_pair")
        seen.add(pair)
        clicks=_metric(row.get("clicks"), integer=True)
        impressions=_metric(row.get("impressions"), integer=True)
        ctr=_metric(row.get("ctr"))
        pos=_metric(row.get("position"))
        if (None in (clicks,impressions,ctr,pos) or clicks>impressions
                or ctr>1 or pos>1000 or
                (impressions>0 and abs(ctr-clicks/impressions)>0.02)):
            raise KeywordGscEvidenceError("invalid_gsc_query_page_metrics")
        evidence_ref="gsc-query-page-sha256:"+sha256(
            f"{PROPERTY}|{start}|{end}|{keyword}|{page}|{clicks:g}|{impressions:g}|{ctr:g}|{pos:g}".encode()
        ).hexdigest()
        observation={
            "query":keyword, "page_url":page,
            "reported_clicks":int(clicks),
            "reported_impressions":int(impressions),
            "reported_ctr":ctr,
            "gsc_reported_average_position":pos,
            "evidence_ref":evidence_ref,
            "dimension":"query_page",
        }
        if keyword in matches:
            matches[keyword].append(observation)
        else:
            disclosed.append({"query":keyword,"page_url":page,"evidence_ref":evidence_ref,
                              "review_state":"OBSERVED_NON_MATCH_NOT_DROPPED"})

    review=[]
    for query in matches:
        observed=matches[query]
        review.append({
            "keyword":query,
            "status":"EXACT_QUERY_PAGE_OBSERVED" if observed else "NOT_IN_RETURNED_GSC_SAMPLE",
            "observed_query_page_rows":observed,
            "keyword_search_volume":None,
            "demand_or_competition_score":None,
            "buyer_intent_verified":False,
            "ranking_position_independently_verified":False,
            "indexation_verified":False,
            "revenue_verified":False,
        })
    return {
        "schema_version":"empire.search.original_public_method_gsc_query_review.v1",
        "mode":"READ_ONLY",
        "owner":"empire_os.search_intelligence.search_console",
        "site_url":PROPERTY,
        "window":[start.isoformat(),end.isoformat()],
        "gsc_query_page_rows":count,
        "candidate_queries":len(review),
        "exactly_observed_candidate_queries":sum(bool(x["observed_query_page_rows"]) for x in review),
        "observed_other_queries":disclosed,
        "ideas":review,
        "gsc_query_page_sample_not_total_keyword_market":True,
        "gsc_sample_may_omit_anonymised_searches":True,
        "gsc_average_position_not_independent_serp_rank":True,
        "query_page_counts_not_sitewide_traffic":True,
        "estimated_search_volume":None,
        "estimated_cpc":None,
        "estimated_difficulty":None,
        "attributed_revenue":None,
        "paid_api_calls":0,
        "outbound_sent":False,
        "database_writes":False,
        "publishing_authorized":False,
        "execution_authority":"none",
    }


def read_original_loopback_gsc(
    research: Mapping[str, Any], *,
    start: date, end: date, today: date | None=None,
    transport=None,
) -> dict[str, Any]:
    """At most one GET to the original loopback; unavailable stays HELD."""
    nowday=today or datetime.now(timezone.utc).date()
    _safe_window(start,end,today=nowday)
    params=urlencode({"start_date":start.isoformat(),
                      "end_date":end.isoformat(),"limit":MAX_ROWS})
    target=LOOPBACK+"?"+params
    if transport is None:
        def transport(url: str) -> bytes:
            req=Request(url,headers={"Accept":"application/json"},method="GET")
            with urlopen(req,timeout=8) as resp:
                if resp.status!=200:
                    raise KeywordGscEvidenceError("gsc_loopback_get_failed")
                return resp.read(MAX_BODY+1)
    try:
        payload=transport(target)
        if not isinstance(payload,bytes) or len(payload)>MAX_BODY:
            raise KeywordGscEvidenceError("gsc_payload_invalid_size")
        raw=json.loads(payload)
        return review_gsc_keyword_ideas(research,raw,start=start,end=end,today=nowday)
    except (OSError,ValueError,TimeoutError,TypeError,UnicodeError):
        return {
            "schema_version":"empire.search.original_public_method_gsc_query_review.v1",
            "status":"HELD_GSC_QUERY_PAGE_SOURCE_UNAVAILABLE_OR_UNVERIFIED",
            "mode":"READ_ONLY","owner":"empire_os.search_intelligence.search_console",
            "window":[start.isoformat(),end.isoformat()],
            "estimated_search_volume":None,
            "observed_candidate_queries":None,
            "outbound_sent":False,"database_writes":False,
            "publishing_authorized":False,"execution_authority":"none",
        }
