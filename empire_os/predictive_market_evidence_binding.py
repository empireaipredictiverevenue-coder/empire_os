"""Territory-specific provenance bridge for Revenue GPS -> Predictive Market Twin.

This uses the EXISTING Market Sweep / Revenue GPS read-only aggregate;
market research counts are not demand, sale probabilities, prices, service
capacity, market share or accounting truth. It does not query the database,
crawl, send messages, price offers, or start a new agent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time

SCHEMA = "empire.predictive_revenue.market_territory_evidence.v1"
SOURCE_SCHEMA = "empire.market_sweep_revenue_gps.v1"
TWIN_SCHEMA = "empire.predictive_revenue.market_economic_twin.v1"
MAX_BYTES = 3_000_000
MAX_AGE = timedelta(hours=8)
SLUG = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
METRO = re.compile(r"^[a-z][a-z0-9]*(?:[ .,/-]+[a-z0-9]+)*$",re.ASCII)
COUNTS = (
    "prospect_count", "canonical_company_count", "scored_prospect_count",
    "acquisition_count", "qualification_count", "approved_buyer_count",
    "delivered_outreach_count", "commercial_reply_count",
    "commercial_terms_count", "verified_payment_count",
    "recognized_revenue_event_count", "competitive_entity_count",
    "competitive_signal_count", "competitive_evidence_coverage_gap_count",
    "commercial_demand_evidence_count", "unverified_reply_record_count",
    "unverified_positive_classification_count",
)


def _slug_location(metro: Any) -> str:
    if (not isinstance(metro,str) or len(metro)>75
            or not METRO.fullmatch(metro.strip().lower())):
        raise ValueError("bounded metro text, not a personal address, required")
    return re.sub(r"[^a-z0-9]+","_",metro.strip().lower()).strip("_")


def _held(reason: str) -> dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"TERRITORY_RESEARCH_EVIDENCE_HOLD","hold_code":reason,
        "source_generated_at":None,"source_revision_fingerprint":None,
        "market_count":None,"reported_commercial_demand_market_count":None,
        "reported_competitor_research_market_count":None,
        "territory_research_cards":[],
        "market_research_is_verified_buying_demand":False,
        "product_unit_price_authenticated":False,
        "actual_delivery_capacity_verified":False,
        "live_economic_forecast_issuance_authorized":False,
        "original_forecast_registered":False,
        "revenue_recognized_by_this_bridge":False,
        "data_mutation":False,"outbound_sent":False,
        "execution_authority":"none",
    }


def _nonnegative(row: Mapping[str,Any], name: str, *, max_value:int=1_000_000) -> int:
    value = row.get(name)
    if type(value) is not int or not 0<=value<=max_value:
        raise ValueError("invalid bounded source counter")
    return value


def review_revenue_gps_territory_evidence(
    snapshot: Mapping[str,Any], *,as_of:datetime,
) -> dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware trusted review clock required")
    if not isinstance(snapshot,Mapping):
        return _held("MARKET_SOURCE_REQUIRED")
    if (snapshot.get("schema_version")!=SOURCE_SCHEMA
            or snapshot.get("mode")!="OBSERVE"
            or snapshot.get("execution_authority")!="none"
            or snapshot.get("outreach_enabled") is not False
            or snapshot.get("buyer_intent_inferred") is not False
            or snapshot.get("commercial_intent_inferred") is not False
            or snapshot.get("revenue_inferred") is not False
            or snapshot.get("market_share_inferred") is not False
            or snapshot.get("restricted_source_scope")!="RESTRICTED_AGGREGATES_ONLY"):
        return _held("UNTRUSTED_SOURCE_RIGHTS_OR_AUTHORITY")
    if (type(snapshot.get("unverified_positive_classifications_present")) is not int
            or snapshot.get("unverified_positive_classifications_present")!=0
            or type(snapshot.get("unverified_reply_records_present")) is not int
            or snapshot.get("unverified_reply_records_present")!=0):
        return _held("UNVERIFIED_REPLIES_CANNOT_BE_MARKET_DEMAND")
    try:
        at = _time(snapshot.get("generated_at"))
    except ValueError:
        return _held("INVALID_SOURCE_EPOCH")
    age=as_of.astimezone(timezone.utc)-at
    if not timedelta(0)<=age<=MAX_AGE:
        return _held("STALE_OR_FUTURE_SOURCE_EPOCH")
    rows=snapshot.get("markets")
    if (not isinstance(rows,list) or not 0<len(rows)<=200
            or _is_invalid_size(snapshot,rows)):
        return _held("MISSING_OR_CONTRADICTORY_MARKET_COUNT")
    if (type(snapshot.get("window_days")) is not int
            or not 1<=snapshot["window_days"]<=31):
        return _held("INVALID_SOURCE_OBSERVATION_WINDOW")
    macro = snapshot.get("verified_product_economics")
    if not isinstance(macro,Mapping):
        return _held("SCENARIO_MISTAKEN_FOR_REAL_COST_OR_PRICE")
    if macro.get("available") is False:
        # The existing producer emits an absence-of-catalogue sentinel,
        # not a policy scenario, if no verified catalog row is present.
        scenario_safe = (macro.get("prediction") is False
                         and macro.get("actual_revenue") is False
                         and macro.get("actual_cost_observed") is not True
                         and macro.get("economics_kind") is None)
    else:
        scenario_safe = (macro.get("economics_kind")=="founder_policy_scenario"
                         and macro.get("prediction") is False
                         and macro.get("actual_cost_observed") is False
                         and macro.get("actual_revenue") is False)
    if not scenario_safe:
        return _held("SCENARIO_MISTAKEN_FOR_REAL_COST_OR_PRICE")

    seen=set()
    cards=[]
    commercial_markets=0
    competitive_markets=0
    try:
        for row in rows:
            if not isinstance(row,Mapping):
                raise ValueError("row must be structured")
            niche=row.get("niche")
            if not isinstance(niche,str) or not SLUG.fullmatch(niche):
                raise ValueError("bounded source niche required")
            geographic_key=_slug_location(row.get("metro"))
            identity=(niche,geographic_key)
            if identity in seen:
                raise ValueError("duplicate or ambiguous territory/niche")
            seen.add(identity)
            counts={key:_nonnegative(row,key) for key in COUNTS}
            # These are counts by a producer, not independently authenticated
            # unique buyers, purchases or settlement events.
            reply=counts["commercial_reply_count"]
            terms=counts["commercial_terms_count"]
            payment=counts["verified_payment_count"]
            combined=reply+terms+payment
            evidence=counts["commercial_demand_evidence_count"]
            if evidence!=combined or row.get("commercial_demand_state")!=(
                "observed" if evidence>0 else "not_observed"
            ):
                raise ValueError("commercial demand aggregate disagrees with constituent source counts")
            pressure=row.get("competitor_pressure_proxy")
            if pressure is None:
                if (row.get("competitor_pressure_is_model") is not False
                        or row.get("competitor_pressure_basis")!="unavailable"):
                    raise ValueError("unsupported competitor proxy")
            elif (type(pressure) not in (int,float)
                    or not 0<=pressure<=100
                    or row.get("competitor_pressure_is_model") is not True
                    or row.get("competitor_pressure_basis")!="competitive_signal_density"):
                raise ValueError("competitor proxy is not a probability or measured share")
            if (counts["competitive_evidence_coverage_gap_count"]!=max(
                    0,counts["canonical_company_count"]-counts["competitive_entity_count"])
                    or row.get("supply_gap_state")!="unknown_not_measured"
                    or row.get("supply_gap_inferred") is not False
                    or row.get("product_purchase_inferred") is not False
                    or row.get("buyer_intent_inferred") is not False
                    or row.get("commercial_intent_inferred") is not False
                    or row.get("market_share_inferred") is not False
                    or row.get("revenue_inferred") is not False
                    or row.get("outreach_enabled") is not False
                    or row.get("execution_authority")!="none"
                    or row.get("market_revenue_prediction_cents") is not None):
                raise ValueError("source row misclaims unknown buyer or supply evidence")
            if (type(row.get("recognized_revenue_cents")) is not int
                    or row["recognized_revenue_cents"]<0
                    or type(row.get("realized_margin_cents")) is not int
                    or abs(row["realized_margin_cents"])>10**13):
                raise ValueError("untrusted source money aggregates")
            if counts["recognized_revenue_event_count"]==0 and (
                row["recognized_revenue_cents"]!=0 or row["realized_margin_cents"]!=0
            ):
                raise ValueError("money cannot be attributed to absent revenue-event row")
            if (row.get("economics_scenario") is not None and (
                    not isinstance(row["economics_scenario"],Mapping)
                    or row["economics_scenario"].get("economics_kind")!="founder_policy_scenario"
                    or row["economics_scenario"].get("actual_revenue") is not False
                    or row["economics_scenario"].get("actual_cost_observed") is not False)):
                raise ValueError("unverified price scenario cannot become actual margin")
            if type(row.get("research_priority_score")) not in (int,float):
                raise ValueError("invalid source research score")
            score=row["research_priority_score"]
            if not 0<=score<=100:
                raise ValueError("research priority score outside source bounds")
            if type(row.get("research_candidate")) is not bool:
                raise ValueError("missing research eligibility flag")
            if (counts["unverified_reply_record_count"]>0
                    or counts["unverified_positive_classification_count"]>0):
                # For this path, unverified reply classifications are a source
                # HOLD, never purchase evidence or a reason to contact.
                raise ValueError("source has unverified positive/reply classifications")
            if pressure is not None:
                competitive_markets+=1
            if evidence>0:
                commercial_markets+=1
            blockers=[]
            if combined==0:
                blockers.append("NO_OBSERVED_COMMERCIAL_REPLY_TERMS_OR_PAYMENT_EVIDENCE")
            if payment==0:
                blockers.append("NO_REPORTED_VERIFIED_PAID_EVENT_IN_TERRITORY_SNAPSHOT")
            if counts["approved_buyer_count"]==0:
                blockers.append("NO_APPROVED_BUYER_CANDIDATE_IN_TERRITORY_SNAPSHOT")
            if counts["canonical_company_count"]==0:
                blockers.append("NO_CANONICAL_COMPANY_IDENTITY_IN_AGGREGATE_MARKET")
            if not counts["competitive_signal_count"]:
                blockers.append("NO_COMPETITIVE_SIGNALS_IN_TERRITORY_SNAPSHOT")
            blockers.extend((
                "NO_VERIFIED_CAPACITY_PRICE_CAC_MATERIALS_OR_SERVICE_DELIVERY_COST",
                "NO_PROSPECTIVELY_REGISTERED_QUANT_PREDICTION_OR_CALIBRATED_OUTCOME",
            ))
            original = [
                at.isoformat(),niche,geographic_key,counts,
                round(float(score),4),pressure,
                row["recognized_revenue_cents"],row["realized_margin_cents"],
            ]
            fingerprint=sha256(json.dumps(original,sort_keys=True,
                                           separators=(",",":"),allow_nan=False).encode()).hexdigest()
            cards.append({
                "market_niche_key":niche,"market_geography_key":geographic_key,
                "source_revision_fingerprint":fingerprint,
                "source_snapshot_epoch":at.isoformat(),
                "source_window_days":snapshot["window_days"],
                "research_priority_score_not_conversion_probability":score,
                "source_research_candidate":row["research_candidate"],
                "canonical_company_research_count":counts["canonical_company_count"],
                "prospect_acquisition_research_count":counts["acquisition_count"],
                "qualified_prospect_research_count":counts["qualification_count"],
                "approved_buyer_candidate_research_count":counts["approved_buyer_count"],
                "source_reported_commercial_replies_not_authenticated":reply,
                "source_reported_commercial_terms_not_accepted":terms,
                "source_reported_payment_event_count_not_independently_authenticated":payment,
                "source_reported_recognized_revenue_event_count_not_attributed":counts["recognized_revenue_event_count"],
                "competitive_signal_research_count":counts["competitive_signal_count"],
                "competitive_proxy_is_market_share":False,
                "commercial_observations_are_unique_purchasers":False,
                "can_infer_direct_demand_from_prospects":False,
                "customer_accepted_price_authenticated":False,
                "service_capacity_authenticated":False,
                "independent_purchase_evidence_connected":False,
                "research_owner_action":"VERIFY_ORIGINAL_BUYER_TERMS_PRICE_AND_TERRITORY_CAPACITY"
                    if combined>0 else "FIND_ORIGINAL_DIRECT_PURCHASER_DEMAND_AND_BUYBOX",
                "missing_proof":blockers,
                "execution_authority":"none",
            })
    except (ValueError, TypeError, KeyError):
        return _held("INVALID_OR_CONFLICTING_TERRITORY_SOURCE_ROWS")
    if (commercial_markets!=snapshot.get("commercial_demand_market_count")
            or competitive_markets!=snapshot.get("competitive_evidence_market_count")):
        return _held("GLOBAL_AND_TERRITORY_EVIDENCE_COUNTS_DRIFTED")
    # The producer also publishes its first 20 research handoffs. Verify none
    # requests execution or names an unreviewed/ambiguous territory identity.
    # This does NOT enqueue them in the Decision Control execution bus.
    queue=snapshot.get("research_queue")
    if not isinstance(queue,list) or len(queue)!=min(len(rows),20):
        return _held("MARKET_RESEARCH_HANDOFF_COUNT_DRIFTED")
    queue_seen=set()
    card_by_identity={
        (card["market_niche_key"],card["market_geography_key"]):card
        for card in cards
    }
    for task in queue:
        if not isinstance(task,Mapping):
            return _held("UNTRUSTED_MARKET_RESEARCH_HANDOFF")
        try:
            identity=(task.get("niche"),_slug_location(task.get("metro")))
        except ValueError:
            return _held("UNTRUSTED_MARKET_RESEARCH_HANDOFF")
        if (identity not in seen or identity in queue_seen
                or task.get("external_execution_authorized") is not False
                or task.get("mutation_authorized") is not False
                or task.get("recommended_next_action") != (
                    "advance_existing_approved_buyer"
                    if card_by_identity[identity]["approved_buyer_candidate_research_count"]>0
                    else "deepen_market_research"
                ) or type(task.get("research_priority_score")) not in (int,float)
                or task["research_priority_score"] != card_by_identity[identity]["research_priority_score_not_conversion_probability"]
                or not isinstance(task.get("evidence_refs"),list)
                or len(task["evidence_refs"])>20
                or any(not isinstance(ref,str) or len(ref)>110
                       or not ref.startswith("canonical:") for ref in task["evidence_refs"])):
            return _held("UNTRUSTED_MARKET_RESEARCH_HANDOFF")
        queue_seen.add(identity)
    cards.sort(key=lambda c:(
        -c["source_reported_commercial_replies_not_authenticated"]
        -c["source_reported_commercial_terms_not_accepted"]
        -c["source_reported_payment_event_count_not_independently_authenticated"],
        -c["research_priority_score_not_conversion_probability"],
        c["market_niche_key"],c["market_geography_key"],
    ))
    revision=sha256(json.dumps([at.isoformat(),
        [c["source_revision_fingerprint"] for c in cards]],sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        **_held("NONE"),
        "status":"TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY",
        "hold_code":None,
        "source_generated_at":at.isoformat(),
        "source_revision_fingerprint":revision,
        "market_count":len(cards),
        "reported_commercial_demand_market_count":commercial_markets,
        "reported_competitor_research_market_count":competitive_markets,
        "territory_research_cards":cards,
        "scope_is_not_a_signed_source_or_geo_identity":True,
        "source_counter_sums_may_not_represent_unique_entities":True,
        "no_automatic_hypothetical_demand_or_paid_capacity_generated":True,
    }


def _is_invalid_size(snapshot:Mapping[str,Any],rows:list[Any])->bool:
    n=snapshot.get("market_count")
    return type(n) is not int or n!=len(rows)


def bind_territory_research_to_market_twin(
    registry:Mapping[str,Any],twin:Mapping[str,Any],
) -> dict[str,Any]:
    """Exact niche+metro-text match; does NOT attest geography, buyer or money."""
    if (not isinstance(registry,Mapping)
            or registry.get("schema_version")!=SCHEMA
            or registry.get("status")!="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
            or registry.get("execution_authority")!="none"
            or not isinstance(twin,Mapping)
            or twin.get("schema_version")!=TWIN_SCHEMA
            or twin.get("status")!="HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
            or twin.get("execution_authority")!="none"
            or twin.get("source_market_conditions_authenticated") is not False
            or twin.get("original_forecast_registered") is not False
            or twin.get("market_shock_applied_to_production") is not False):
        raise ValueError("only safe market evidence and hypothetical twin")
    matched=[
        card for card in registry.get("territory_research_cards",())
        if isinstance(card,Mapping)
        and card.get("market_niche_key")==twin.get("niche_key")
        and card.get("market_geography_key")==twin.get("geography_key")
    ]
    if len(matched)!=1:
        return {
            "schema_version":"empire.predictive_revenue.territory_twin_research_link.v1",
            "mode":"OBSERVE",
            "status":"TWIN_TERRITORY_SOURCE_NOT_EXACTLY_MATCHED",
            "research_territory_binding_present":False,
            "market_source_revision_fingerprint":None,
            "territory_data_is_paid_demand_or_capacity":False,
            "source_market_metro_text_proves_jurisdiction":False,
            "economic_scenario_authentic":False,
            "next_action":"RESOLVE_CANONICAL_MARKET_GEO_ID_AND_SOURCE_REVISION_WITH_OWNER",
            "database_writes":False,"outbound_sent":False,"execution_authority":"none",
        }
    row=matched[0]
    return {
        "schema_version":"empire.predictive_revenue.territory_twin_research_link.v1",
        "mode":"OBSERVE",
        "status":"EXACT_TEXT_TERRITORY_RESEARCH_LINK_ONLY",
        "research_territory_binding_present":True,
        "market_source_revision_fingerprint":row["source_revision_fingerprint"],
        "market_source_epoch":row["source_snapshot_epoch"],
        "hypothetical_twin_pilot_design_sha256":twin.get("original_pilot_design_sha256"),
        "source_research_priority_not_buyer_probability":row["research_priority_score_not_conversion_probability"],
        "market_source_reported_commercial_replies_not_authenticated":row["source_reported_commercial_replies_not_authenticated"],
        "missing_commercial_evidence":list(row["missing_proof"]),
        "territory_data_is_paid_demand_or_capacity":False,
        "source_market_metro_text_proves_jurisdiction":False,
        "hypothetical_twin_price_is_accepted_customer_price":False,
        "economic_scenario_authentic":False,
        "next_action":"VERIFY_REAL_CAPACITY_ACCEPTED_PRICE_AND_PROSPECTIVE_FORECAST_BEFORE_LIVE_USE",
        "database_writes":False,"outbound_sent":False,"execution_authority":"none",
    }


def review_revenue_gps_territory_evidence_runtime(
    repo_root:str | Path,*,as_of:datetime,
)->dict[str,Any]:
    root=Path(repo_root).resolve()
    p=root/"runtime/market_sweeps/revenue_gps_latest.json"
    try:
        if ((root/"runtime").is_symlink()
                or p.parent.is_symlink() or p.is_symlink()
                or not p.is_file() or not 0<p.stat().st_size<=MAX_BYTES):
            return _held("SOURCE_SNAPSHOT_UNAVAILABLE")
        snapshot=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError):
        return _held("SOURCE_SNAPSHOT_UNREADABLE")
    return review_revenue_gps_territory_evidence(snapshot,as_of=as_of)
