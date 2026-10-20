"""BLS official cost-index research adapter for Predictive Revenue.

Consumes *existing owner-supplied*, bounded BLS API response metadata. No
network access, secret registration key, scheduling, production twin mutation,
forecast calibration or fake job-level costs. PPI measures producer OUTPUT
price changes, not an individual operator's labour/material invoice.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time

SCHEMA = "empire.predictive_revenue.bls_index_research.v1"
OWNER_SCHEMA = "empire.economic_sources.bls_owner_review.v1"
SOURCE_API = ("https://api.bls.gov/publicAPI/v1/timeseries/data/",
              "https://api.bls.gov/publicAPI/v2/timeseries/data/")
SERIES_ID = re.compile(r"^[A-Z0-9_#-]{6,60}$")
METRICS = frozenset(("producer_output_price_index","wage_related_index"))
MAX_SOURCE_AGE = timedelta(hours=72)
MAX_PERIOD_AGE = timedelta(days=150)
COUNT_LIMIT = 12


def _unknown(status: str) -> dict[str,Any]:
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","status":status,
        "series_observation_count":None,"series_research_cards":[],
        "owner_source_generated_at":None,"source_revision_sha256":None,
        "original_source_publisher_authenticated_independently":False,
        "series_canonical_definition_independently_verified":False,
        "index_is_a_specific_supplier_invoice":False,
        "national_index_is_exact_territory_price":False,
        "index_is_employer_hourly_payroll":False,
        "forecast_error_calibrated":False,
        "actual_material_or_labor_cost_authenticated":False,
        "realized_profit_verified":False,"source_owner_writes":False,
        "external_fetch_or_paid_query_performed":False,
        "database_writes":False,"outbound_sent":False,"execution_authority":"none",
    }


def _index(value:Any)->Decimal:
    if not isinstance(value,str) or not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,6})?",value):
        raise ValueError("numeric BLS published index required")
    x=Decimal(value)
    if not x.is_finite() or not Decimal("0")<x<=Decimal("10000000"):
        raise ValueError("bounded positive BLS index required")
    return x


def _month(row:Mapping[str,Any],now:datetime)->tuple[int,int,str]:
    y=row.get("year");p=row.get("period")
    if (not isinstance(y,str) or not re.fullmatch(r"(?:19|20)\d{2}",y)
            or not isinstance(p,str) or not re.fullmatch(r"M(?:0[1-9]|1[0-2])",p)):
        raise ValueError("BLS monthly period invalid or annual average")
    year=int(y);month=int(p[1:])
    if (year,month)>(now.year,now.month):
        raise ValueError("future BLS observation month")
    return year,month,f"{year:04}-{month:02}"


def review_bls_cost_index_owner(
    owner:Mapping[str,Any]|None, *, as_of:datetime,
)->dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware market source review clock required")
    if owner is None:
        return _unknown("BLS_OWNER_SOURCE_NOT_CONNECTED")
    if (not isinstance(owner,Mapping)
            or owner.get("schema_version")!=OWNER_SCHEMA
            or owner.get("mode")!="OBSERVE"
            or owner.get("execution_authority")!="none"
            or owner.get("source_publisher")!="U.S. Bureau of Labor Statistics"
            or owner.get("official_api_endpoint") not in SOURCE_API
            or owner.get("data_rights_scope")!="INTERNAL_ECONOMIC_RESEARCH"
            or owner.get("raw_job_supplier_quotes_included") is not False
            or owner.get("raw_personal_wage_records_included") is not False
            or owner.get("consumer_outreach_authorized") is not False
            or owner.get("price_quote_or_sale_verified") is not False):
        return _unknown("BLS_OWNER_SOURCE_CONTRACT_HOLD")
    try:
        now=as_of.astimezone(timezone.utc)
        source_time=_time(owner.get("generated_at"))
    except ValueError:
        return _unknown("BLS_SOURCE_EPOCH_INVALID")
    if not timedelta(0)<=now-source_time<=MAX_SOURCE_AGE:
        return _unknown("BLS_SOURCE_STALE_OR_FUTURE_HOLD")
    raw=owner.get("bls_api_response")
    manifests=owner.get("approved_series_manifest")
    if (not isinstance(raw,Mapping)
            or raw.get("status")!="REQUEST_SUCCEEDED"
            or raw.get("message") != []
            or not isinstance(raw.get("Results"),Mapping)
            or not isinstance(manifests,list)
            or not 1<=len(manifests)<=COUNT_LIMIT):
        return _unknown("BLS_API_OR_MANIFEST_HOLD")
    published=raw["Results"].get("series")
    if not isinstance(published,list) or len(published)!=len(manifests):
        return _unknown("BLS_API_SERIES_COVERAGE_HOLD")
    manifest_by_id={}
    try:
        for m in manifests:
            if (not isinstance(m,Mapping)
                    or set(m)!={"series_id","economic_role","source_country",
                                "geographic_scope","frequency","unit",
                                "seasonal_adjustment","owner_category_reviewed"}
                    or not isinstance(m.get("series_id"),str)
                    or not SERIES_ID.fullmatch(m["series_id"])
                    or m["series_id"] in manifest_by_id
                    or m.get("economic_role") not in METRICS
                    or m.get("source_country")!="US"
                    or m.get("geographic_scope")!="national_or_series_defined"
                    or m.get("frequency")!="monthly"
                    or m.get("unit")!="index_not_currency"
                    or m.get("seasonal_adjustment") not in ("seasonally_adjusted","not_seasonally_adjusted")
                    or m.get("owner_category_reviewed") is not True):
                raise ValueError("source owner review metadata incomplete")
            manifest_by_id[m["series_id"]]=m
        seen=set()
        cards=[]
        for s in published:
            if not isinstance(s,Mapping) or not isinstance(s.get("seriesID"),str):
                raise ValueError("invalid BLS result series")
            sid=s["seriesID"]
            if sid in seen or sid not in manifest_by_id:
                raise ValueError("unknown or duplicate published series")
            seen.add(sid)
            rows=s.get("data")
            if not isinstance(rows,list) or not 2<=len(rows)<=150:
                raise ValueError("too few or too many original observations")
            periods={}
            prelim=False
            for item in rows:
                if not isinstance(item,Mapping):
                    raise ValueError("invalid BLS period")
                y,m,p=_month(item,now)
                point=(y,m)
                if point in periods:
                    raise ValueError("duplicate BLS month")
                periods[point]=_index(item.get("value"))
                foot=item.get("footnotes",[])
                if not isinstance(foot,list) or len(foot)>10:
                    raise ValueError("invalid source revision footnotes")
                for f in foot:
                    if (not isinstance(f,Mapping)
                            or not isinstance(f.get("code"),str)
                            or len(f["code"])>10):
                        raise ValueError("bad BLS source footnotes")
                    if f.get("code")=="P":
                        prelim=True
            latest=max(periods)
            if (now-datetime(latest[0],latest[1],1,tzinfo=timezone.utc))>MAX_PERIOD_AGE:
                raise ValueError("BLS latest data period too old")
            previous=(latest[0]-1,latest[1])
            yoy=None
            if previous in periods:
                yoy=round(float((periods[latest]/periods[previous]-1)*100),4)
            # A one-month rise is not a year-over-year input-price shock.
            cards.append({
                "original_public_series_id":sid,
                "owner_reported_series_role":manifest_by_id[sid]["economic_role"],
                "source_geographic_scope":"national_or_series_defined",
                "latest_observed_month":f"{latest[0]:04}-{latest[1]:02}",
                "latest_published_index_value_not_currency":str(periods[latest]),
                "same_month_prior_year_index_value_not_currency":str(periods[previous]) if previous in periods else None,
                "year_over_year_index_change_pct_research_only":yoy,
                "original_periods_examined":len(rows),
                "any_source_preliminary_footnotes":prelim,
                "source_original_period_missing_yoy":previous not in periods,
                "index_movement_is_verified_actual_supplier_cost_change":False,
                "index_movement_is_verified_local_wage_change":False,
                "index_movement_is_accepted_customer_price":False,
                "owner_category_is_independently_audited":False,
                "proposed_existing_twin_driver":"material_cost"
                    if manifest_by_id[sid]["economic_role"]=="producer_output_price_index"
                    else None,
                "scenario_value_applied_automatically":False,
            })
        if seen!=set(manifest_by_id):
            raise ValueError("missing original manifest coverage")
    except (ValueError,TypeError,InvalidOperation,OverflowError):
        return _unknown("BLS_SOURCE_VALUE_OR_PERIOD_HOLD")
    # Public original payload fingerprints indicate content revision, not a
    # signed BLS source attestation. No registration key is accepted/stored.
    try:
        revision=sha256(json.dumps(
            {"series":published,"manifest":manifests},
            sort_keys=True,separators=(",",":"),allow_nan=False,
        ).encode()).hexdigest()
    except (ValueError,TypeError):
        return _unknown("BLS_SOURCE_PAYLOAD_HOLD")
    return {
        **_unknown("BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"),
        "series_observation_count":len(cards),
        "series_research_cards":sorted(cards,key=lambda c:c["original_public_series_id"]),
        "owner_source_generated_at":source_time.isoformat(),
        "source_revision_sha256":revision,
        "source_api_version":"v2" if "/v2/" in owner["official_api_endpoint"] else "v1",
        "yoy_change_is_not_price_quote":True,
        "economic_twin_material_and_labor_scenario_design_ready":True,
        "actual_supplier_cost_multiplier_authorized":False,
        "next_owner":"existing_economic_source_materials_finance_and_predictive_twin_owners",
        "next_action":"REVIEW_SERIES_MEANING_COST_SHARE_AND_ORIGINAL_INVOICE_BASELINE",
    }


def propose_bls_hypothetical_material_cost_stress(
    review:Mapping[str,Any],*,series_id:str,
    assumed_cost_exposure_share:float,
    assumed_price_change_pass_through_fraction:float,
)->dict[str,Any]:
    """Optional what-if design only; does not run or alter the existing twin."""
    if (not isinstance(review,Mapping)
            or review.get("schema_version")!=SCHEMA
            or review.get("status")!="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
            or review.get("execution_authority")!="none"
            or not isinstance(series_id,str)):
        raise ValueError("trusted reviewed BLS research required")
    shares=(assumed_cost_exposure_share,assumed_price_change_pass_through_fraction)
    if any(type(x) not in (int,float) or not 0<=x<=1 for x in shares):
        raise ValueError("bounded hypothetical input assumptions required")
    rows=[r for r in review["series_research_cards"]
          if r.get("original_public_series_id")==series_id]
    if len(rows)!=1 or rows[0]["owner_reported_series_role"]!="producer_output_price_index":
        raise ValueError("material output index only; wages do not prove capacity")
    row=rows[0]
    pct=row["year_over_year_index_change_pct_research_only"]
    if type(pct) not in (int,float):
        raise ValueError("no same-period year-on-year comparison")
    effective=1+(pct/100)*assumed_cost_exposure_share*assumed_price_change_pass_through_fraction
    if not 0.5<=effective<=1.5:
        raise ValueError("bounded stress multiplier outside allowed scenario range")
    return {
        "schema_version":"empire.predictive_revenue.bls_material_cost_what_if.v1",
        "mode":"OBSERVE","status":"HYPOTHETICAL_COST_STRESS_PROPOSAL_ONLY",
        "source_revision_sha256":review["source_revision_sha256"],
        "source_public_series_id":series_id,
        "latest_source_month":row["latest_observed_month"],
        "input_index_yoy_change_pct":pct,
        "assumed_cost_exposure_share":assumed_cost_exposure_share,
        "assumed_price_change_pass_through_fraction":assumed_price_change_pass_through_fraction,
        "hypothetical_fulfilment_cost_multiplier":round(effective,6),
        "existing_twin_driver_type":"material_cost",
        "original_company_cost_baseline_authenticated":False,
        "original_local_material_price_verified":False,
        "causal_pass_through_calibrated":False,
        "economic_twin_recalculated":False,
        "cost_shock_applied_to_production":False,
        "scenario_revenue_or_profit_authenticated":False,
        "model_training_authorized":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }


def bind_bls_cost_stress_to_existing_twin(
    review:Mapping[str,Any],
    stress:Mapping[str,Any],
    twin:Mapping[str,Any],
)->dict[str,Any]:
    """Attach a *hypothesis* to the original hypothetical twin, not its executor.

    BLS national figures cannot supply a verified local price, quote, capacity
    or causal cost shock; matching an SHA or scenario value is not proof.
    """
    from empire_os.predictive_market_economic_twin import SCHEMA as TWIN_SCHEMA
    if (not isinstance(review,Mapping)
            or review.get("schema_version")!=SCHEMA
            or review.get("status")!="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
            or review.get("execution_authority")!="none"
            or review.get("actual_material_or_labor_cost_authenticated") is not False
            or review.get("source_revision_sha256") is None):
        raise ValueError("source-reviewed cost index packet required")
    if (not isinstance(stress,Mapping)
            or stress.get("schema_version")!="empire.predictive_revenue.bls_material_cost_what_if.v1"
            or stress.get("status")!="HYPOTHETICAL_COST_STRESS_PROPOSAL_ONLY"
            or stress.get("source_revision_sha256")!=review["source_revision_sha256"]
            or stress.get("existing_twin_driver_type")!="material_cost"
            or stress.get("economic_twin_recalculated") is not False
            or stress.get("scenario_revenue_or_profit_authenticated") is not False
            or stress.get("cost_shock_applied_to_production") is not False
            or stress.get("execution_authority")!="none"):
        raise ValueError("untrusted hypothetical material stress proposal")
    if (not isinstance(twin,Mapping)
            or twin.get("schema_version")!=TWIN_SCHEMA
            or twin.get("status")!="HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED"
            or twin.get("execution_authority")!="none"
            or twin.get("source_market_conditions_authenticated") is not False
            or twin.get("original_forecast_registered") is not False
            or twin.get("market_shock_applied_to_production") is not False
            or twin.get("pricing_and_purchasing_terms_verified") is not False):
        raise ValueError("existing hypothetical twin original owner required")
    # Recompute the what-if from reviewed series, rather than trusting a
    # caller's arbitrary multiplier in a manually edited source packet.
    original=propose_bls_hypothetical_material_cost_stress(
        review,series_id=stress.get("source_public_series_id"),
        assumed_cost_exposure_share=stress.get("assumed_cost_exposure_share"),
        assumed_price_change_pass_through_fraction=stress.get(
            "assumed_price_change_pass_through_fraction"),
    )
    if original!=dict(stress):
        raise ValueError("BLS hypothetical cost stress content drift")
    return {
        "schema_version":"empire.predictive_revenue.bls_twin_cost_stress_link.v1",
        "mode":"OBSERVE","status":"BLS_TO_MARKET_TWIN_RESEARCH_LINK_ONLY",
        "original_bls_source_revision_sha256":review["source_revision_sha256"],
        "original_twin_pilot_design_sha256":twin["original_pilot_design_sha256"],
        "original_market_key":twin["market_key"],
        "economic_scenario_niche_key":twin["niche_key"],
        "economic_scenario_geography_key":twin["geography_key"],
        "bls_national_series_is_exact_market_geography":False,
        "hypothetical_fulfilment_cost_multiplier":original[
            "hypothetical_fulfilment_cost_multiplier"],
        "assumed_cost_share_unverified":original["assumed_cost_exposure_share"],
        "assumed_pass_through_fraction_unverified":original[
            "assumed_price_change_pass_through_fraction"],
        "existing_economic_twin_driver_type":"material_cost",
        "original_customer_unit_cost_verified":False,
        "scenario_expected_profit_delta_computed_by_this_link":None,
        "forecast_issued_or_registered":False,
        "source_cost_stress_executed":False,
        "next_action":"EXISTING_MATERIALS_FINANCE_AND_TWIN_OWNERS_REVIEW_ASSUMPTION",
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
