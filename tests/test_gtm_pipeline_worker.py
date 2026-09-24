from datetime import datetime, timezone

from empire_os.gtm_pipeline_worker import (
    _hydrate_review_evidence,
    POSTAL_ADDRESS,
    build_outbound_payload,
    run_gtm_pipeline,
)


NOW = datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc)


def review(review_id="00000000-0000-0000-0000-000000000001"):
    return {
        "id": review_id,
        "contact_name": "Clay Winter",
        "contact_email": "clay@example.com",
        "offer_key": "managed_service",
        "evidence": {
            "business_name": "Kihle Roofing",
            "niche": "roofing",
            "metro": "Wichita, KS",
            "review_ready": True,
            "outreach_ready": True,
            "rating": 4.8,
            "review_count": 116,
        },
    }


def test_build_outbound_payload_is_compliant_and_evidence_safe():
    payload = build_outbound_payload(review(), now=NOW)
    assert payload["p_subject"] == "Clay — one thing I noticed in Wichita, KS"
    assert POSTAL_ADDRESS in payload["p_body_text"]
    assert "opt out" in payload["p_body_text"].lower()
    assert "Kihle Roofing" in payload["p_body_text"]
    assert "generic lead pitch" in payload["p_body_text"]
    assert payload["p_metadata"]["conversation_quality"] == "v2"
    assert "revenue" not in payload["p_metadata"]
    assert payload["p_proposed_by"] == "empire_gtm_agent_v1"
    assert payload["p_expires_at"].startswith("2026-09-24T16:00:00")


def test_pipeline_auto_reviews_then_proposes_only_ready_reviews():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if method == "GET" and path.startswith("/rest/v1/buyer_candidate_reviews?"):
            if "status=eq.approved" in path:
                return []
            return [{
                "id": "00000000-0000-0000-0000-000000000010",
                "contact_email": "clay@example.com",
            }]
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


def test_pipeline_defaults_to_25_daily_review_cap():
    seen_caps = []

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.approved" in path:
                return []
            return [{
                "id": "00000000-0000-0000-0000-000000000099",
                "contact_email": "owner@example.com",
            }]
        if path.endswith("auto_review_buyer_candidate"):
            seen_caps.append(payload["p_daily_cap"])
            return {"status": "approved", "decision": "approved"}
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.candidate_auto_approved == 1
    assert seen_caps == [25]


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
    assert result.outreach_deferred == 1
    assert result.proposal_errors == ()
    assert "outbound personalization evidence missing" in (
        result.deferred_reasons[0]
    )


def test_placeholder_contact_is_deferred_not_proposed():
    calls = []
    bad = review("00000000-0000-0000-0000-000000000050")
    bad["contact_name"] = "Your Referral Program"
    bad["contact_email"] = "your@email.com"

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [bad]
        if path.endswith("propose_reviewed_outbound_intent"):
            raise AssertionError("placeholder contact must never be proposed")
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert result.intents_proposed == 0
    assert result.outreach_deferred == 1
    assert result.proposal_errors == ()
    assert "verified person contact required" in result.deferred_reasons[0]


def test_missing_specific_proof_is_deferred_not_service_error():
    no_proof = review("00000000-0000-0000-0000-000000000051")
    no_proof["evidence"].pop("rating", None)
    no_proof["evidence"].pop("review_count", None)

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [no_proof]
        if path.endswith("propose_reviewed_outbound_intent"):
            raise AssertionError("evidence-poor contact must not be proposed")
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert result.intents_proposed == 0
    assert result.outreach_deferred == 1
    assert result.proposal_errors == ()
    assert "specific outreach evidence required" in result.deferred_reasons[0]



def test_gtm_metadata_carries_recipient_locale_and_local_time():
    payload = build_outbound_payload(review(), now=NOW)
    meta = payload["p_metadata"]
    assert meta["recipient_locale"]["country_code"] == "US"
    assert meta["recipient_locale"]["timezone"] == "America/Chicago"
    assert meta["outreach_language"] == "en-US"
    assert meta["recipient_local_timing"]["eligible"] is True


def test_gtm_defers_when_recipient_is_outside_local_contact_window():
    row = review("00000000-0000-0000-0000-000000000061")

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [row]
        if path.endswith("propose_reviewed_outbound_intent"):
            raise AssertionError("out-of-hours intent must not be proposed")
        raise AssertionError((method, path))

    # 11:00 UTC = 06:00 in Wichita in September.
    result = run_gtm_pipeline(
        request,
        now=datetime(2026, 9, 21, 11, 0, tzinfo=timezone.utc),
    )
    assert result.intents_proposed == 0
    assert result.outreach_deferred == 1
    assert "outside_recipient_local_contact_window" in result.deferred_reasons[0]


def test_gtm_defers_multilingual_country_without_explicit_language():
    row = review("00000000-0000-0000-0000-000000000062")
    row["evidence"]["metro"] = "Toronto, ON"

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return [row]
        if path.endswith("propose_reviewed_outbound_intent"):
            raise AssertionError("language-unresolved intent must not be proposed")
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert result.intents_proposed == 0
    assert result.outreach_deferred == 1
    assert "recipient outreach language unresolved" in result.deferred_reasons[0]


def test_hydrate_review_refreshes_public_proof_even_when_context_complete():
    row = review("00000000-0000-0000-0000-000000000071")
    row["prospect_id"] = "00000000-0000-0000-0000-000000000072"
    row["evidence"].pop("rating", None)
    row["evidence"].pop("review_count", None)

    def request(method, path, payload=None, **_kwargs):
        assert method == "GET"
        assert path.startswith("/rest/v1/prospects?")
        return [{
            "business_name": "Clay Roofing",
            "niche": "roofing",
            "metro": "Wichita, KS",
            "rating": 4.8,
            "review_count": 114,
            "buy_signal_score": 100,
            "runs_ads": False,
        }]

    hydrated = _hydrate_review_evidence(request, row)
    assert hydrated["evidence"]["business_name"] == row["evidence"]["business_name"]
    assert hydrated["evidence"]["rating"] == 4.8
    assert hydrated["evidence"]["review_count"] == 114
    assert hydrated["evidence"]["buy_signal_score"] == 100


def test_pipeline_skips_pending_contact_already_approved():
    pending_id = "00000000-0000-0000-0000-000000000081"
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.approved" in path:
                return [{"contact_email": "same@example.com"}]
            return [{
                "id": pending_id,
                "contact_email": "SAME@example.com",
                "proposed_at": "2026-09-21T18:00:00+00:00",
            }]
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        if path.endswith("auto_review_buyer_candidate"):
            raise AssertionError("duplicate contact must not be auto-reviewed")
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert result.candidate_auto_approved == 0
    assert result.candidate_skipped == 1
    assert any(
        "duplicate_normalized_contact" in reason
        for reason in result.deferred_reasons
    )


def test_pipeline_skips_second_duplicate_pending_contact_same_cycle():
    first = "00000000-0000-0000-0000-000000000091"
    second = "00000000-0000-0000-0000-000000000092"
    approved_calls = []

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.approved" in path:
                return []
            return [
                {"id": first, "contact_email": "victor@example.com"},
                {"id": second, "contact_email": "VICTOR@example.com"},
            ]
        if path.endswith("auto_review_buyer_candidate"):
            approved_calls.append(payload["p_review_id"])
            return {"status": "approved", "decision": "approved"}
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert approved_calls == [first]
    assert result.candidate_auto_approved == 1
    assert result.candidate_skipped == 1
