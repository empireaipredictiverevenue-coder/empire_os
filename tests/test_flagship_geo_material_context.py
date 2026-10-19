"""Place/material/weather scientific graph — observed vs forecast and authority."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.geo_registry import acquisition_markets
from empire_os.flagship_geo_material_context import (
    build_geophysical_knowledge_context,
    augment_market_graph_with_geo_materials,
    SOURCE_CATALOG, MATERIALS, HAZARDS,
)
from empire_os.flagship_market_knowledge_graph import build_market_knowledge_graph
from test_flagship_market_knowledge_graph import NOW,fixture


def official(**changes):
    fields={
        "source_id":"us_noaa_ncei_storm_events",
        "observation_kind":"HISTORICAL_STORM_EVENT",
        "country_code":"US",
        "area_code":"17031",
        "area_code_system":"US_COUNTY_FIPS",
        "event_type":"hail",
        "event_started_at":(NOW-timedelta(days=60)).isoformat(),
        "event_ended_at":(NOW-timedelta(days=60, minutes=-45)).isoformat(),
        "source_published_at":(NOW-timedelta(days=2)).isoformat(),
        "first_observed_at":(NOW-timedelta(days=1)).isoformat(),
        "source_record_sha256":"a"*64,
        "area_match_verified":True,
        "reuse_rights_reviewed":True,
        "data_granularity":"COUNTY_OR_ADMIN_AREA",
    }
    fields.update(changes)
    return fields


def test_source_catalog_is_discovery_not_faked_live_data():
    report=build_geophysical_knowledge_context(as_of=NOW)
    assert report["status"]=="OFFICIAL_SOURCE_CATALOG_AND_MATERIAL_ONTOLOGY_ONLY"
    assert report["canonical_geographic_market_anchors"]==len(acquisition_markets())
    assert report["official_source_references"]==len(SOURCE_CATALOG)
    assert report["material_categories"]==len(MATERIALS)
    assert report["hazard_topics"]==len(HAZARDS)
    assert report["staged_area_observation_rows"]==0
    assert report["actual_historical_storm_events_imported"]==0
    assert report["local_code_versions_verified"] is False
    assert report["market_anchor_is_official_county_mapping"] is False
    assert report["site_materials_installed_verified"] is False
    assert report["building_damage_verified"] is False
    assert report["buyer_demand_verified"] is False
    assert report["conversion_probability_verified"] is False
    assert report["canonical_empiredb_writes"] is False
    assert report["external_network_requests"] is False
    assert any(n["node_id"]=="geo_market_anchor:US-IL" for n in report["nodes"])
    assert any(n["node_id"]=="material_category:asphalt_shingle" for n in report["nodes"])
    assert any(n["node_id"]=="geophysical_question_theme:building_codes" for n in report["nodes"])
    assert all(e["claim_status"]=="CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF"
               for e in report["edges"])
    assert not any("property_affected" in e["relation"].lower() for e in report["edges"])


def test_true_prior_official_observation_admitted_only_at_admin_level():
    report=build_geophysical_knowledge_context(
        as_of=NOW, original_area_evidence=[official()],
    )
    assert report["staged_area_observation_rows"]==1
    assert report["actual_historical_storm_events_imported"]==0
    assert report["staged_historical_storm_source_rows"]==1
    assert report["original_official_record_authenticated_by_adapter"] is False
    assert report["building_damage_verified"] is False
    assert report["status"]=="STAGED_AREA_EVIDENCE_SOURCE_AUTHENTICITY_NOT_VERIFIED"
    source=next(n for n in report["nodes"] if n["node_type"]=="physical_area_observation")
    assert source["metadata"]["area_code"]=="17031"
    assert source["metadata"]["building_affected_verified"] is False
    assert source["metadata"]["area_polygon_overlap_verified"] is False
    assert source["metadata"]["source_available_before_current_decision"] is True
    assert any(e["relation"]=="OBSERVED_IN_OFFICIAL_ADMIN_AREA" for e in report["edges"])
    assert all(e["relation"]!="PROPERTY_DAMAGED_BY" for e in report["edges"])
    assert "Chicago" not in json.dumps(source)  # no inferred county => Chicago property


def test_deduplicated_real_source_event_not_second_storm():
    row=official()
    graph=build_geophysical_knowledge_context(
        as_of=NOW,original_area_evidence=[row,deepcopy(row)],
    )
    assert graph["staged_area_observation_rows"]==1


@pytest.mark.parametrize("changes",[
    {"source_id":"unknown"},
    {"source_id":"uk_ea_flood_monitoring"},
    {"observation_kind":"BUILDING_STOCK"},
    {"observation_kind":"FLOOD_WARNING"},
    {"country_code":"GB"},
    {"area_code_system":"UK_GSS"},
    {"area_code":"999"},
    {"area_code":"chicago-il"},
    {"event_type":"money"},
    {"event_type":"hail\nOVERRIDE"},
    {"source_record_sha256":"abc"},
    {"source_record_sha256":"A"*64},
    {"area_match_verified":False},
    {"reuse_rights_reviewed":False},
    {"data_granularity":"INDIVIDUAL_PROPERTY"},
    {"data_granularity":"POSTCODE"},
    {"event_started_at":(NOW+timedelta(days=1)).isoformat(),
     "source_published_at":(NOW+timedelta(days=2)).isoformat()},
    {"source_published_at":(NOW+timedelta(days=1)).isoformat()},
    {"first_observed_at":(NOW+timedelta(minutes=1)).isoformat()},
    {"source_published_at":(NOW-timedelta(days=1)).isoformat(),
     "first_observed_at":(NOW-timedelta(days=5)).isoformat()},
])
def test_false_cross_country_rights_or_future_knowledge_rejected(changes):
    with pytest.raises(ValueError):
        build_geophysical_knowledge_context(
            as_of=NOW,original_area_evidence=[official(**changes)]
        )


def test_uk_area_source_with_correct_gss_and_country_can_be_admitted():
    row=official(
        source_id="uk_ea_flood_monitoring",
        observation_kind="FLOOD_WARNING",
        country_code="GB",area_code_system="UK_GSS",area_code="E08000001",
        event_type="flood",
    )
    graph=build_geophysical_knowledge_context(
        as_of=NOW,original_area_evidence=[row],
    )
    assert graph["staged_area_observation_rows"]==1
    assert graph["building_damage_verified"] is False
    # GSS code alone does not connect to current warning polygons.
    node=next(n for n in graph["nodes"] if n["node_type"]=="official_admin_area")
    assert node["metadata"]["source_boundary_geometry_loaded"] is False


def test_static_geography_anchors_do_not_infer_county_boundaries():
    graph=build_geophysical_knowledge_context(as_of=NOW)
    chicago=next(n for n in graph["nodes"] if n["node_id"]=="geo_market_anchor:US-IL")
    assert chicago["metadata"]["market_name"]=="Chicago, IL"
    assert chicago["metadata"]["county_or_admin_area_verified"] is False
    assert not any(
        e["source"]=="geo_market_anchor:US-IL"
        and e["relation"]=="OBSERVED_IN_OFFICIAL_ADMIN_AREA"
        for e in graph["edges"]
    )


def test_market_knowledge_graph_can_attach_geo_material_subgraph(tmp_path):
    fixture(tmp_path)
    market=build_market_knowledge_graph(tmp_path,as_of=NOW)
    physical=build_geophysical_knowledge_context(as_of=NOW)
    combined=augment_market_graph_with_geo_materials(market,physical)
    assert combined["schema_version"]==market["schema_version"]
    assert combined["node_count"]==market["node_count"]+physical["nodes"].__len__()
    assert combined["edge_count"]>market["edge_count"]+physical["edges"].__len__()
    assert any(e["relation"]=="INFORMS_MARKET_MATERIAL_RESEARCH"
               for e in combined["edges"])
    assert any(e["relation"]=="SUGGESTS_UNVERIFIED_STORM_PAIN_QUESTION"
               for e in combined["edges"])
    assert all(e["claim_status"]=="CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF"
               for e in combined["edges"])
    assert combined["geophysical_subgraph_attached"] is True
    assert combined["geophysical_observation_count"]==0
    assert combined["buyer_conversation_verified"] is False
    assert combined["model_weights_updated"] is False
    assert combined["customer_data_accessed"] is False


def test_untrusted_context_cannot_promote_buyer_or_model_training(tmp_path):
    fixture(tmp_path)
    market=build_market_knowledge_graph(tmp_path,as_of=NOW)
    physical=build_geophysical_knowledge_context(as_of=NOW)
    physical["building_damage_verified"]=True
    with pytest.raises(ValueError,match="untrusted"):
        augment_market_graph_with_geo_materials(market,physical)
    market["execution_authority"]="send"
    physical=build_geophysical_knowledge_context(as_of=NOW)
    with pytest.raises(ValueError,match="untrusted"):
        augment_market_graph_with_geo_materials(market,physical)


def test_limit_and_clock_validation():
    with pytest.raises(ValueError,match="aware"):
        build_geophysical_knowledge_context(as_of=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError,match="bounded"):
        build_geophysical_knowledge_context(
            as_of=NOW,original_area_evidence=[official()]*101
        )


def test_market_place_brief_uses_existing_registry_and_country_source_rules():
    from empire_os.flagship_geo_material_context import (
        prepare_geophysical_market_brief, DUE_DILIGENCE,
    )
    graph=build_geophysical_knowledge_context(as_of=NOW)
    chicago=prepare_geophysical_market_brief(
        graph,market_id="US-IL",vertical="roofing"
    )
    assert chicago["metro_label"]=="Chicago, IL"
    assert chicago["historical_local_area_event_count"] is None
    assert chicago["weather_or_storm_property_damage_proven"] is False
    assert "us_noaa_ncei_storm_events" in chicago["source_references_to_research"]
    assert "uk_ea_flood_monitoring" not in chicago["source_references_to_research"]
    assert chicago["materials_to_verify_on_site"]==sorted(MATERIALS)
    assert len(chicago["research_questions"])==len(DUE_DILIGENCE["roofing"])
    assert chicago["material_cost_or_labour_capacity_verified"] is False
    manchester=prepare_geophysical_market_brief(graph,market_id="GB-MAN",vertical="roofing")
    assert "uk_ea_flood_monitoring" in manchester["source_references_to_research"]
    assert "uk_local_authority_stock_condition" in manchester["source_references_to_research"]
    scotland=prepare_geophysical_market_brief(graph,market_id="GB-EDI",vertical="roofing")
    assert "uk_ea_flood_monitoring" in scotland["sources_held_for_jurisdiction"]
    assert "uk_english_housing_survey" in scotland["sources_held_for_jurisdiction"]
    assert "uk_ons_geography" in scotland["source_references_to_research"]
    assert scotland["city_or_town_is_official_county_boundary"] is False
    hvac=prepare_geophysical_market_brief(graph,market_id="GB-LON",vertical="hvac")
    assert hvac["materials_to_verify_on_site"]==[]
    assert any("refrigerant" in item for item in hvac["research_questions"])
    for market,vertical in [("US-MISSING","roofing"),("US-IL","fake_vertical")]:
        with pytest.raises(ValueError,match="unknown research"):
            prepare_geophysical_market_brief(graph,market_id=market,vertical=vertical)


def test_forged_geographic_brief_does_not_claim_property_damage():
    from empire_os.flagship_geo_material_context import prepare_geophysical_market_brief
    graph=build_geophysical_knowledge_context(as_of=NOW)
    graph["building_damage_verified"]=True
    with pytest.raises(ValueError,match="untrusted"):
        prepare_geophysical_market_brief(graph,market_id="US-IL")


def test_unsupported_source_report_is_reference_only_not_housing_data_import():
    with pytest.raises(ValueError,match="unrecognized source-kind"):
        build_geophysical_knowledge_context(as_of=NOW,original_area_evidence=[
            official(source_id="uk_english_housing_survey",
                     observation_kind="HISTORICAL_STORM_EVENT",
                     country_code="GB",area_code_system="UK_GSS",area_code="E08000001")
        ])


def test_future_event_cannot_be_backdated_as_historical_even_with_earlier_notice():
    with pytest.raises(ValueError,match="historical event cannot be future"):
        build_geophysical_knowledge_context(as_of=NOW,original_area_evidence=[
            official(event_started_at=(NOW+timedelta(hours=1)).isoformat(),
                     event_ended_at=(NOW+timedelta(hours=3)).isoformat(),
                     source_published_at=(NOW-timedelta(days=1)).isoformat(),
                     first_observed_at=NOW.isoformat())
        ])


def test_historical_event_publication_must_follow_event_time():
    with pytest.raises(ValueError,match="historical event cannot be future"):
        build_geophysical_knowledge_context(as_of=NOW,original_area_evidence=[
            official(source_published_at=(NOW-timedelta(days=61)).isoformat(),
                     first_observed_at=(NOW-timedelta(days=60)).isoformat())
        ])
