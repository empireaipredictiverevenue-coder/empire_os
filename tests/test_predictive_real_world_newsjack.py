"""Explicit synthetic newsjack stories preserve truth, geography and consent."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from test_predictive_market_evidence_binding import review as territory_review, NOW
from empire_os.predictive_real_world_newsjack import review_newsjack_event_research


def digest(x):
    return sha256(x.encode()).hexdigest()


def record(n=1,*,event="market_change",kind="competitor",geo="little_rock_ar",
           niche="hvac",source="news",status="reported_article",
           risk="routine",certainty="observed",hours=2,cluster="market_story"):
    return {
        "event_key":event,
        "source_origin_key":f"publisher_{n}",
        "source_record_sha256":digest(f"source_original_{n}"),
        "source_family":source,
        "source_status":status,
        "event_category":kind,
        "news_context_safety":risk,
        "niche_key":niche,"geography_key":geo,
        "first_published_at":(NOW-timedelta(hours=hours)).isoformat(),
        "source_observed_at":(NOW-timedelta(hours=hours-1)).isoformat(),
        "headline_sha256":digest(f"headline_{n}"),
        "evidence_rights":"INTERNAL_RESEARCH_METADATA_ONLY",
        "claim_certainty":certainty,
        "story_cluster_key":cluster,
    }


def review(records=None,terr=None):
    return review_newsjack_event_research(
        records if records is not None else [record()],
        terr if terr is not None else territory_review(),as_of=NOW,
    )


def test_competitor_breaking_news_to_exact_market_research_brief_not_campaign():
    out=review()
    assert out["status"]=="NEWSJACK_RESEARCH_SIGNAL_TRIAGE_READY"
    assert out["event_cluster_count"]==1
    assert out["source_article_count"]==1
    r=out["event_research_cards"][0]
    assert r["territory_exact_research_match"] is True
    assert r["category"]=="competitor"
    assert r["niche_key"]=="hvac"
    assert r["geography_key"]=="little_rock_ar"
    assert r["hours_since_first_publication"]==2
    assert r["bounded_research_urgency_hours_remaining"]==70
    assert r["playbook_owner"].startswith("existing_strategy")
    assert r["proposed_playbook"]=="DRAFT_TIMELY_CONTEXTUAL_RESEARCH_BRIEF_FOR_REVIEW"
    assert r["strategy_driver_hypothesis"]=="competitor_response"
    assert r["driver_multiplier_inferred_from_news"] is False
    assert r["hypothetical_economic_twin_recalculated"] is False
    assert r["source_claim_is_verified_event_truth"] is False
    assert r["media_attention_is_purchase_probability"] is False
    assert r["independent_origins_verified"] is None
    assert out["media_publication_authorized"] is False
    assert out["outbound_sent"] is False
    assert out["database_writes"] is False


def test_tragedy_storm_disaster_in_market_is_helpful_safety_only():
    x=review([record(kind="storm_weather",risk="disaster")])
    r=x["event_research_cards"][0]
    assert r["proposed_playbook"]=="FACTUAL_PUBLIC_SAFETY_REVIEW_ONLY"
    assert r["news_safety_review_required"] is True
    assert r["strategy_driver_hypothesis"]=="weather_storm"
    assert r["commercial_publication_or_outreach_approved"] is False


@pytest.mark.parametrize("risk",[
    "death_or_injury","conflict","political","public_safety","private_person",
])
def test_sensitive_news_never_auto_drafts_promotional_angle(risk):
    x=review([record(risk=risk)])
    assert x["event_research_cards"][0]["proposed_playbook"]=="FACTUAL_PUBLIC_SAFETY_REVIEW_ONLY"


def test_media_and_wire_duplicate_do_not_establish_independent_corrob():
    a=record()
    b=deepcopy(a)
    dup=review([a,b])
    assert dup["source_article_count"]==1
    assert dup["duplicate_source_records_count"]==1
    r=dup["event_research_cards"][0]
    assert r["reported_source_records"]==1
    assert r["independent_origins_verified"] is None
    two=review([a,record(2)])
    assert two["event_research_cards"][0]["reported_source_records"]==2
    assert two["event_research_cards"][0]["independent_origins_verified"] is None
    assert two["event_research_cards"][0]["source_claim_is_verified_event_truth"] is False


def test_official_and_unconfirmed_coverage_do_not_promote_truth():
    original=record(source="official",status="official_notice")
    doubt=record(2,status="unconfirmed",certainty="possible")
    result=review([original,doubt])
    x=result["event_research_cards"][0]
    assert x["event_uncertain_or_forecast"] is True
    assert x["proposed_playbook"]=="CORROBORATE_ORIGINAL_EVENT_CLAIM"
    assert x["source_claim_is_verified_event_truth"] is False


def test_search_attention_is_not_buyer_intent_or_revenue():
    x=review([record(source="search",kind="market_demand")])
    card=x["event_research_cards"][0]
    assert card["media_attention_is_purchase_probability"] is False
    assert x["news_attention_is_authenticated_buyer_demand"] is False
    assert x["calibrated_profit_uplift_available"] is False


def test_wrong_geography_alias_must_not_auto_join():
    row=record(geo="littlerock_ar")
    out=review([row])
    card=out["event_research_cards"][0]
    assert card["territory_exact_research_match"] is False
    assert card["market_source_revision_sha256"] is None
    assert card["proposed_playbook"]=="RESEARCH_GEOGRAPHIC_AND_NICHE_BINDING"


def test_different_niche_same_city_is_not_buyer_match():
    out=review([record(niche="telehealth")])
    assert out["event_research_cards"][0]["territory_exact_research_match"] is False


def test_forecast_story_is_unconfirmed_market_intervention():
    out=review([record(status="forecast_or_outlook",certainty="forecast")])
    x=out["event_research_cards"][0]
    assert x["proposed_playbook"]=="CORROBORATE_ORIGINAL_EVENT_CLAIM"
    assert "SOURCE_FORECAST" in x["source_assertion_classes"] or "SOURCE_UNKNOWN" in x["source_assertion_classes"]


@pytest.mark.parametrize("field,value",[
    ("event_key","contact@example.com"),("source_record_sha256","not-a-hash"),
    ("headline_sha256","fake"),("story_cluster_key",""),
    ("source_origin_key","private@email.org"),("evidence_rights","RESELL_HEADLINES"),
    ("source_family","spyware"),("news_context_safety","HARMLESS_ALWAYS"),
    ("claim_certainty","CERTAIN_PURCHASE"),("event_category","crypto_pump"),
    ("first_published_at",NOW.isoformat()),
    ("source_observed_at",(NOW+timedelta(minutes=10)).isoformat()),
    ("geography_key","Private Street Address"),
])
def test_missing_source_rights_broken_times_or_private_data_hold(field,value):
    r=record()
    r[field]=value
    out=review([r])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"
    assert out["event_research_cards"]==[]
    assert out["media_publication_authorized"] is False
    assert out["execution_authority"]=="none"


def test_source_older_than_research_window_is_held():
    out=review([record(hours=80)])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"
    assert out["event_cluster_count"] is None


def test_reported_article_cannot_self_claim_official_notice():
    out=review([record(source="news",status="official_notice")])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"


def test_forecast_cannot_launder_as_observed_data():
    out=review([record(status="forecast_or_outlook",certainty="observed")])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"


def test_cluster_identity_collision_holds_instead_of_mixing_two_events():
    out=review([record(),record(2,event="completely_different_event")])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"
    assert out["hold_code"]=="EVENT_CLUSTER_IDENTITY_COLLISION"


def test_changing_origins_with_same_hash_is_not_evidence_of_more_independence():
    a=record()
    b=record(2)
    b["source_record_sha256"]=a["source_record_sha256"]
    out=review([a,b])
    assert out["status"]=="NEWSJACK_RESEARCH_SIGNAL_TRIAGE_READY"
    assert out["event_research_cards"][0]["independent_origins_verified"] is None


def test_source_same_digest_with_conflicting_payload_holds():
    a=record()
    b=deepcopy(a)
    b["claim_certainty"]="possible"
    out=review([a,b])
    assert out["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"


def test_empty_supplied_batch_is_not_evidence_of_global_no_news():
    x=review([])
    assert x["event_cluster_count"]==0
    assert x["real_time_news_collection_activated"] is False
    assert x["news_attention_is_authenticated_buyer_demand"] is False


def test_untrusted_territory_owner_blocks_event_join():
    terr=territory_review()
    terr["status"]="SALES_VERIFIED"
    assert review(terr=terr)["status"]=="REAL_WORLD_EVENT_SOURCE_HOLD"


def test_no_raw_headlines_urls_or_person_data_in_result():
    x=review([record()])
    serialized=json.dumps(x)
    assert "http" not in serialized
    assert "publisher_1" not in serialized
    assert "headline_1" not in serialized
    assert x["original_publisher_independence_authentication_available"] is False


def twin_bundle():
    from test_predictive_market_economic_twin import market,driver
    from test_predictive_profitability_playbooks import pilot,plan
    from empire_os.predictive_market_economic_twin import review_market_economic_twin
    from empire_os.predictive_market_evidence_binding import bind_territory_research_to_market_twin
    p=pilot()
    m=market()
    m["geography_key"]="little_rock_ar"
    twin=review_market_economic_twin(
        p,plan(p),m,[driver()],as_of=NOW,
    )
    return twin,bind_territory_research_to_market_twin(territory_review(),twin)


def test_news_event_links_to_existing_twin_only_as_research_trigger():
    from empire_os.predictive_real_world_newsjack import bind_newsjack_research_to_economic_twin
    twin,link=twin_bundle()
    result=bind_newsjack_research_to_economic_twin(review(),event_key="market_change",
                                                   twin=twin,territory_link=link)
    assert result["status"]=="EVENT_TO_TWIN_RESEARCH_PROPOSAL_ONLY"
    assert result["research_link_verified"] is True
    assert result["suggested_existing_twin_driver"]=="competitor_response"
    assert result["original_pilot_design_sha256"]==twin["original_pilot_design_sha256"]
    assert result["explicit_hypothetical_impact_parameters_required"] is True
    assert result["hypothetical_economic_shock_automatically_applied"] is False
    assert result["source_event_promotional_campaign_authorized"] is False
    assert result["scenario_uplift_calibrated"] is False
    assert result["execution_authority"]=="none"


def test_event_cannot_join_different_territory_market_revision():
    from empire_os.predictive_real_world_newsjack import bind_newsjack_research_to_economic_twin
    twin,link=twin_bundle()
    link["market_source_revision_fingerprint"]="0"*64
    result=bind_newsjack_research_to_economic_twin(
        review(),event_key="market_change",twin=twin,territory_link=link
    )
    assert result["status"]=="NEWS_EVENT_TWIN_SOURCE_BINDING_HOLD"
    assert result["hypothetical_economic_shock_automatically_applied"] is False


def test_event_cannot_join_unknown_or_wrong_storm_and_niche():
    from empire_os.predictive_real_world_newsjack import bind_newsjack_research_to_economic_twin
    twin,link=twin_bundle()
    out=bind_newsjack_research_to_economic_twin(
        review([record(event="storm_warning",kind="storm_weather",geo="nyc")]),
        event_key="storm_warning",twin=twin,territory_link=link,
    )
    assert out["research_link_verified"] is False
    assert out["news_event_is_paid_demand"] is False


def test_forged_twin_authentication_rejected():
    from empire_os.predictive_real_world_newsjack import bind_newsjack_research_to_economic_twin
    twin,link=twin_bundle()
    twin["source_market_conditions_authenticated"]=True
    with pytest.raises(ValueError):
        bind_newsjack_research_to_economic_twin(
            review(),event_key="market_change",twin=twin,territory_link=link,
        )


def test_optional_live_news_feed_unknown_when_not_connected(tmp_path):
    from empire_os.predictive_real_world_newsjack import review_newsjack_source_readiness_runtime
    x=review_newsjack_source_readiness_runtime(str(tmp_path),as_of=NOW)
    assert x["status"]=="LIVE_NEWS_SOURCE_NOT_CONNECTED"
    assert x["news_source_event_record_count"] is None
    assert x["news_research_result"] is None
    assert x["original_news_service_live_verified"] is False


def make_news_feed():
    return {
        "schema_version":"empire.news_event_source_metadata.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "generated_at":NOW.isoformat(),
        "source_owner":"existing_news_intelligence_source_owner",
        "licensing_internal_research_allowed":True,
        "raw_article_bodies_included":False,
        "publisher_provider_authentication_verified":False,
        "event_metadata":[record()],
    }


def test_read_only_news_feed_owner_contract_and_territory_research(tmp_path):
    from empire_os.predictive_real_world_newsjack import review_newsjack_source_readiness_runtime
    from test_predictive_market_evidence_binding import snapshot as market_snapshot
    root=tmp_path
    gps=root/"runtime/market_sweeps/revenue_gps_latest.json"
    gps.parent.mkdir(parents=True)
    gps.write_text(json.dumps(market_snapshot()))
    news=root/"runtime/real_world_news/latest.json"
    news.parent.mkdir(parents=True)
    news.write_text(json.dumps(make_news_feed()))
    (news.parent/"private_full_text.json").write_text("SECRET_NOT_READ")
    r=review_newsjack_source_readiness_runtime(str(root),as_of=NOW)
    assert r["status"]=="NEWS_FEED_INTERNAL_RESEARCH_REVIEWED"
    assert r["news_source_event_record_count"]==1
    assert r["news_research_result"]["event_cluster_count"]==1
    assert r["original_news_service_live_verified"] is False
    assert "SECRET_NOT_READ" not in json.dumps(r)


def test_news_feed_invalid_rights_and_source_age_hold_without_articles(tmp_path):
    from empire_os.predictive_real_world_newsjack import review_newsjack_source_readiness_runtime
    root=tmp_path
    file=root/"runtime/real_world_news/latest.json"
    file.parent.mkdir(parents=True)
    data=make_news_feed()
    data["licensing_internal_research_allowed"]=False
    file.write_text(json.dumps(data))
    assert review_newsjack_source_readiness_runtime(str(root),as_of=NOW)["status"]=="NEWS_FEED_SOURCE_CONTRACT_HOLD"
    data=make_news_feed()
    data["generated_at"]=(NOW-timedelta(days=2)).isoformat()
    file.write_text(json.dumps(data))
    assert review_newsjack_source_readiness_runtime(str(root),as_of=NOW)["status"]=="NEWS_SOURCE_EPOCH_HOLD"


def test_source_revision_changes_when_safety_context_or_claim_changes():
    first=review([record()])
    changed=review([record(risk="public_safety")])
    assert (first["event_research_cards"][0]["event_source_revision_sha256"]
            !=changed["event_research_cards"][0]["event_source_revision_sha256"])
    assert changed["event_research_cards"][0]["news_safety_review_required"] is True
    changed_claim=review([record(certainty="likely")])
    assert (first["event_research_cards"][0]["event_source_revision_sha256"]
            !=changed_claim["event_research_cards"][0]["event_source_revision_sha256"])


def jev_owner_review(status="RESEARCH_REVIEW"):
    row={
        "signal_id":"fixture:solar:1",
        "title":"Fictional solar policy source update for a test",
        "sector":"solar","market":"GB",
        "primary_source_url":"https://example.org/source",
        "published_at":(NOW-timedelta(hours=2)).isoformat(),
        "publication_date":None,
        "publication_precision":"instant",
        "evidence_refs":["fixture:source-capture"],
        "status":status,
        "missing_evidence":["independent_corroboration_required"],
        "corroboration_verified_by_input":False,
        "search_observation":None,
        "destination_url":None,
        "destination_operator_attested":False,
        "jev_shadow_decision":None,
        "traffic_channels_for_review":["organic_search"] if status=="RESEARCH_REVIEW" else [],
        "content_brief_recommendation_only":False,
        "actual_visitors":None,"actual_enquiries":None,"actual_revenue":False,
        "publishing_enabled":False,"outbound_enabled":False,
        "paid_media_spend_enabled":False,"execution_authority":"none",
        "evidence_fingerprint":digest("source_original_report"),
    }
    return {
        "schema_version":"empire.organic.newsjack_jev_review.v1",
        "mode":"OBSERVE","candidate_count":1,
        "status_counts":{status:1},"candidates":[row],
        "source_collector":"existing_authorised_news_and_research_owner",
        "jev_provider_active":False,
        "newsjack_installed_or_invoked":False,"gsc_queried":False,
        "publishing_enabled":False,"outbound_enabled":False,
        "payment_enabled":False,"execution_authority":"none",
    }


def test_reuse_existing_newsjack_jev_owner_contract_without_new_scraper():
    from empire_os.predictive_real_world_newsjack import review_existing_jev_newsjack_handoff
    output=review_existing_jev_newsjack_handoff(jev_owner_review(),as_of=NOW)
    assert output["status"]=="JEV_NEWSJACK_SOURCE_RESEARCH_REVIEWED"
    assert output["jev_owner_review_verified"] is True
    assert output["source_signal_count"]==1
    card=output["national_scope_research_cards"][0]
    assert card["market_country_scope"]=="GB"
    assert card["sector_research_scope"]=="solar"
    assert card["original_jev_status"]=="RESEARCH_REVIEW"
    assert card["country_scope_proves_exact_service_territory"] is False
    assert card["source_signal_is_authenticated_demand"] is False
    assert card["source_signal_is_verified_incremental_revenue"] is False
    assert output["territory_to_economic_twin_bound"] is False
    assert output["newsjack_upstream_skills_invoked_by_this_bridge"] is False
    assert "example.org" not in json.dumps(output)
    assert "Fictional solar" not in json.dumps(output)
    assert output["marketing_or_pr_execution_authorized"] is False


def test_newsjack_upstream_owner_invocation_claim_cannot_unlock_actions():
    from empire_os.predictive_real_world_newsjack import review_existing_jev_newsjack_handoff
    packet=jev_owner_review()
    packet["newsjack_installed_or_invoked"]=True
    result=review_existing_jev_newsjack_handoff(packet,as_of=NOW)
    assert result["status"]=="JEV_NEWSJACK_SOURCE_RESEARCH_REVIEWED"
    assert result["newsjack_upstream_skills_invoked_by_this_bridge"] is False
    assert result["marketing_or_pr_execution_authorized"] is False


@pytest.mark.parametrize("field,value",[
    ("publishing_enabled",True),("outbound_enabled",True),
    ("payment_enabled",True),("execution_authority","send"),
])
def test_jev_owner_packet_cannot_grant_autopublishing(field,value):
    from empire_os.predictive_real_world_newsjack import review_existing_jev_newsjack_handoff
    packet=jev_owner_review()
    packet[field]=value
    r=review_existing_jev_newsjack_handoff(packet,as_of=NOW)
    assert r["status"]=="JEV_NEWSJACK_OWNER_PACKET_HOLD"


@pytest.mark.parametrize("field,value",[
    ("execution_authority","publish"),("publishing_enabled",True),
    ("actual_revenue",True),("actual_visitors",100),
    ("actual_enquiries",1),("evidence_fingerprint","not-sha"),
    ("sector","private@buyer.example"),("market","FR"),
    ("publication_precision","unknown"),
])
def test_jev_candidate_commercial_or_source_tampering_holds(field,value):
    from empire_os.predictive_real_world_newsjack import review_existing_jev_newsjack_handoff
    packet=jev_owner_review()
    packet["candidates"][0][field]=value
    r=review_existing_jev_newsjack_handoff(packet,as_of=NOW)
    assert r["status"]=="JEV_NEWSJACK_OWNER_PACKET_HOLD"
    assert r["national_scope_research_cards"]==[]


def test_jev_owner_count_and_stale_source_holds():
    from empire_os.predictive_real_world_newsjack import review_existing_jev_newsjack_handoff
    packet=jev_owner_review()
    packet["status_counts"]={"CONTENT_BRIEF_REVIEW":1}
    r=review_existing_jev_newsjack_handoff(packet,as_of=NOW)
    assert r["hold_code"]=="JEV_OWNER_STATUS_COUNTS_CONFLICT"
    packet=jev_owner_review()
    packet["candidates"][0]["published_at"]=(NOW-timedelta(days=9)).isoformat()
    r=review_existing_jev_newsjack_handoff(packet,as_of=NOW)
    assert r["hold_code"]=="JEV_OWNER_SOURCE_EVIDENCE_HOLD"
