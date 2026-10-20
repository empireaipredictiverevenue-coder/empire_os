"""Real-world event / newsjacking research bridge for Predictive Revenue.

Use existing Event Truth, Media Trend Fusion, territory evidence and Strategy
owner contracts. An article is not original physical truth, a buyer, demand,
damage, a calibrated forecast or spend/publishing authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from empire_os.real_world_event_intelligence import (
    EventAssertionTruth, assertion_truth_from_source, source_timestamp,
)
from empire_os.media_trend_fusion import MediaTrendSignal, fuse_media_trend
from empire_os.predictive_market_evidence_binding import SCHEMA as TERRITORY_SCHEMA
from empire_os.predictive_market_economic_twin import DRIVERS

SCHEMA = "empire.predictive_revenue.real_world_newsjack_research.v1"
SOURCE_STATUS = frozenset(("official_notice","reported_article","forecast_or_outlook","unconfirmed"))
CATEGORY = frozenset((
    "regulation","competitor","materials","supply_chain","storm_weather",
    "infrastructure","search_platform","economic_policy","housing_permits",
    "product_launch","customer_problem","market_demand",
))
RISK = frozenset(("routine","public_safety","disaster","death_or_injury","conflict","political","private_person"))
SOURCE_FIELDS = frozenset((
    "event_key","source_origin_key","source_record_sha256","source_family",
    "source_status","event_category","news_context_safety","niche_key",
    "geography_key","first_published_at","source_observed_at",
    "headline_sha256","evidence_rights","claim_certainty","story_cluster_key",
))
SOURCE_FAMILIES = frozenset(("news","official","community","competitor","search"))
SAFE_RIGHTS = "INTERNAL_RESEARCH_METADATA_ONLY"
KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,95}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_AGE = timedelta(hours=72)
TYPE_TO_DRIVER = {
    "regulation":"regulatory_change","competitor":"competitor_response",
    "materials":"material_cost","supply_chain":"supply_chain",
    "storm_weather":"weather_storm","infrastructure":"supply_chain",
    "search_platform":"search_ai_change","economic_policy":"seasonal_demand",
    "housing_permits":"seasonal_demand","product_launch":"consumer_preference",
    "customer_problem":"consumer_preference","market_demand":"seasonal_demand",
}
assert set(TYPE_TO_DRIVER)==CATEGORY
assert set(TYPE_TO_DRIVER.values()).issubset(DRIVERS)


def _key(v: Any, label: str) -> str:
    if not isinstance(v,str) or not KEY.fullmatch(v):
        raise ValueError("bounded "+label+" identifier required")
    return v


def _sha(v: Any, label: str) -> str:
    if not isinstance(v,str) or not SHA.fullmatch(v):
        raise ValueError("opaque "+label+" digest required")
    return v


def _hold(code: str) -> dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"REAL_WORLD_EVENT_SOURCE_HOLD","hold_code":code,
        "event_research_cards":[],"event_cluster_count":None,
        "source_article_count":None,"duplicate_source_records_count":None,
        "source_article_is_independent_event_truth":False,
        "news_attention_is_authenticated_buyer_demand":False,
        "events_are_paid_sales":False,"calibrated_profit_uplift_available":False,
        "media_publication_authorized":False,"outbound_sent":False,
        "database_writes":False,"execution_authority":"none",
    }


def review_newsjack_event_research(
    records: Sequence[Mapping[str,Any]],
    territory: Mapping[str,Any], *,
    as_of:datetime,
) -> dict[str,Any]:
    """Owned source metadata only; never fetch, parse, publish or contact."""
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware decision clock required")
    if (not isinstance(territory,Mapping)
            or territory.get("schema_version")!=TERRITORY_SCHEMA
            or territory.get("status")!="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
            or territory.get("execution_authority")!="none"
            or territory.get("live_economic_forecast_issuance_authorized") is not False):
        return _hold("TERRITORY_SOURCE_NOT_READY")
    cards=territory.get("territory_research_cards")
    if (not isinstance(cards,list)
            or type(territory.get("market_count")) is not int
            or len(cards)!=territory["market_count"]
            or len(cards)>200
            or not isinstance(territory.get("source_revision_fingerprint"),str)
            or not SHA.fullmatch(territory["source_revision_fingerprint"])):
        return _hold("TERRITORY_CARDS_UNTRUSTED")
    market_index={}
    for row in cards:
        if not isinstance(row,Mapping):
            return _hold("TERRITORY_CARDS_UNTRUSTED")
        niche=row.get("market_niche_key")
        geo=row.get("market_geography_key")
        if not isinstance(niche,str) or not isinstance(geo,str):
            return _hold("TERRITORY_CARDS_UNTRUSTED")
        identity=(_key(niche,"niche"),_key(geo,"geography"))
        if identity in market_index or row.get("source_revision_fingerprint") is None:
            return _hold("TERRITORY_CARDS_UNTRUSTED")
        market_index[identity]=row
    if not isinstance(records,(list,tuple)) or len(records)>120:
        raise ValueError("bounded original source metadata required")
    now=as_of.astimezone(timezone.utc)
    unique={}
    duplicates=0
    try:
        for row in records:
            if not isinstance(row,Mapping) or set(row)!=SOURCE_FIELDS:
                raise ValueError("exact news event source metadata required")
            for k in ("event_key","source_origin_key","story_cluster_key"):
                _key(row[k],k)
            for k in ("niche_key","geography_key"):
                _key(row[k],k)
            for k in ("source_record_sha256","headline_sha256"):
                _sha(row[k],k)
            if (row["source_family"] not in SOURCE_FAMILIES
                    or row["source_status"] not in SOURCE_STATUS
                    or row["event_category"] not in CATEGORY
                    or row["news_context_safety"] not in RISK
                    or row["evidence_rights"]!=SAFE_RIGHTS
                    or not isinstance(row["claim_certainty"],str)
                    or row["claim_certainty"] not in (
                        "observed","likely","possible","forecast","unknown"
                    )):
                raise ValueError("untrusted or unlicensed news metadata")
            if (row["source_status"]=="official_notice"
                    and row["source_family"]!="official"):
                raise ValueError("press coverage is not an official notice")
            if (row["source_status"]=="forecast_or_outlook"
                    and row["claim_certainty"]=="observed"):
                raise ValueError("forecast may not be relabelled observed")
            published=source_timestamp(row["first_published_at"])
            seen_at=source_timestamp(row["source_observed_at"])
            if (published>seen_at or seen_at>now
                    or published>now or now-published>MAX_AGE):
                raise ValueError("event source is stale future or time-inconsistent")
            # Hashes identify revisions; do not infer distinct original sources
            # from syndicated publishers or multiple stories repeating a claim.
            key=(row["source_origin_key"],row["source_record_sha256"])
            if key in unique:
                if unique[key]!=dict(row):
                    raise ValueError("same origin and digest with conflicting identity")
                duplicates+=1
                continue
            unique[key]=dict(row)
    except (ValueError,TypeError,KeyError):
        return _hold("UNTRUSTED_OR_STALE_EVENT_SOURCE")
    groups={}
    for r in unique.values():
        group=r["story_cluster_key"]
        identity=(r["event_key"],r["niche_key"],r["geography_key"],r["event_category"])
        if group in groups and groups[group]["identity"]!=identity:
            return _hold("EVENT_CLUSTER_IDENTITY_COLLISION")
        groups.setdefault(group,{"identity":identity,"rows":[]})["rows"].append(r)
    outputs=[]
    for group_key,bundle in groups.items():
        event_key,niche,geo,category=bundle["identity"]
        src=sorted(bundle["rows"],key=lambda x:(x["source_origin_key"],x["source_record_sha256"]))
        matched=market_index.get((niche,geo))
        # There is no provider-origin independence attestation. Multiple
        # publishers or feeds can be repeating the same wire/source.
        origin_count=len({r["source_origin_key"] for r in src})
        independent_count_verified=None
        safety={r["news_context_safety"] for r in src}
        sensitive=bool(safety-{"routine"})
        uncertain=any(
            r["source_status"]=="unconfirmed" or r["claim_certainty"] in ("possible","unknown","forecast")
            for r in src
        )
        media_signals=[
            MediaTrendSignal(topic=event_key,source_family="news" if r["source_family"]=="official" else r["source_family"],
                             velocity=None,evidence_refs=(r["source_record_sha256"],),
                             observed_at=r["source_observed_at"],
                             source_component="newsjack_source_metadata")
            for r in src
        ]
        trend=fuse_media_trend(event_key,media_signals)
        # Safety-first decision: a company can research any public event but
        # cannot build promotional campaigns around disasters, deaths, violence
        # or uncertain reports through this connector.
        if matched is None:
            recommendation="RESEARCH_GEOGRAPHIC_AND_NICHE_BINDING"
        elif sensitive:
            recommendation="FACTUAL_PUBLIC_SAFETY_REVIEW_ONLY"
        elif uncertain:
            recommendation="CORROBORATE_ORIGINAL_EVENT_CLAIM"
        else:
            recommendation="DRAFT_TIMELY_CONTEXTUAL_RESEARCH_BRIEF_FOR_REVIEW"
        published=min(source_timestamp(r["first_published_at"]) for r in src)
        latency_h=round((now-published).total_seconds()/3600,3)
        detection_h=round((min(source_timestamp(r["source_observed_at"]) for r in src)-published).total_seconds()/3600,3)
        priority=round((35 if matched is not None else 0)
                       +(20 if latency_h<=12 else 10 if latency_h<=36 else 3)
                       +(10 if any(r["source_status"]=="official_notice" for r in src) else 0)
                       +(5 if not uncertain else 0),2)
        identity_ref=sha256(json.dumps({
            "event":event_key,"geo":geo,"niche":niche,
            "source_metadata_revisions":sorted(
                sha256(json.dumps(r,sort_keys=True,separators=(",",":"),
                                   allow_nan=False).encode()).hexdigest()
                for r in src
            ),
        },sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        outputs.append({
            "event_key":event_key,"story_cluster_key":group_key,
            "event_source_revision_sha256":identity_ref,
            "niche_key":niche,"geography_key":geo,"category":category,
            "first_observed_publication_at":published.isoformat(),
            "hours_since_first_publication":latency_h,
            "source_first_detection_lag_hours":detection_h,
            "research_priority_heuristic_not_buy_probability":priority,
            "measured_incremental_business_value_minor":None,
            "attributed_campaign_incremental_revenue_minor":None,
            "bounded_research_urgency_hours_remaining":max(0,round(72-latency_h,3)),
            "reported_source_records":len(src),
            "distinct_claimed_origins":origin_count,
            "independent_origins_verified":independent_count_verified,
            "media_trend_state":trend["trend_state"],
            "media_attention_is_purchase_probability":False,
            "source_assertion_classes":sorted({
                assertion_truth_from_source(
                    certainty=r["claim_certainty"],
                    message_type="forecast" if r["source_status"]=="forecast_or_outlook" else None,
                ).value for r in src
            }),
            "source_claim_is_verified_event_truth":False,
            "source_licence_allows_quote_or_resale":False,
            "news_safety_review_required":sensitive,
            "event_uncertain_or_forecast":uncertain,
            "territory_exact_research_match":matched is not None,
            "market_source_revision_sha256":(
                matched["source_revision_fingerprint"] if matched else None
            ),
            "market_source_evidence_is_verified_buyer_demand":False,
            "strategy_driver_hypothesis":TYPE_TO_DRIVER[category],
            "driver_multiplier_inferred_from_news":False,
            "hypothetical_economic_twin_recalculated":False,
            "original_quant_forecast_registered":False,
            "playbook_owner":(
                "existing_storm_spatial_and_safety_owner" if category=="storm_weather"
                else "existing_strategy_seo_aeo_geo_and_market_research_owners"
            ),
            "proposed_playbook":recommendation,
            "commercial_publication_or_outreach_approved":False,
        })
    outputs.sort(key=lambda v:(-int(v["territory_exact_research_match"]),
                                v["hours_since_first_publication"],v["event_key"]))
    return {
        **_hold("NONE"),"status":"NEWSJACK_RESEARCH_SIGNAL_TRIAGE_READY",
        "hold_code":None,
        "territory_source_revision_sha256":territory["source_revision_fingerprint"],
        "event_cluster_count":len(outputs),
        "source_article_count":len(unique),
        "duplicate_source_records_count":duplicates,
        "event_research_cards":outputs,
        "original_publisher_independence_authentication_available":False,
        "real_time_news_collection_activated":False,
        "new_source_rss_or_gdelt_api_connected":False,
        "scenario_shocks_require_separate_explicit_assumptions":True,
        "sensitive_events_have_promotional_block":True,
    }


def bind_newsjack_research_to_economic_twin(
    event_review: Mapping[str,Any],
    *,
    event_key:str,
    twin:Mapping[str,Any],
    territory_link:Mapping[str,Any],
) -> dict[str,Any]:
    """Existing territory/twin owners must independently bind the same cohort.

    An event is a prompt to TEST explicit economic stress assumptions, never
    a multiplier estimated by the news article or an executable campaign.
    """
    from empire_os.predictive_market_economic_twin import SCHEMA as TWIN_SCHEMA
    if not isinstance(event_review,Mapping) or (
        event_review.get("schema_version") != SCHEMA
        or event_review.get("status") != "NEWSJACK_RESEARCH_SIGNAL_TRIAGE_READY"
        or event_review.get("execution_authority") != "none"
        or event_review.get("media_publication_authorized") is not False
    ):
        raise ValueError("reviewed original event research packet required")
    if not isinstance(twin,Mapping) or (
        twin.get("schema_version") != TWIN_SCHEMA
        or twin.get("status") != "HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
        or twin.get("execution_authority") != "none"
        or twin.get("source_market_conditions_authenticated") is not False
        or twin.get("original_forecast_registered") is not False
        or twin.get("market_shock_applied_to_production") is not False
    ):
        raise ValueError("original hypothetical market twin required")
    if not isinstance(territory_link,Mapping) or (
        territory_link.get("schema_version")
        != "empire.predictive_revenue.territory_twin_research_link.v1"
        or territory_link.get("status") != "EXACT_TEXT_TERRITORY_RESEARCH_LINK_ONLY"
        or territory_link.get("research_territory_binding_present") is not True
        or territory_link.get("economic_scenario_authentic") is not False
        or territory_link.get("execution_authority") != "none"
    ):
        raise ValueError("source-review territory binding required")
    event_key=_key(event_key,"event")
    cards=event_review.get("event_research_cards")
    if not isinstance(cards,list) or len(cards)>120:
        raise ValueError("bounded event cards required")
    matched=[c for c in cards if isinstance(c,Mapping) and
             c.get("event_key")==event_key and
             c.get("niche_key")==twin.get("niche_key") and
             c.get("geography_key")==twin.get("geography_key")]
    if (len(matched)!=1
            or matched[0].get("territory_exact_research_match") is not True
            or matched[0].get("market_source_revision_sha256")
               != territory_link.get("market_source_revision_fingerprint")
            or territory_link.get("hypothetical_twin_pilot_design_sha256")
               != twin.get("original_pilot_design_sha256")
            or matched[0].get("driver_multiplier_inferred_from_news") is not False
            or matched[0].get("hypothetical_economic_twin_recalculated") is not False
            or matched[0].get("commercial_publication_or_outreach_approved") is not False):
        return {
            "schema_version":"empire.predictive_revenue.newsjack_twin_research_link.v1",
            "status":"NEWS_EVENT_TWIN_SOURCE_BINDING_HOLD",
            "mode":"OBSERVE",
            "research_link_verified":False,
            "news_event_is_paid_demand":False,
            "source_event_promotional_campaign_authorized":False,
            "hypothetical_economic_shock_automatically_applied":False,
            "next_action":"RESOLVE_SOURCE_REVISION_NICHE_TERRITORY_AND_PILOT_IDENTITY",
            "database_writes":False,"outbound_sent":False,
            "execution_authority":"none",
        }
    c=matched[0]
    return {
        "schema_version":"empire.predictive_revenue.newsjack_twin_research_link.v1",
        "status":"EVENT_TO_TWIN_RESEARCH_PROPOSAL_ONLY",
        "mode":"OBSERVE",
        "research_link_verified":True,
        "event_source_revision_sha256":c["event_source_revision_sha256"],
        "market_source_revision_sha256":c["market_source_revision_sha256"],
        "original_pilot_design_sha256":twin["original_pilot_design_sha256"],
        "suggested_existing_twin_driver":c["strategy_driver_hypothesis"],
        "news_safety_review_required":c["news_safety_review_required"],
        "proposed_existing_owner_playbook":c["proposed_playbook"],
        "explicit_hypothetical_impact_parameters_required":True,
        "original_event_truth_independently_verified":False,
        "geography_canonical_id_attested":False,
        "buying_intent_or_profit_verified":False,
        "scenario_uplift_calibrated":False,
        "news_event_is_paid_demand":False,
        "source_event_promotional_campaign_authorized":False,
        "hypothetical_economic_shock_automatically_applied":False,
        "next_action":"EXISTING_STRATEGY_AND_MARKET_TWIN_OWNERS_REVIEW_WHAT_IF_ASSUMPTIONS",
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }


NEWS_FEED_REL = "runtime/real_world_news/latest.json"
NEWS_FEED_SCHEMA = "empire.news_event_source_metadata.v1"
NEWS_FEED_FIELDS = frozenset((
    "schema_version","mode","execution_authority","generated_at",
    "source_owner","licensing_internal_research_allowed",
    "raw_article_bodies_included","publisher_provider_authentication_verified",
    "event_metadata",
))


def review_newsjack_source_readiness_runtime(
    repo_root: str, *, as_of:datetime,
) -> dict[str,Any]:
    """Optional owner feed is NOT live yet. Do not synthesize events on absence."""
    from pathlib import Path
    from empire_os.predictive_market_evidence_binding import (
        review_revenue_gps_territory_evidence_runtime,
    )
    root=Path(repo_root).resolve()
    path=root / NEWS_FEED_REL
    base={
        "schema_version":"empire.predictive_revenue.newsjack_source_readiness.v1",
        "mode":"OBSERVE","status":"LIVE_NEWS_SOURCE_NOT_CONNECTED",
        "news_source_event_record_count":None,"news_research_result":None,
        "event_evidence_authenticated":False,
        "original_news_service_live_verified":False,
        "licensed_collection_enabled_by_this_review":False,
        "marketing_publication_authorized":False,
        "outbound_sent":False,"database_writes":False,
        "execution_authority":"none",
    }
    try:
        if ((root/"runtime").is_symlink() or path.parent.is_symlink()
                or path.is_symlink() or not path.is_file()):
            return base
        if not 0<path.stat().st_size<=1_000_000:
            return dict(base,status="NEWS_SOURCE_FILE_SIZE_HOLD")
        source=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        return dict(base,status="NEWS_SOURCE_READ_HOLD")
    if (not isinstance(source,Mapping) or set(source)!=NEWS_FEED_FIELDS
            or source.get("schema_version")!=NEWS_FEED_SCHEMA
            or source.get("mode")!="OBSERVE"
            or source.get("execution_authority")!="none"
            or source.get("source_owner")!="existing_news_intelligence_source_owner"
            or source.get("licensing_internal_research_allowed") is not True
            or source.get("raw_article_bodies_included") is not False
            or source.get("publisher_provider_authentication_verified") is not False):
        return dict(base,status="NEWS_FEED_SOURCE_CONTRACT_HOLD")
    try:
        source_at=source_timestamp(source.get("generated_at"))
        age=as_of.astimezone(timezone.utc)-source_at
    except ValueError:
        return dict(base,status="NEWS_SOURCE_EPOCH_HOLD")
    if not timedelta(0)<=age<=timedelta(hours=6):
        return dict(base,status="NEWS_SOURCE_EPOCH_HOLD")
    market=review_revenue_gps_territory_evidence_runtime(root,as_of=as_of)
    if market.get("status")!="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY":
        return dict(base,status="NEWS_TERRITORY_SOURCE_HOLD")
    output=review_newsjack_event_research(source.get("event_metadata"),market,as_of=as_of)
    if output.get("status")!="NEWSJACK_RESEARCH_SIGNAL_TRIAGE_READY":
        return dict(base,status="NEWS_EVENT_METADATA_HOLD")
    return dict(base,status="NEWS_FEED_INTERNAL_RESEARCH_REVIEWED",
                news_source_event_record_count=output["source_article_count"],
                news_research_result=output,
                original_news_service_live_verified=False)


JEV_OWNER_SCHEMA = "empire.organic.newsjack_jev_review.v1"
JEV_STATUSES = frozenset((
    "HOLD_EVIDENCE","RESEARCH_REVIEW","NOT_RELEVANT","CONTENT_BRIEF_REVIEW",
))


def review_existing_jev_newsjack_handoff(
    owner_review: Mapping[str,Any], *, as_of:datetime,
) -> dict[str,Any]:
    """Adapt the EXISTING JEV/Newsjack owner result, without re-collecting news.

    JEV reports country market (GB/US) and sector (e.g. solar), not a verified
    canonical city/territory ID. Never silently map it to a GPS/twin corridor.
    No model confidence, search traffic or news standing becomes buyer intent.
    """
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware time required")
    base={
        "schema_version":"empire.predictive_revenue.jev_newsjack_owner_handoff.v1",
        "mode":"OBSERVE","status":"JEV_NEWSJACK_OWNER_PACKET_HOLD",
        "hold_code":"UNTRUSTED_OR_MISSING_OWNER_REVIEW",
        "newsjack_upstream_skills_invoked_by_this_bridge":False,
        "jev_owner_review_verified":False,
        "source_signal_count":None,
        "national_scope_research_cards":[],
        "territory_to_economic_twin_bound":False,
        "matched_quant_forecast_or_real_profit_available":False,
        "marketing_or_pr_execution_authorized":False,
        "newsjack_report_is_paid_buyer_intent":False,
        "outbound_sent":False,"database_writes":False,"execution_authority":"none",
    }
    if (not isinstance(owner_review,Mapping)
            or owner_review.get("schema_version")!=JEV_OWNER_SCHEMA
            or owner_review.get("mode")!="OBSERVE"
            or owner_review.get("execution_authority")!="none"
            or owner_review.get("publishing_enabled") is not False
            or owner_review.get("outbound_enabled") is not False
            or owner_review.get("payment_enabled") is not False
            or type(owner_review.get("newsjack_installed_or_invoked")) is not bool):
        return base
    candidates=owner_review.get("candidates")
    n=owner_review.get("candidate_count")
    if (not isinstance(candidates,list) or type(n) is not int
            or not 0<=n<=100 or len(candidates)!=n):
        return dict(base,hold_code="JEV_OWNER_CANDIDATE_COUNT_CONFLICT")
    seen=set()
    cards=[]
    try:
        for c in candidates:
            if not isinstance(c,Mapping):
                raise ValueError("typed JEV owner record required")
            sid=c.get("signal_id")
            if not isinstance(sid,str) or not 1<=len(sid)<=128 or sid in seen:
                raise ValueError("duplicate or missing source identity")
            seen.add(sid)
            state=c.get("status")
            if (state not in JEV_STATUSES
                    or c.get("execution_authority")!="none"
                    or c.get("publishing_enabled") is not False
                    or c.get("outbound_enabled") is not False
                    or c.get("paid_media_spend_enabled") is not False
                    or c.get("actual_revenue") is not False
                    or c.get("actual_visitors") is not None
                    or c.get("actual_enquiries") is not None):
                raise ValueError("JEV owner attempted to promote action or actual commerce")
            fingerprint=c.get("evidence_fingerprint")
            if not isinstance(fingerprint,str) or not SHA.fullmatch(fingerprint):
                raise ValueError("original source fingerprint missing")
            country,sector=c.get("market"),c.get("sector")
            if (country not in ("GB","US") or not isinstance(sector,str)
                    or not 2<=len(sector)<=45 or not sector.replace("_","").isalpha()):
                raise ValueError("national market scope or sector invalid")
            if state!="HOLD_EVIDENCE":
                source_day=c.get("publication_precision")
                if source_day=="instant":
                    at=source_timestamp(c.get("published_at"))
                    if not timedelta(0)<=as_of.astimezone(timezone.utc)-at<=MAX_AGE:
                        raise ValueError("stale or future article")
                elif source_day=="day":
                    from datetime import date
                    published_day=date.fromisoformat(c.get("publication_date"))
                    age_days=(as_of.astimezone(timezone.utc).date()-published_day).days
                    if not 0<=age_days<=3:
                        raise ValueError("stale or future day-precision article")
                else:
                    raise ValueError("source time required")
            decision=c.get("jev_shadow_decision")
            if decision is not None and (
                not isinstance(decision,Mapping)
                or decision.get("scope")!="classification_confidence_not_traffic_probability"
                or type(decision.get("confidence")) not in (int,float)
                or not 0<=decision["confidence"]<=1
            ):
                raise ValueError("untrusted JEV model confidence")
            cards.append({
                "source_signal_revision_sha256":fingerprint,
                "market_country_scope":country,
                "sector_research_scope":sector,
                "original_jev_status":state,
                "needs_evidence_review":state!="CONTENT_BRIEF_REVIEW",
                "original_jev_shadow_model_decision_available":decision is not None,
                "newsjack_source_evidence_is_verified_physical_event":False,
                "country_scope_proves_exact_service_territory":False,
                "source_signal_is_authenticated_demand":False,
                "source_signal_is_verified_incremental_revenue":False,
                "suitable_next_owner":"existing_jev_newsjack_editorial_and_market_intelligence_owner",
                "allowed_action":"RESEARCH_ONLY_NO_PUBLISH_OR_SEND",
            })
    except (ValueError,TypeError):
        return dict(base,hold_code="JEV_OWNER_SOURCE_EVIDENCE_HOLD")
    reported=owner_review.get("status_counts")
    counts={name:sum(c["original_jev_status"]==name for c in cards)
            for name in JEV_STATUSES}
    if not isinstance(reported,Mapping) or any(
        type(reported.get(k,0)) is not int or reported.get(k,0)!=counts[k]
        for k in JEV_STATUSES
    ) or set(reported)!=set(k for k,v in counts.items() if v):
        return dict(base,hold_code="JEV_OWNER_STATUS_COUNTS_CONFLICT")
    return dict(
        base,status="JEV_NEWSJACK_SOURCE_RESEARCH_REVIEWED",hold_code=None,
        jev_owner_review_verified=True,
        source_signal_count=n,
        national_scope_research_cards=cards,
        source_material_national_not_territory_precision=True,
        original_owner_code_authority_not_transferred=True,
    )
