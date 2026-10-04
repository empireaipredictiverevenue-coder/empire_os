from datetime import datetime, timezone

from empire_os.linkedin_revenue_department import (
    build_linkedin_revenue_department_from_scout_snapshot,
    build_linkedin_revenue_department_snapshot,
    build_linkedin_revenue_opportunity,
    refresh_linkedin_revenue_department,
    scout_candidate_to_linkedin_record,
)


NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _person(*, verified: bool = True) -> dict:
    return {
        "person_id": "person-1",
        "name": "Jane Doe",
        "title": "Chief Revenue Officer",
        "decision_role": "economic_buyer",
        "contact_verified": verified,
        "evidence_ref": "public-profile:person-1",
    }


def _signal(summary: str = "Hiring four SDRs after a new market expansion") -> dict:
    return {
        "signal_type": "hiring_growth",
        "summary": summary,
        "observed_at": "2026-10-03T12:00:00Z",
        "evidence_ref": "public-job-posting:123",
        "source": "public_web",
        "confidence": 0.95,
    }


def test_unknown_evidence_fails_closed_without_outreach_authority():
    row = build_linkedin_revenue_opportunity(
        {
            "business_name": "Acme Ltd",
            "description": "Professional services.",
            "first_party_people": [],
            "signals": [],
        },
        now=NOW,
    )

    assert row["stage_04_buying_signals"]["state"] == "UNKNOWN"
    assert row["stage_06_personalised_outreach"]["draft"] is None
    assert row["review_readiness"]["ready_for_human_review"] is False
    assert "decision_maker_unresolved" in row["review_readiness"]["blockers"]
    assert "buying_signal_unknown" in row["review_readiness"]["blockers"]
    assert row["review_readiness"]["outreach_authorized"] is False
    assert row["truth_contract"]["synthetic_data_allowed"] is False


def test_evidenced_signal_and_verified_person_produce_review_only_draft():
    row = build_linkedin_revenue_opportunity(
        {
            "business_name": "Northwind Labs",
            "description": "B2B SaaS expanding into a new market and hiring SDRs.",
            "source_evidence_ref": "company-site:northwind",
            "first_party_people": [_person()],
            "signals": [_signal()],
            "target_buyer_pools": ["software_and_advisory_buyers"],
            "target_product_codes": ["predictive_revenue_intelligence_os"],
        },
        now=NOW,
    )

    assert row["stage_03_decision_makers"]["primary"]["name"] == "Jane Doe"
    assert row["stage_04_buying_signals"]["observed_signal_count"] == 1
    draft = row["stage_06_personalised_outreach"]["draft"]
    assert draft is not None
    assert draft["send_enabled"] is False
    assert draft["invented_claims"] is False
    assert row["review_readiness"]["ready_for_human_review"] is True
    assert row["review_readiness"]["outreach_authorized"] is False


def test_future_or_unevidenced_signals_are_not_promoted():
    row = build_linkedin_revenue_opportunity(
        {
            "business_name": "Future Corp",
            "first_party_people": [_person()],
            "signals": [
                {
                    "signal_type": "funding",
                    "summary": "Raised a round",
                    "observed_at": "2026-10-05T12:00:00Z",
                    "evidence_ref": "public-news:future",
                },
                {
                    "signal_type": "hiring",
                    "summary": "Hiring sales",
                    "observed_at": "2026-10-03T12:00:00Z",
                },
            ],
        },
        now=NOW,
    )

    assert row["stage_04_buying_signals"]["observed_signal_count"] == 0
    assert row["stage_04_buying_signals"]["state"] == "UNKNOWN"
    assert "buying_signal_unknown" in row["review_readiness"]["blockers"]


def test_suppression_and_unsubscribe_force_stop_recommendation():
    row = build_linkedin_revenue_opportunity(
        {
            "business_name": "Stop Corp",
            "first_party_people": [_person()],
            "signals": [_signal()],
            "suppressed": True,
            "reply_text": "Please opt out and do not contact me.",
        },
        now=NOW,
    )

    assert row["stage_09_replies"]["classification"] == "unsubscribe"
    assert row["stage_08_follow_up"]["sequence"]["recommended_action"] == "STOP_SUPPRESSED"
    assert "suppressed" in row["review_readiness"]["blockers"]
    assert row["stage_08_follow_up"]["sequence"]["message_send_enabled"] is False


def test_snapshot_prefers_available_expected_revenue_value():
    base = {
        "description": "Home services platform expanding and hiring.",
        "source_evidence_ref": "company-site:verified",
        "first_party_people": [_person()],
        "signals": [_signal()],
    }
    complete_economics = {
        "probability_close": 0.4,
        "probability_payment_given_close": 0.95,
        "probability_fulfilment_given_payment": 0.9,
        "ltv_cents": 1000000,
        "margin_factor": 0.8,
        "capacity_factor": 1.0,
        "recency_factor": 0.9,
        "confidence": 0.8,
        "time_discount_factor": 0.95,
        "acquisition_cost_cents": 10000,
        "fulfilment_cost_cents": 50000,
        "risk_cost_cents": 10000,
    }

    result = build_linkedin_revenue_department_snapshot(
        [
            {
                **base,
                "business_name": "Unknown Economics Co",
                "economic_inputs": {},
            },
            {
                **base,
                "business_name": "Known Economics Co",
                "economic_inputs": complete_economics,
            },
        ],
        now=NOW,
    )

    assert result["candidate_count"] == 2
    assert result["items"][0]["account"]["business_name"] == "Known Economics Co"
    assert result["items"][0]["stage_05_priority"][
        "expected_revenue_value"
    ]["status"] == "AVAILABLE"
    assert result["items"][0]["stage_05_priority"][
        "new_revenue_scoring_model_introduced"
    ] is False
    assert result["live_outbound_enabled"] is False


def test_scout_candidate_with_canonical_opportunity_value_outranks_equivalent_without_economics():
    scout = {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "generated_at": "2026-10-03T12:00:00Z",
        "candidates": [
            {
                "business_name": "A No Economics Co",
                "website": "https://no-economics.example",
                "description": "Home services platform expanding and hiring.",
                "observed_buying_triggers": ["expansion"],
                "first_party_people": [{
                    **_person(),
                    "evidence_ref": "https://no-economics.example/team",
                }],
            },
            {
                "business_name": "Z Canonical Value Co",
                "website": "https://canonical-value.example",
                "description": "Home services platform expanding and hiring.",
                "observed_buying_triggers": ["expansion"],
                "first_party_people": [{
                    **_person(),
                    "evidence_ref": "https://canonical-value.example/team",
                }],
                "target_opportunity_keys": ["opp-high-value"],
            },
        ],
    }
    opportunity_value = {
        "schema_version": "empire.opportunity_value.snapshot.v1",
        "items": [{
            "opportunity_key": "opp-high-value",
            "status": "AVAILABLE",
            "rank": 1,
            "expected_revenue_cents": 2500000,
            "expected_cost_cents": 500000,
            "expected_gross_profit_cents": 2000000,
            "risk_adjusted_score": 0.91,
            "confidence": 0.88,
        }],
    }

    result = build_linkedin_revenue_department_from_scout_snapshot(
        scout,
        opportunity_value_snapshot=opportunity_value,
        now=NOW,
    )

    assert result["candidate_count"] == 2
    assert result["canonical_opportunity_value_available_count"] == 1
    assert result["items"][0]["account"]["business_name"] == (
        "Z Canonical Value Co"
    )
    priority = result["items"][0]["stage_05_priority"]
    assert priority["ranking_basis"] == (
        "canonical_opportunity_risk_adjusted_value_then_fit"
    )
    assert priority["top_canonical_opportunity_value"][
        "opportunity_key"
    ] == "opp-high-value"
    assert priority["top_canonical_opportunity_value"][
        "risk_adjusted_score"
    ] == 0.91
    assert result["items"][1]["account"]["business_name"] == (
        "A No Economics Co"
    )


def test_content_brief_is_evidence_only_and_does_not_post():
    row = build_linkedin_revenue_opportunity(
        {
            "business_name": "Signal Co",
            "first_party_people": [_person()],
            "signals": [_signal("Opened a new office in Manchester")],
        },
        now=NOW,
    )

    content = row["stage_07_linkedin_content"]
    assert content["observed_signal_themes"] == ["hiring_growth"]
    assert content["evidence"][0]["summary"] == "Opened a new office in Manchester"
    assert content["invented_claims"] is False
    assert content["post_enabled"] is False





def test_scout_adapter_preserves_unverified_contact_candidates():
    record = scout_candidate_to_linkedin_record(
        {
            "business_name": "Buyer Exchange",
            "website": "https://buyer.example",
            "first_party_emails": ["jane@buyer.example"],
            "first_party_phones": ["+15125550123"],
            "first_party_people": [{
                "name": "Jane Smith",
                "title": "CEO",
            }],
        },
        observed_at="2026-10-03T12:00:00+00:00",
    )

    assert record["first_party_people"] == []
    assert record["contact_candidates"] == [
        {
            "kind": "email",
            "value": "jane@buyer.example",
            "evidence_ref": "https://buyer.example",
        },
        {
            "kind": "phone",
            "value": "+15125550123",
            "evidence_ref": "https://buyer.example",
        },
    ]

    row = build_linkedin_revenue_opportunity(record, now=NOW)
    stage = row["stage_03_decision_makers"]
    assert stage["primary"] is None
    assert stage["resolution_state"] == (
        "OBSERVED_CANDIDATE_REQUIRES_VERIFICATION"
    )
    assert stage["observed_unverified_candidates"][0]["name"] == "Jane Smith"
    assert stage["observed_contact_candidates"][0]["verification_state"] == (
        "OBSERVED_UNVERIFIED"
    )
    assert row["review_readiness"]["recommended_next_research_action"] == (
        "verify_observed_decision_maker"
    )
    assert row["review_readiness"]["outreach_authorized"] is False

def test_scout_adapter_uses_observed_site_trigger_without_inventing_people():
    record = scout_candidate_to_linkedin_record(
        {
            "business_name": "Northwind Labs",
            "website": "https://northwind.example",
            "description": "Expanding sales team.",
            "observed_buying_triggers": ["hiring"],
            "first_party_people": [
                {"name": "Unresolved Person", "title": "VP Sales"}
            ],
            "target_icp_profile_keys": [
                "predictive_revenue_home_services_platform"
            ],
        },
        observed_at="2026-10-03T12:00:00+00:00",
    )

    assert record["signals"] == [{
        "signal_type": "public_buying_trigger_term",
        "summary": "Observed public trigger term: hiring",
        "observed_at": "2026-10-03T12:00:00+00:00",
        "evidence_ref": "https://northwind.example",
        "source": "buyer_acquisition_scout_first_party_site",
        "confidence": None,
    }]
    assert record["first_party_people"] == []
    assert record["observed_people_candidates"] == [{
        "name": "Unresolved Person",
        "title": "VP Sales",
        "evidence_ref": "https://northwind.example",
    }]
    assert record["source_evidence_ref"] == "https://northwind.example"


def test_scout_snapshot_projects_into_nine_stage_review_lane():
    scout = {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "generated_at": "2026-10-03T12:00:00Z",
        "candidates": [{
            "business_name": "Northwind Labs",
            "website": "https://northwind.example",
            "description": "Home services platform expanding and hiring.",
            "buyer_type": "qualified_end_buyer",
            "target_buyer_pools": ["enterprise_and_data_buyers"],
            "target_product_codes": [
                "predictive_revenue_intelligence_os"
            ],
            "target_icp_profile_keys": [
                "predictive_revenue_home_services_platform"
            ],
            "observed_buying_triggers": ["expansion", "hiring"],
            "first_party_people": [{
                **_person(),
                "evidence_ref": "https://northwind.example/team",
            }],
            "query_evidence_count": 3,
            "candidate_state": "RESEARCH_EVIDENCE_ONLY",
            "canonical_identity_verified": False,
            "commercial_terms_verified": False,
        }],
    }

    result = build_linkedin_revenue_department_from_scout_snapshot(
        scout,
        now=NOW,
    )

    assert result["source"] == "buyer_acquisition_scout"
    assert result["candidate_count"] == 1
    assert result["observed_signal_candidate_count"] == 1
    assert result["resolved_decision_maker_count"] == 1
    assert result["verified_contact_count"] == 1
    assert result["outreach_draft_count"] == 1
    assert result["human_review_ready_count"] == 1
    assert result["live_outbound_enabled"] is False
    assert result["database_write_performed"] is False
    assert result["content_posted"] is False


def test_scout_future_snapshot_does_not_create_observed_signal_time():
    result = build_linkedin_revenue_department_from_scout_snapshot(
        {
            "schema_version": "empire.buyer_acquisition_scout.v1",
            "generated_at": "2026-10-05T12:00:00Z",
            "candidates": [{
                "business_name": "Future Signal Co",
                "website": "https://future.example",
                "observed_buying_triggers": ["funding"],
                "first_party_people": [_person()],
            }],
        },
        now=NOW,
    )

    assert result["source_snapshot_fresh_enough_for_signal_time"] is False
    assert result["observed_signal_candidate_count"] == 0
    assert "buying_signal_unknown" in result["items"][0][
        "review_readiness"
    ]["blockers"]


def test_refresh_writes_runtime_snapshot_without_database_or_outbound(tmp_path):
    source = tmp_path / "runtime/buyer_acquisition/scout_latest.json"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
{
  "schema_version": "empire.buyer_acquisition_scout.v1",
  "generated_at": "2026-10-03T12:00:00Z",
  "candidates": [
    {
      "business_name": "Evidence Co",
      "website": "https://evidence.example",
      "observed_buying_triggers": ["expansion"]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = refresh_linkedin_revenue_department(tmp_path)
    output = (
        tmp_path
        / "runtime/buyer_acquisition/linkedin_revenue_department_latest.json"
    )

    assert output.exists()
    assert result["candidate_count"] == 1
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"



def test_scout_intent_seed_becomes_linkedin_why_now_evidence():
    scout = {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "generated_at": "2026-10-04T08:30:00Z",
        "candidates": [{
            "business_name": "Intent Roof LLC",
            "website": "https://intent-roof.example",
            "description": "Roofing and siding contractor.",
            "discovery_source": "community_intent_seed",
            "intent_signal_id": "sig-roof-1",
            "intent_score": 86,
            "intent_band": "high",
            "intent_observed_at": "2026-10-04T08:00:00Z",
            "intent_pain_points": ["lead_generation", "revenue_growth"],
            "intent_evidence_url": (
                "https://reddit.com/r/Roofing/comments/example"
            ),
            "intent_summary": (
                "Need more qualified appointments; Google Ads has not "
                "been consistently profitable."
            ),
            "first_party_people": [{
                **_person(),
                "evidence_ref": "https://intent-roof.example/about",
            }],
            "first_party_emails": ["owner@intent-roof.example"],
            "target_icp_profile_keys": [
                "intent_driven_home_service_growth"
            ],
            "target_product_codes": ["managed_service"],
            "target_buyer_pools": ["local_and_smb_buyers"],
            "observed_buying_triggers": [],
            "candidate_state": "RESEARCH_EVIDENCE_ONLY",
        }],
    }

    result = build_linkedin_revenue_department_from_scout_snapshot(
        scout,
        now=NOW,
    )

    assert result["candidate_count"] == 1
    row = result["items"][0]
    signals = row["stage_04_buying_signals"]["signals"]
    assert signals[0]["signal_type"] == "public_intent_signal"
    assert signals[0]["evidence_ref"] == (
        "https://reddit.com/r/Roofing/comments/example"
    )
    assert row["stage_06_personalised_outreach"]["reason_now"] == (
        "Need more qualified appointments; Google Ads has not "
        "been consistently profitable."
    )
    assert row["review_readiness"]["ready_for_human_review"] is True
    assert row["review_readiness"]["outreach_authorized"] is False
