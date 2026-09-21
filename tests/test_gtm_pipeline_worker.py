from datetime import datetime, timezone

from empire_os.gtm_pipeline_worker import (
    POSTAL_ADDRESS,
    build_outbound_payload,
    run_gtm_pipeline,
)


NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def review(review_id="00000000-0000-0000-0000-000000000001"):
    return {
        "id": review_id,
        "contact_name": "Clay Winter",
        "contact_email": "clay@example.com",
        "offer_key": "managed_service",
        "evidence": {
            "business_name": "Kihle Roofing",
            "niche": "roofing",
            "metro": "Wichita",
            "review_ready": True,
            "outreach_ready": True,
            "rating": 4.8,
            "review_count": 116,
        },
    }


def test_build_outbound_payload_is_compliant_and_evidence_safe():
    payload = build_outbound_payload(review(), now=NOW)
    assert payload["p_subject"] == "Clay — one thing I noticed in Wichita"
    assert POSTAL_ADDRESS in payload["p_body_text"]
    assert "opt out" in payload["p_body_text"].lower()
    assert "Kihle Roofing" in payload["p_body_text"]
    assert "generic lead pitch" in payload["p_body_text"]
    assert payload["p_metadata"]["conversation_quality"] == "v2"
    assert "revenue" not in payload["p_metadata"]
    assert payload["p_proposed_by"] == "empire_gtm_agent_v1"
    assert payload["p_expires_at"].startswith("2026-09-23T16:00:00")


def test_pipeline_auto_reviews_then_proposes_only_ready_reviews():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if method == "GET" and path.startswith("/rest/v1/buyer_candidate_reviews?"):
            return [{"id": "00000000-0000-0000-0000-000000000010"}]
        if path.endswith("auto_review_buyer_candidate"):
            return {
                "decision": "approved",
                "status": "approved",
                "review_id": payload["p_review_id"],
            }
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [review("00000000-0000-0000-0000-000000000010")]
        if path.endswith("propose_reviewed_outbound_intent"):
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000020",
            }
        raise AssertionError((method, path))

    result = run_gtm_pipeline(
        request,
        limit=10,
        daily_cap=10,
        now=NOW,
    )
    assert result.pending_seen == 1
    assert result.candidate_auto_approved == 1
    assert result.intents_proposed == 1
    assert result.proposal_errors == ()
    proposal = calls[-1][2]
    assert proposal["p_review_id"] == (
        "00000000-0000-0000-0000-000000000010"
    )
    assert POSTAL_ADDRESS in proposal["p_body_text"]


def test_pipeline_skips_ineligible_review_without_fabricating_evidence():
    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith("/rest/v1/buyer_candidate_reviews?"):
            return [{"id": "00000000-0000-0000-0000-000000000010"}]
        if path.endswith("auto_review_buyer_candidate"):
            raise RuntimeError("verified decision-maker contact evidence required")
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert result.pending_seen == 1
    assert result.candidate_auto_approved == 0
    assert result.candidate_skipped == 1
    assert result.intents_proposed == 0
    assert result.proposal_errors == ()


def test_build_outbound_payload_rejects_placeholder_context():
    broken = review()
    broken["evidence"] = {
        "review_ready": True,
        "outreach_ready": True,
    }

    try:
        build_outbound_payload(broken, now=NOW)
    except ValueError as exc:
        assert "outbound personalization evidence missing" in str(exc)
    else:
        raise AssertionError("missing personalization must fail closed")


def test_pipeline_hydrates_missing_context_from_canonical_prospect():
    calls = []
    review_id = "00000000-0000-0000-0000-000000000030"
    prospect_id = "00000000-0000-0000-0000-000000000031"

    incomplete = {
        "id": review_id,
        "prospect_id": prospect_id,
        "contact_name": "Dave Smith",
        "contact_email": "dave@example.com",
        "offer_key": "managed_service",
        "evidence": {
            "review_ready": True,
            "outreach_ready": True,
            "rating": 4.8,
            "review_count": 116,
        },
    }

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [incomplete]
        if method == "GET" and path.startswith("/rest/v1/prospects?"):
            return [{
                "business_name": "SewerTV Hydro Jetting and Plumbing",
                "niche": "plumbing",
                "metro": "san antonio, tx",
                "rating": 4.9,
                "review_count": 87,
                "buy_signal_score": 95,
                "runs_ads": None,
            }]
        if path.endswith("propose_reviewed_outbound_intent"):
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000032",
            }
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.intents_proposed == 1
    assert result.proposal_errors == ()
    proposal = next(
        payload
        for method, path, payload in calls
        if path.endswith("propose_reviewed_outbound_intent")
    )
    assert proposal["p_subject"] == (
        "Dave — one thing I noticed in san antonio, tx"
    )
    assert "SewerTV Hydro Jetting and Plumbing" in proposal["p_body_text"]
    assert "4.9★ across 87 reviews" in proposal["p_body_text"]
    assert "your team" not in proposal["p_body_text"]
    assert "your market" not in proposal["p_body_text"]


def test_pipeline_skips_when_canonical_context_cannot_be_resolved():
    review_id = "00000000-0000-0000-0000-000000000040"
    prospect_id = "00000000-0000-0000-0000-000000000041"

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [{
                "id": review_id,
                "prospect_id": prospect_id,
                "contact_name": "Alex Smith",
                "contact_email": "alex@example.com",
                "offer_key": "managed_service",
                "evidence": {
                    "review_ready": True,
                    "outreach_ready": True,
                },
            }]
        if method == "GET" and path.startswith("/rest/v1/prospects?"):
            return []
        if path.endswith("propose_reviewed_outbound_intent"):
            raise AssertionError("unresolved context must not be proposed")
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.intents_proposed == 0
    assert len(result.proposal_errors) == 1
    assert "outbound personalization evidence missing" in (
        result.proposal_errors[0]
    )
