from datetime import datetime, timezone

from empire_os.linkedin_revenue_department import (
    build_linkedin_revenue_department_snapshot,
    build_linkedin_revenue_opportunity,
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
