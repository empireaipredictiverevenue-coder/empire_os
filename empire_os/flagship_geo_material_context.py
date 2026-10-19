"""Geography, materials and hazard knowledge for the flagship market brain.

Pure, bounded, canonical-source-attributed knowledge-graph extension.
Location anchors come from EXISTING Empire geo_registry; official external
datasets are DISCOVERY REFERENCES until an original admissible observation
is supplied. Material questions are an engineering ontology, NOT knowledge
that any property has a particular roof, risk, damage or repair contract.

No networking, polygons, geo-joins, personal records, inferred county FIPS,
hazard predictions, model weights or commercially executable opportunities.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
from dataclasses import dataclass
import json
import re

from empire_os.geo_registry import acquisition_markets
from empire_os.flagship_market_knowledge_graph import SCHEMA as MARKET_SCHEMA

SCHEMA="empire.flagship.geo_material_knowledge.v1"
MAX_OBSERVATIONS=100
MAX_SOURCE_LATENCY_DAYS=3650
US_FIPS=re.compile(r"^[0-9]{5}$")
GB_GSS=re.compile(r"^[ENSW][0-9]{8}$")
SHA=re.compile(r"^[0-9a-f]{64}$")
SAFE_EVENT=re.compile(r"^[a-z][a-z0-9_]{1,39}$")

# Source catalogue: capabilities and identifiers, NOT actual ingested values.
# Exact website references, attribution and licensing require source review.
SOURCE_CATALOG={
    "us_noaa_ncei_storm_events": {
        "country":"US","covers":("HISTORICAL_STORM_EVENT",),
        "url":"https://www.ncei.noaa.gov/access/storm-events-database/",
        "source_policy":"OFFICIAL_PUBLIC_REFERENCE_REVIEW_DOWNLOAD_TERMS",
    },
    "us_noaa_ncei_climate": {
        "country":"US","covers":("HISTORICAL_WEATHER",),
        "url":"https://www.ncei.noaa.gov/cdo-web/",
        "source_policy":"OFFICIAL_PUBLIC_REFERENCE_REVIEW_DOWNLOAD_TERMS",
    },
    "us_fema_national_risk_index": {
        "country":"US","covers":("HAZARD_ZONE_INDEX",),
        "url":"https://hazards.fema.gov/nri/",
        "source_policy":"OFFICIAL_PUBLIC_RISK_INDEX_NOT_SITE_DAMAGE",
    },
    "us_census_tiger_geography": {
        "country":"US","covers":("ADMINISTRATIVE_BOUNDARY_VERSION",),
        "url":"https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
        "source_policy":"OFFICIAL_BOUNDARY_VERSIONED_NOT_DEMOGRAPHIC_DATA",
    },
    "uk_ons_geography": {
        "country":"GB","covers":("ADMINISTRATIVE_BOUNDARY_VERSION",),
        "url":"https://www.ons.gov.uk/methodology/geography/geographicalproducts/namescodesandlookups",
        "source_policy":"OFFICIAL_GSS_IDENTIFIERS_CHECK_THIRD_PARTY_LICENCE",
    },
    "uk_ea_flood_monitoring": {
        "country":"GB","covers":("FLOOD_WARNING",),
        "url":"https://environment.data.gov.uk/flood-monitoring/doc/reference",
        "source_policy":"OGL_WITH_ATTRIBUTION_ENGLAND_ONLY",
    },
    "uk_ea_rainfall": {
        "country":"GB","covers":("HISTORICAL_WEATHER",),
        "url":"https://environment.data.gov.uk/flood-monitoring/doc/rainfall",
        "source_policy":"OGL_WITH_ATTRIBUTION_ENGLAND_ONLY",
    },
    "us_american_housing_survey": {
        "country":"US","covers":(),
        "url":"https://www.census.gov/programs-surveys/ahs/data.html",
        "source_policy":"REPORT_AND_SURVEY_REFERENCE_ONLY_NO_COUNTY_JOIN_VERIFIED",
    },
    "uk_english_housing_survey": {
        "country":"GB","covers":(),
        "url":"https://www.gov.uk/government/collections/english-housing-survey",
        "source_policy":"ENGLAND_ONLY_HOUSING_STOCK_REFERENCE_REVIEW_TERMS",
    },
    "uk_local_authority_stock_condition": {
        "country":"GB","covers":(),
        "url":"https://www.gov.uk/government/collections/english-housing-survey-local-authority-stock-condition-modelling",
        "source_policy":"ENGLAND_ONLY_MODELED_AREA_LEVEL_NOT_SITE_CONDITION",
    },
    "us_ibhs_fortified_material_guidance": {
        "country":"US","covers":(),
        "url":"https://fortifiedhome.org/",
        "source_policy":"REFERENCE_ONLY_MATERIAL_PERFORMANCE_NOT_INSTALLED_FACT",
    },
}

# Material categories and hazards are vocabulary for diagnosis ONLY.
# Do not attach any of these materials to a building/metro without
# an independently verified first-party material survey.
MATERIALS={
    "asphalt_shingle": ("hail","wind","heat","fire","roof_leak"),
    "standing_seam_metal": ("wind","hail","coastal_corrosion","thermal_movement"),
    "clay_concrete_tile": ("hail","wind","freeze_thaw","structural_loading"),
    "natural_slate": ("hail","freeze_thaw","wind","roof_leak"),
    "low_slope_membrane": ("ponding","heat","roof_leak","wind"),
    "timber_shingle": ("fire","moisture","wind"),
    "roof_underlayment": ("roof_leak","heat","moisture"),
    "flashing_gutters": ("roof_leak","wind","freeze_thaw"),
    "solar_pv_mounting": ("wind","hail","roof_leak","fire"),
    "insulation_air_sealing": ("heat","moisture","fire"),
}
HAZARDS=frozenset(x for v in MATERIALS.values() for x in v)|frozenset({
    "flood","heavy_rain","tornado","wildfire","seismic","snow_load"
})
PHYSICAL_TOPICS=frozenset({
    "materials","historical_storms","weather_climatology","floods",
    "hazard_zones","administrative_history","construction_era",
    "building_codes","insurance_exposure","building_stock",
    "labour_capacity","material_costs","energy_retrofit",
})
SOURCE_FOR_KIND={
    kind:{key for key,desc in SOURCE_CATALOG.items() if kind in desc["covers"]}
    for kind in {
        "HISTORICAL_STORM_EVENT","HISTORICAL_WEATHER","HAZARD_ZONE_INDEX",
        "ADMINISTRATIVE_BOUNDARY_VERSION","FLOOD_WARNING",
    }
}


def _iso(value: Any) -> datetime:
    if not isinstance(value,str) or len(value)>55:
        raise ValueError("invalid observation timestamp")
    try:
        moment=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observation timestamp") from exc
    if moment.utcoffset() is None:
        raise ValueError("timezone required")
    return moment.astimezone(timezone.utc)


def _digest(*values: Any) -> str:
    return sha256(json.dumps(values,sort_keys=True,separators=(",",":"),
                             allow_nan=False).encode()).hexdigest()


def _evidence(row: Mapping[str,Any], *, as_of: datetime) -> dict[str, Any]:
    required={
        "source_id","observation_kind","country_code","area_code",
        "area_code_system","event_type","event_started_at",
        "event_ended_at","source_published_at","first_observed_at",
        "source_record_sha256","area_match_verified","reuse_rights_reviewed",
        "data_granularity",
    }
    if not isinstance(row,Mapping) or set(row)!=required:
        raise ValueError("official geography evidence schema mismatch")
    sid=row["source_id"]
    kind=row["observation_kind"]
    source=SOURCE_CATALOG.get(sid)
    if source is None or kind not in source["covers"]:
        raise ValueError("unrecognized source-kind authority")
    country=row["country_code"]
    if country!=source["country"]:
        raise ValueError("source geographic jurisdiction mismatch")
    if (row["area_code_system"]=="US_COUNTY_FIPS"
            and country=="US" and isinstance(row["area_code"],str)
            and US_FIPS.fullmatch(row["area_code"])):
        pass
    elif (row["area_code_system"]=="UK_GSS"
          and country=="GB" and isinstance(row["area_code"],str)
          and GB_GSS.fullmatch(row["area_code"])):
        pass
    else:
        raise ValueError("official area identifier required")
    if (not isinstance(row["event_type"],str)
            or not SAFE_EVENT.fullmatch(row["event_type"])
            or row["event_type"] not in HAZARDS
            and kind not in ("ADMINISTRATIVE_BOUNDARY_VERSION","HISTORICAL_WEATHER")):
        raise ValueError("event type outside reviewed physical ontology")
    if row["data_granularity"] not in ("COUNTY_OR_ADMIN_AREA","SOURCE_ZONE"):
        raise ValueError("property-level inference prohibited")
    if row["area_match_verified"] is not True or row["reuse_rights_reviewed"] is not True:
        raise ValueError("source rights or area origin not verified")
    digest=row["source_record_sha256"]
    if not isinstance(digest,str) or not SHA.fullmatch(digest):
        raise ValueError("source record digest required")
    start=_iso(row["event_started_at"])
    end=_iso(row["event_ended_at"])
    published=_iso(row["source_published_at"])
    first_seen=_iso(row["first_observed_at"])
    if (end<start or published>as_of or first_seen>as_of
            or first_seen<published
            or published<start-timedelta(days=MAX_SOURCE_LATENCY_DAYS)):
        raise ValueError("historical source not available as of capture")
    if kind in ("HISTORICAL_STORM_EVENT","HISTORICAL_WEATHER") and (
        start>as_of or end>as_of or published<end
    ):
        raise ValueError("historical event cannot be future or unpublished")
    # Forecast zones are spatially descriptive; not forecasted direct loss.
    return {
        "source_id":sid,"observation_kind":kind,
        "country_code":country,
        "area_code_system":row["area_code_system"],
        "area_code":row["area_code"],
        "source_record_sha256":digest,
        "event_type":row["event_type"],
        "event_started_at":start.isoformat(),
        "event_ended_at":end.isoformat(),
        "source_published_at":published.isoformat(),
        "first_observed_at":first_seen.isoformat(),
        "data_granularity":row["data_granularity"],
    }


def build_geophysical_knowledge_context(
    *, as_of: datetime,
    original_area_evidence: Sequence[Mapping[str,Any]]=(),
) -> dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware geophysical graph time required")
    now=as_of.astimezone(timezone.utc)
    if (not isinstance(original_area_evidence,(list,tuple))
            or len(original_area_evidence)>MAX_OBSERVATIONS):
        raise ValueError("bounded licensed physical source evidence required")
    markets=acquisition_markets()
    if len({m.market_id for m in markets})!=len(markets):
        raise ValueError("canonical geographic anchor collision")
    observations=[]
    seen=set()
    for row in original_area_evidence:
        value=_evidence(row,as_of=now)
        fingerprint=_digest(value)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        observations.append((fingerprint,value))
    nodes={}
    edges={}
    def node(kind: str, key: str, metadata: Mapping[str,Any] | None=None)->str:
        ident=kind+":"+key
        entry={"node_id":ident,"node_type":kind,"metadata":dict(metadata or {})}
        if ident in nodes and nodes[ident]!=entry:
            raise ValueError("conflicting physical node")
        nodes[ident]=entry
        return ident
    def edge(a: str, rel: str, b: str, provenance: str, at: str | None=None)->None:
        if a not in nodes or b not in nodes:
            raise ValueError("unresolved material/geographic relation")
        key=_digest(a,rel,b,provenance)
        entry={
            "edge_id":"edge_"+key[:24],"source":a,"relation":rel,
            "target":b,"provenance_sha256":provenance,
            "observed_at":at,
            "claim_status":"CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF",
        }
        edges[key]=entry
    for market in markets:
        region=node("geographic_region",market.country_code+"-"+market.region_code,{
            "country_code":market.country_code,
            "region_code":market.region_code,
            "boundary_verified":False,
        })
        city=node("geo_market_anchor",market.market_id,{
            "country_code":market.country_code,
            "region_code":market.region_code,
            "market_name":market.metro,
            "anchor_type":"CITY_CENTROID_NOT_COUNTY_OR_STORM_ZONE",
            "county_or_admin_area_verified":False,
            "building_stock_verified":False,
        })
        edge(city,"GEO_ANCHOR_IN_DECLARED_REGION",region,
             _digest("existing_empire_geo_registry",market.market_id))
    for source_id,source in sorted(SOURCE_CATALOG.items()):
        node("geophysical_source",source_id,{
            "country_code":source["country"],
            "reference_url":source["url"],
            "source_access_policy":source["source_policy"],
            "actual_dataset_imported":False,
            "official_reference_is_property_evidence":False,
        })
    for material,concerns in sorted(MATERIALS.items()):
        m=node("material_category",material,{
            "installed_on_any_property_verified":False,
            "manufacturer_or_sku_performance_verified":False,
            "site_survey_required":True,
        })
        for concern in concerns:
            h=node("hazard_topic",concern,{
                "physical_risk_estimated":False,
                "property_damage_verified":False,
            })
            edge(m,"MATERIAL_REQUIRES_CONDITION_ASSESSMENT_FOR",h,
                 _digest("material_question_taxonomy",material,concern))
    for hazard in sorted(HAZARDS):
        node("hazard_topic",hazard,{
            "physical_risk_estimated":False,
            "property_damage_verified":False,
        })
    for theme in sorted(PHYSICAL_TOPICS):
        node("geophysical_question_theme",theme,{
            "site_facts_verified":False,
            "requires_applicable_local_evidence":True,
        })
    for fingerprint,value in observations:
        kind=value["observation_kind"]
        datum=node("physical_area_observation",fingerprint[:24],{
            "source_kind":kind,
            "observation_kind":kind,
            "country_code":value["country_code"],
            "area_code_system":value["area_code_system"],
            "area_code":value["area_code"],
            "event_type":value["event_type"],
            "event_started_at":value["event_started_at"],
            "event_ended_at":value["event_ended_at"],
            "first_observed_at":value["first_observed_at"],
            "source_published_at":value["source_published_at"],
            "original_source_sha256":value["source_record_sha256"],
            "source_available_before_current_decision":True,
            "source_origin_authenticated_by_this_adapter":False,
            "area_polygon_overlap_verified":False,
            "building_affected_verified":False,
            "individual_property_damage_verified":False,
        })
        edge(datum,"OBSERVED_IN_OFFICIAL_ADMIN_AREA",
             node("official_admin_area",value["country_code"]+":"+value["area_code_system"]+":"+value["area_code"],{
                 "country_code":value["country_code"],
                 "area_code_system":value["area_code_system"],
                 "official_code":value["area_code"],
                 "source_boundary_geometry_loaded":False,
             }),fingerprint,value["first_observed_at"])
        edge(datum,"SOURCE_DOCUMENTED_BY",
             "geophysical_source:"+value["source_id"],
             fingerprint,value["source_published_at"])
        if value["event_type"] in HAZARDS:
            edge(datum,"SOURCE_TAGGED_HAZARD_TOPIC",
                 "hazard_topic:"+value["event_type"],fingerprint,
                 value["source_published_at"])
    return {
        "schema_version":SCHEMA,
        "status":"OFFICIAL_SOURCE_CATALOG_AND_MATERIAL_ONTOLOGY_ONLY"
        if not observations else "STAGED_AREA_EVIDENCE_SOURCE_AUTHENTICITY_NOT_VERIFIED",
        "mode":"OBSERVE",
        "as_of":now.isoformat(),
        "canonical_geographic_market_anchors":len(markets),
        "official_source_references":len(SOURCE_CATALOG),
        "source_catalog_references_not_imported":len(SOURCE_CATALOG),
        "material_categories":len(MATERIALS),
        "hazard_topics":len(HAZARDS),
        "research_question_topics":len(PHYSICAL_TOPICS),
        "staged_area_observation_rows":len(observations),
        "actual_historical_storm_events_imported":0,
        "staged_historical_storm_source_rows":sum(
            v["observation_kind"]=="HISTORICAL_STORM_EVENT"
            for _,v in observations),
        "original_official_record_authenticated_by_adapter":False,
        "local_code_versions_verified":False,
        "market_anchor_is_official_county_mapping":False,
        "site_materials_installed_verified":False,
        "building_damage_verified":False,
        "buyer_demand_verified":False,
        "conversion_probability_verified":False,
        "country_specific_coverage_not_global":True,
        "nodes":list(sorted(nodes.values(),key=lambda x:x["node_id"])),
        "edges":list(sorted(edges.values(),key=lambda x:x["edge_id"])),
        "original_data_reused_for_model_training":False,
        "external_network_requests":False,
        "canonical_empiredb_writes":False,
        "outbound_authorized":False,
        "execution_authority":"none",
    }


def augment_market_graph_with_geo_materials(
    market_graph: Mapping[str,Any], geo_graph: Mapping[str,Any]
)->dict[str,Any]:
    if (not isinstance(market_graph,Mapping) or not isinstance(geo_graph,Mapping)
            or market_graph.get("schema_version")!=MARKET_SCHEMA
            or market_graph.get("execution_authority")!="none"
            or geo_graph.get("schema_version")!=SCHEMA
            or geo_graph.get("execution_authority")!="none"
            or geo_graph.get("original_data_reused_for_model_training") is not False
            or geo_graph.get("building_damage_verified") is not False):
        raise ValueError("untrusted geographic/market graph")
    combined=dict(market_graph)
    original={n["node_id"]:n for n in combined["nodes"]}
    for node in geo_graph["nodes"]:
        key=node["node_id"]
        if key in original and original[key]!=node:
            raise ValueError("cross-layer geographic node identity collision")
        original[key]=node
    all_edges={e["edge_id"]:e for e in combined["edges"]}
    for edge in geo_graph["edges"]:
        key=edge["edge_id"]
        if key in all_edges and all_edges[key]!=edge:
            raise ValueError("cross-layer geographic relation collision")
        all_edges[key]=edge
    # Explicit links connect materials/hazards to the EXISTING market and
    # Pain-Solution Engine; these are investigation prompts, not claims
    # that a person has a problem, owns a material, or bought a service.
    typed_bridges={
        **{"material_category:"+key:"market_vertical:roofing"
           for key in MATERIALS if key not in ("solar_pv_mounting","insulation_air_sealing")},
        "material_category:solar_pv_mounting":"market_vertical:solar",
        "material_category:insulation_air_sealing":"market_vertical:hvac",
    }
    for source,target in sorted(typed_bridges.items()):
        if source not in original or target not in original:
            continue
        p=_digest("catalogue_review_question",source,target)
        link_id="edge_"+_digest(source,"INFORMS_MARKET_MATERIAL_RESEARCH",target,p)[:24]
        all_edges[link_id]={
            "edge_id":link_id,"source":source,
            "relation":"INFORMS_MARKET_MATERIAL_RESEARCH","target":target,
            "provenance_sha256":p,"observed_at":None,
            "claim_status":"CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF",
        }
    storm_theme="problem_theme:storm_demand"
    if storm_theme in original:
        for hazard in ("hail","wind","flood","heavy_rain","tornado"):
            source="hazard_topic:"+hazard
            if source not in original:
                continue
            p=_digest("hazard_question_map",hazard)
            link_id="edge_"+_digest(source,"SUGGESTS_UNVERIFIED_STORM_PAIN_QUESTION",storm_theme,p)[:24]
            all_edges[link_id]={
                "edge_id":link_id,"source":source,
                "relation":"SUGGESTS_UNVERIFIED_STORM_PAIN_QUESTION",
                "target":storm_theme,"provenance_sha256":p,
                "observed_at":None,
                "claim_status":"CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF",
            }
    # No invented physical area=>property edges.
    combined["nodes"]=list(sorted(original.values(),key=lambda n:n["node_id"]))
    combined["edges"]=list(sorted(all_edges.values(),key=lambda e:e["edge_id"]))
    combined["node_count"]=len(combined["nodes"])
    combined["edge_count"]=len(combined["edges"])
    combined["geophysical_subgraph_attached"]=True
    combined["geophysical_observation_count"]=geo_graph[
        "staged_area_observation_rows"]
    return combined

# Static diagnostic questions are not site surveys, quotes or technical advice.
# Every chosen item needs evidence from the actual jurisdiction and building.
DUE_DILIGENCE={
    "roofing":(
        "Verify the actual roof assembly, material and installation/repair date",
        "Inspect roof age, underlayment, flashing, gutters, drainage and slope",
        "Join official dated storm/hail/wind history only by verified area boundary",
        "Compare applicable code edition, permits and insurer coverage",
        "Check lawful labour availability and replacement-material lead times",
        "Verify the customer's actual problem and authorised inspection results",
    ),
    "solar":(
        "Check roof type, condition, structural loading and waterproofing",
        "Verify irradiation and weather with an appropriately dated measurement source",
        "Check site-specific shade, roof age and local grid/interconnection rules",
        "Compare measured energy use, tariff history and system installation quotes",
        "Verify insurer, warranty, labour and real customer capacity",
    ),
    "hvac":(
        "Confirm equipment age, refrigerant, maintenance and verified failure history",
        "Use local historical heating/cooling degree days and extreme weather",
        "Check building insulation, humidity, size and site-specific load calculation",
        "Verify codes, permits, refrigerant rules and contractor capacity",
        "Compare documented energy prices and actual operating costs",
    ),
    "all_markets":(
        "Resolve the jurisdiction using authoritative date-versioned boundary IDs",
        "Check building stock era and survey uncertainty before inferring materials",
        "Separate hazard climatology, historical events, forecasts and alerts",
        "Verify applicable regulations and effective date, not just current rules",
        "Record trade availability, prices, repairs and insurance terms only from originals",
        "Confirm a real person or company's current need before commercial ranking",
    ),
}


def prepare_geophysical_market_brief(
    context: Mapping[str,Any], *, market_id: str, vertical: str = "roofing",
) -> dict[str,Any]:
    """Trust only an existing geo registry anchor; do not guess a county."""
    if (not isinstance(context,Mapping)
            or context.get("schema_version")!=SCHEMA
            or context.get("execution_authority")!="none"
            or context.get("building_damage_verified") is not False
            or context.get("market_anchor_is_official_county_mapping") is not False
            or context.get("canonical_empiredb_writes") is not False):
        raise ValueError("untrusted geographic context")
    market = next(
        (m for m in acquisition_markets() if m.market_id==market_id),
        None
    )
    if market is None or vertical not in DUE_DILIGENCE:
        raise ValueError("unknown research market or problem vertical")
    country=market.country_code
    source_ids=[]
    held_source_ids=[]
    for source_id,source in SOURCE_CATALOG.items():
        if source["country"]!=country:
            continue
        if ("ENGLAND_ONLY" in source["source_policy"]
                and market.region_code!="England"):
            held_source_ids.append(source_id)
            continue
        source_ids.append(source_id)
    return {
        "schema_version":"empire.flagship.geo_material.market_brief.v1",
        "status":"PHYSICAL_CONTEXT_RESEARCH_READY_NO_LOCAL_FACTS",
        "market_id":market.market_id,
        "country_code":country,
        "region_code":market.region_code,
        "metro_label":market.metro,
        "city_or_town_is_official_county_boundary":False,
        "official_country_area_crosswalk_loaded":False,
        "source_references_to_research":source_ids,
        "sources_held_for_jurisdiction":held_source_ids,
        "source_reference_is_ingested_dataset":False,
        "research_questions":list(DUE_DILIGENCE[vertical]),
        "materials_to_verify_on_site":list(sorted(MATERIALS))
        if vertical in ("roofing","solar") else [],
        "weather_or_storm_property_damage_proven":False,
        "historical_local_area_event_count":None,
        "building_code_version_verified":False,
        "material_cost_or_labour_capacity_verified":False,
        "buyer_need_or_solution_sale_verified":False,
        "execution_authority":"none",
    }
