"""Prospective market feature custody: genuine sources ≠ verified outcomes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from empire_os.flagship_market_knowledge_graph import build_market_knowledge_graph
from empire_os.flagship_predictive_market_features import (
    MARKETS, build_point_in_time_market_features,
    review_market_feature_prediction_gap,
)
from test_flagship_market_knowledge_graph import fixture, safe_example, NOW


def feature_graph(tmp_path, *, with_synthetic_example=False):
    fixture(tmp_path)
    return build_market_knowledge_graph(
        tmp_path, as_of=NOW,
        approved_examples=[safe_example()] if with_synthetic_example else [],
    )


def test_real_source_feature_evidence_no_forecast_or_synthetic_outcome(tmp_path):
    g=feature_graph(tmp_path,with_synthetic_example=True)
    packet=build_point_in_time_market_features(g,issued_at=NOW)
    assert packet["schema_version"]=="empire.predictive_revenue.market_feature_snapshot.v1"
    assert packet["market_count"]==6
    assert packet["verified_terminal_outcome_pairs"]==0
    assert packet["historical_forecast_registry_receipt"] is None
    assert packet["model_training_activated"] is False
    assert packet["future_source_information_used"] is False
    assert packet["approved_scenario_lessons_are_not_training_labels"] is True
    assert packet["observed_public_post_total"]==1
    agency=next(r for r in packet["market_features"] if r["market_vertical"]=="agency")
    assert agency["source_venue_count"]==2
    assert agency["distinct_attributable_public_posts"]==1
    assert agency["unverified_problem_theme_counts"]=={
        "lead_generation":1,"sales_conversion":1
    }
    assert agency["forecast_probability"] is None
    assert agency["forecast_revenue_cents"] is None
    assert agency["predictive_model_training_ready"] is False
    assert agency["public_posts_are_independent_buyer_samples"] is False
    assert "sales_conversion" in agency["unverified_problem_theme_counts"]
    result=review_market_feature_prediction_gap(packet)
    assert result["status"]=="SCIENTIFIC_EVIDENCE_PREPARED_FORECAST_HELD"
    assert result["market_count"]==6
    assert result["market_features_with_observed_public_topics"]==1
    assert result["independent_validation_available"] is False
    assert result["brier_evaluation_available"] is False
    assert result["prediction_issued"] is False
    assert result["realized_revenue_verified"] is False
    assert "Sensitive conversation example" not in json.dumps(packet)
    assert "Private Poster" not in json.dumps(packet)
    assert "07700111222" not in json.dumps(packet)
    assert not (tmp_path/"predictions").exists()


def test_future_graph_cannot_leak_into_historical_forecast(tmp_path):
    graph=feature_graph(tmp_path)
    with pytest.raises(ValueError,match="not captured before"):
        build_point_in_time_market_features(graph,issued_at=NOW-timedelta(seconds=1))
    with pytest.raises(ValueError,match="not captured before"):
        build_point_in_time_market_features(graph,issued_at=NOW+timedelta(hours=7))


def test_unknown_market_activity_not_reported_as_zero_demand(tmp_path):
    graph=feature_graph(tmp_path)
    packet=build_point_in_time_market_features(graph,issued_at=NOW)
    roof=next(r for r in packet["market_features"] if r["market_vertical"]=="roofing")
    assert roof["source_venue_count"]==3
    assert roof["distinct_attributable_public_posts"]==0
    assert roof["market_demand_zero_verified"] is False
    assert roof["readiness_status"]=="NO_ATTRIBUTABLE_PUBLIC_MARKET_EVIDENCE"
    assert roof["forecast_probability"] is None
    assert packet["market_count"]==len(MARKETS)


@pytest.mark.parametrize("days",[0,91,True,None,-1,"30",2.5])
def test_unsupported_forecast_horizons_rejected(tmp_path,days):
    graph=feature_graph(tmp_path)
    with pytest.raises(ValueError):
        build_point_in_time_market_features(graph,issued_at=NOW,horizon_days=days)


@pytest.mark.parametrize("field",[
    "buyer_conversation_verified","customer_roi_verified",
    "model_weights_updated","community_text_reused_for_training",
    "external_crawler_run","customer_data_accessed",
    "payment_authorized","outbound_authorized",
])
def test_forecast_features_cannot_accept_execution_or_verified_sales_claim(tmp_path,field):
    graph=feature_graph(tmp_path)
    graph[field]=True
    with pytest.raises(ValueError,match="untrusted graph"):
        build_point_in_time_market_features(graph,issued_at=NOW)


@pytest.mark.parametrize("field,value",[
    ("execution_authority","root"),
    ("mode","LIVE"),
    ("status","CUSTOMER_READY"),
    ("node_count",900),
    ("edge_count",900),
])
def test_untrusted_graph_schema_or_counts_held(tmp_path,field,value):
    graph=feature_graph(tmp_path)
    graph[field]=value
    with pytest.raises(ValueError):
        build_point_in_time_market_features(graph,issued_at=NOW)


def test_forged_future_source_edge_is_rejected(tmp_path):
    graph=feature_graph(tmp_path)
    original=next(x for x in graph["edges"]
                  if x["relation"]=="CITED_FROM_PUBLIC_SOURCE")
    original["observed_at"]=(NOW+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError,match="future source"):
        build_point_in_time_market_features(graph,issued_at=NOW)


def test_forged_topic_without_citation_cannot_be_counted(tmp_path):
    graph=feature_graph(tmp_path)
    line=next(x for x in graph["edges"]
              if x["relation"]=="UNVERIFIED_TOPIC_TAG")
    line["source"]="research_source:reddit_agency"
    with pytest.raises(ValueError,match="spoofed public theme"):
        build_point_in_time_market_features(graph,issued_at=NOW)


def test_source_topic_chronology_cannot_shift_engagement_date(tmp_path):
    graph=feature_graph(tmp_path)
    line=next(x for x in graph["edges"]
              if x["relation"]=="UNVERIFIED_TOPIC_TAG")
    line["observed_at"]=(NOW-timedelta(days=1)).isoformat()
    with pytest.raises(ValueError,match="chronology conflict"):
        build_point_in_time_market_features(graph,issued_at=NOW)


def test_duplicate_links_dont_spuriously_double_market_signal(tmp_path):
    graph=feature_graph(tmp_path)
    duplicate=deepcopy(graph["edges"][0])
    graph["edges"].append(duplicate)
    graph["edge_count"]+=1
    with pytest.raises(ValueError,match="untrusted graph edge"):
        build_point_in_time_market_features(graph,issued_at=NOW)


def test_recomputed_packet_hash_detects_after_the_fact_edit(tmp_path):
    packet=build_point_in_time_market_features(feature_graph(tmp_path),issued_at=NOW)
    packet["market_features"][0]["forecast_probability"]=0.99
    with pytest.raises(ValueError,match="tampered"):
        review_market_feature_prediction_gap(packet)


def test_deterministic_same_clock_and_sources(tmp_path):
    graph=feature_graph(tmp_path)
    first=build_point_in_time_market_features(graph,issued_at=NOW)
    second=build_point_in_time_market_features(graph,issued_at=NOW)
    assert first==second
    later=build_point_in_time_market_features(
        graph,issued_at=NOW+timedelta(minutes=1)
    )
    assert first["feature_packet_sha256"]!=later["feature_packet_sha256"]
    assert later["feature_issued_at"]!=first["feature_issued_at"]


def test_out_of_window_public_research_is_not_usable_predictive_signal(tmp_path):
    # This is a prospective source graph captured now with no recently
    # attributable post; no historic reconstruction of future data.
    fixture(tmp_path,rows=[])
    graph=build_market_knowledge_graph(tmp_path,as_of=NOW)
    packet=build_point_in_time_market_features(graph,issued_at=NOW)
    assert packet["observed_public_post_total"]==0
    assert all(row["market_demand_zero_verified"] is False
               for row in packet["market_features"])


def test_market_feature_packet_never_contains_approved_chat_example_text(tmp_path):
    graph=feature_graph(tmp_path,with_synthetic_example=True)
    packet=build_point_in_time_market_features(graph,issued_at=NOW)
    serialized=json.dumps(packet)
    assert "example_roofing_001" not in serialized
    assert "VERIFY_SERVICE_AREA" not in serialized
    assert "synthetic model-only example" not in serialized
    assert packet["historical_forecast_registry_receipt"] is None


def test_existing_quant_brain_receives_no_invented_economics(tmp_path):
    from empire_os.quant_brain import _DECISION_PACKET_REQUIRED
    graph=feature_graph(tmp_path)
    packet=build_point_in_time_market_features(graph,issued_at=NOW)
    result=review_market_feature_prediction_gap(packet)
    assert result["ready_quant_packet_count"]==0
    assert len(result["canonical_quant_brain_missing_inputs"])==len(MARKETS)
    for row in result["canonical_quant_brain_missing_inputs"]:
        assert row["quant_status"]=="UNAVAILABLE"
        assert row["verified_buyer_terms"] is False
        assert row["market_features_alone_sufficient_for_quant"] is False
        assert set(row["missing_commercial_inputs"])==set(_DECISION_PACKET_REQUIRED)
        assert len(row["source_feature_lineage_sha256"])==64
