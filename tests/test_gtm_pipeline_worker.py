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
    assert payload["p_subject"]
    assert "unlock" not in payload["p_body_text"].lower()
    assert POSTAL_ADDRESS in payload["p_body_text"]
    assert "opt out" in payload["p_body_text"].lower()
    assert "Kihle Roofing" in payload["p_body_text"]
    assert "generic lead pitch" not in payload["p_body_text"]
    import hashlib, json
    expected_copy_id = 'copy-sha256:' + hashlib.sha256(json.dumps(
        {'subject': payload['p_subject'], 'body': payload['p_body_text']},
        sort_keys=True, ensure_ascii=False,
    ).encode('utf-8')).hexdigest()
    assert payload['p_metadata']['copy_draft_id'] == expected_copy_id
    assert payload["p_metadata"]["conversation_quality"] == "v2"
    assert payload["p_metadata"]["message_optimizer_version"] == "v1"
    assert payload["p_metadata"]["subject_variants"]
    assert payload["p_metadata"]["message_quality_review"]["score"] >= 70
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.intents_proposed == 1
    assert result.proposal_errors == ()
    proposal = next(
        payload
        for method, path, payload in calls
        if path.endswith("propose_reviewed_outbound_intent")
    )
    assert proposal["p_subject"]
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
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
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    assert approved_calls == [first]
    assert result.candidate_auto_approved == 1
    assert result.candidate_skipped == 1


def test_adaptive_payload_records_selected_subject_and_body_arms():
    snapshot = {
        "segments": {
            "__global__": {
                "delivered": 0,
                "subject_arms": {},
                "body_arms": {},
            }
        }
    }
    payload = build_outbound_payload(
        review(),
        now=NOW,
        optimizer_snapshot=snapshot,
    )
    adaptive = payload["p_metadata"]["adaptive_outreach"]
    assert adaptive["subject_arm"] in {
        "company_only",
        "company_question",
        "one_thing",
        "territory_company",
        "company_topic",
        "quick_question",
        "commercial_signals",
        "territory_topic",
    }
    assert adaptive["body_arm"] in {
        "plain_one_page",
        "direct_observation",
        "simple_question",
    }
    assert adaptive["subject_selection"]["mode"] == "balanced_learning"
    assert adaptive["body_selection"]["mode"] == "balanced_learning"
    assert payload["p_metadata"]["message_optimizer_version"] == "adaptive_v1"
    assert payload["p_metadata"]["message_quality_review"]["score"] >= 80
    assert POSTAL_ADDRESS in payload["p_body_text"]
    assert "opt out" in payload["p_body_text"].lower()


def test_adaptive_payload_records_human_arm_attribution():
    payload = build_outbound_payload(
        review(),
        now=NOW,
        optimizer_snapshot={},
    )
    meta = payload["p_metadata"]
    adaptive = meta["adaptive_outreach"]
    assert meta["message_optimizer_version"] == "adaptive_v1"
    assert adaptive["subject_arm"]
    assert adaptive["body_arm"]
    assert adaptive["copy_policy"] == "human_plain_specific_v1"
    assert adaptive["ai_slop_allowed"] is False
    assert meta["message_quality_review"]["experiment_eligible"] is True
    lowered = payload["p_body_text"].lower()
    assert not any(term in lowered for term in (
        "unlock", "leverage", "game-changing", "ai-powered",
        "cutting-edge", "revolutionary",
    ))


def test_pipeline_prioritizes_fresh_reviews_and_excludes_stale_backlog():
    seen_paths = []

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            seen_paths.append(path)
            if "status=eq.approved" in path:
                return []
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(
        request,
        now=NOW,
    )

    assert result.pending_seen == 0
    pending_path = next(
        path for path in seen_paths
        if "status=eq.pending" in path
    )
    assert "order=proposed_at.desc" in pending_path
    assert "proposed_at=gte." in pending_path
    assert "2026-09-14T16%3A00%3A00%2B00%3A00" in pending_path


def test_pipeline_only_uses_fresh_approved_contacts_as_duplicate_blockers():
    seen_paths = []

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            seen_paths.append(path)
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        raise AssertionError((method, path))

    run_gtm_pipeline(request, now=NOW)

    approved_path = next(
        path for path in seen_paths
        if "status=eq.approved" in path
    )
    assert "reviewed_at=gte." in approved_path
    assert "order=reviewed_at.desc" in approved_path
    assert "2026-09-14T16%3A00%3A00%2B00%3A00" in approved_path


def test_offer_outside_standing_authority_is_routed_to_founder_review():
    review = {
        "id": "review-1",
        "prospect_id": "prospect-1",
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@example.com",
        "offer_key": "predictive_revenue_diagnostic",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if path.endswith("auto_review_buyer_candidate"):
            raise RuntimeError("offer outside standing authority")
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.candidate_skipped == 1
    assert len(result.founder_review_required) == 1
    row = result.founder_review_required[0]
    assert row["review_id"] == "review-1"
    assert row["offer_key"] == "predictive_revenue_diagnostic"
    assert row["founder_gate_required"] is True
    assert row["outbound_authorized"] is False
    assert not any(
        "offer outside standing authority" in reason
        for reason in result.deferred_reasons
    )


def test_legacy_software_mrr_founder_review_is_product_bound():
    review = {
        "id": "review-mrr",
        "prospect_id": "prospect-mrr",
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@example.com",
        "offer_key": "software_mrr",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if path.endswith("auto_review_buyer_candidate"):
            raise RuntimeError("offer outside standing authority")
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)
    row = result.founder_review_required[0]
    assert row["source_offer_key"] == "software_mrr"
    assert row["offer_key"] == "search_growth_command"


def test_founder_review_excludes_prior_outbound_history():
    review = {
        "id": "review-history",
        "prospect_id": "prospect-history",
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@example.com",
        "offer_key": "predictive_revenue_diagnostic",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if path.endswith("auto_review_buyer_candidate"):
            raise RuntimeError("offer outside standing authority")
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            if "prospect_id=eq.prospect-history" in path:
                return [{"id": "intent-1", "status": "delivered"}]
            return []
        if method == "GET" and path.startswith("/rest/v1/outbound_suppressions?"):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.founder_review_required == ()
    assert any(
        "prior_outbound_history" in reason
        for reason in result.deferred_reasons
    )


def test_founder_review_history_guard_fails_closed():
    review = {
        "id": "review-guard",
        "prospect_id": "prospect-guard",
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@example.com",
        "offer_key": "predictive_revenue_diagnostic",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if path.endswith("auto_review_buyer_candidate"):
            raise RuntimeError("offer outside standing authority")
        if method == "GET" and path.startswith("/rest/v1/outbound_intents?"):
            raise RuntimeError("history unavailable")
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    import pytest

    with pytest.raises(RuntimeError, match="history unavailable"):
        run_gtm_pipeline(request, now=NOW)


def test_prior_outbound_history_excludes_founder_review_candidate():
    review = {
        "id": "review-redwood",
        "prospect_id": "prospect-redwood",
        "contact_name": "Richard Lewis",
        "contact_title": "Chief Executive Officer & Founder",
        "contact_email": "richard@redwoodservices.com",
        "offer_key": "predictive_revenue_intelligence_os",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if method == "GET" and path.startswith(
            "/rest/v1/outbound_intents?"
        ):
            return [{
                "prospect_id": "prospect-redwood",
                "normalized_recipient": "richard@redwoodservices.com",
                "status": "delivered",
            }]
        if method == "GET" and path.startswith(
            "/rest/v1/outbound_suppressions?"
        ):
            return []
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.candidate_skipped == 1
    assert result.founder_review_required == ()
    assert any(
        "prior_outbound_history" in reason
        for reason in result.deferred_reasons
    )


def test_suppressed_contact_excluded_before_founder_review():
    review = {
        "id": "review-suppressed",
        "prospect_id": "prospect-suppressed",
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_email": "jane@example.com",
        "offer_key": "search_growth_command",
        "company_score": 90,
        "decision_score": 1.0,
        "proposed_at": NOW.isoformat(),
    }

    def request(method, path, payload=None, **_kwargs):
        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            if "status=eq.pending" in path:
                return [review]
            return []
        if method == "GET" and path.startswith(
            "/rest/v1/outbound_intents?"
        ):
            return []
        if method == "GET" and path.startswith(
            "/rest/v1/outbound_suppressions?"
        ):
            return [{"normalized_contact": "jane@example.com"}]
        if path.endswith("list_buyer_reviews_for_outbound"):
            return []
        raise AssertionError((method, path))

    result = run_gtm_pipeline(request, now=NOW)

    assert result.candidate_skipped == 1
    assert result.founder_review_required == ()
    assert any(
        "suppressed_contact" in reason
        for reason in result.deferred_reasons
    )

def test_safety_lookup_failure_prevents_all_gtm_mutations():
    import pytest

    for blocked in ("outbound_intents", "outbound_suppressions"):
        calls = []

        def request(method, path, payload=None, **_kwargs):
            calls.append((method, path))
            if method == "POST":
                raise AssertionError("unsafe mutation attempted")
            if path.startswith("/rest/v1/buyer_candidate_reviews?"):
                return []
            if blocked in path:
                raise RuntimeError("safety lookup unavailable")
            if "outbound_intents" in path or "outbound_suppressions" in path:
                return []
            raise AssertionError(path)

        with pytest.raises(RuntimeError, match="safety lookup unavailable"):
            run_gtm_pipeline(request, now=NOW)
        assert not any(method == "POST" for method, _ in calls)


def test_invalid_safety_projection_prevents_all_gtm_mutations():
    import pytest

    for blocked in ("outbound_intents", "outbound_suppressions"):
        calls = []

        def request(method, path, payload=None, **_kwargs):
            calls.append((method, path))
            if method == "POST":
                raise AssertionError("unsafe mutation attempted")
            if path.startswith("/rest/v1/buyer_candidate_reviews?"):
                return []
            if blocked in path:
                return None
            if "outbound_intents" in path or "outbound_suppressions" in path:
                return []
            raise AssertionError(path)

        with pytest.raises(ValueError, match="invalid projection"):
            run_gtm_pipeline(request, now=NOW)
        assert not any(method == "POST" for method, _ in calls)


def test_safety_projections_at_limit_fail_closed():
    import pytest

    for table, count in (("outbound_intents", 1000), ("outbound_suppressions", 5000)):
        writes = []

        def request(method, path, payload=None, **kwargs):
            if method == "GET" and "buyer_candidate_reviews" in path:
                return []
            if method == "GET" and "outbound_intents" in path:
                return [{}] * count if table == "outbound_intents" else []
            if method == "GET" and "outbound_suppressions" in path:
                return [{}] * count if table == "outbound_suppressions" else []
            writes.append((method, path))
            raise AssertionError("mutation attempted")

        with pytest.raises(ValueError, match="safety pagination repeated page"):
            run_gtm_pipeline(request, now=NOW)
        assert writes == []


def test_founder_history_helper_rejects_invalid_projection():
    import pytest
    from empire_os.gtm_pipeline_worker import _founder_review_has_prior_contact

    def request(method, path, **kwargs):
        return None

    with pytest.raises(ValueError, match="invalid projection"):
        _founder_review_has_prior_contact(
            request, prospect_id="prospect-1", contact_email="person@example.com"
        )


def test_approved_review_history_limit_fails_closed():
    import pytest
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path))
        if method == "GET" and "buyer_candidate_reviews" in path:
            if "status=eq.approved" in path:
                return [{"contact_email": "person@example.com"}] * 100
            return []
        raise AssertionError("should not continue after incomplete approved history")

    with pytest.raises(ValueError, match="safety pagination repeated page"):
        run_gtm_pipeline(request, now=NOW)
    assert all(method == "GET" for method, _ in calls)


def test_founder_history_requires_contact_identity():
    import pytest
    from empire_os.gtm_pipeline_worker import _founder_review_has_prior_contact

    with pytest.raises(ValueError, match="requires prospect or contact"):
        _founder_review_has_prior_contact(
            lambda *args, **kwargs: [], prospect_id=None, contact_email=None
        )


def test_missing_review_projection_fails_closed():
    import pytest
    for missing_status in ("pending", "approved"):
        calls = []

        def request(method, path, payload=None, **kwargs):
            calls.append((method, path))
            if method == "GET" and "buyer_candidate_reviews" in path:
                if f"status=eq.{missing_status}" in path:
                    return None
                return []
            raise AssertionError("unsafe downstream operation")

        with pytest.raises(ValueError, match="(review projection must be a list|invalid projection)"):
            run_gtm_pipeline(request, now=NOW)
        assert all(method == "GET" for method, _ in calls)


def test_safety_pagination_reads_beyond_first_page():
    from empire_os.gtm_pipeline_worker import _complete_safety_projection
    from urllib.parse import parse_qs, urlsplit

    offsets = []

    def request(method, path, **kwargs):
        query = parse_qs(urlsplit(path).query)
        offset = int(query["offset"][0])
        offsets.append(offset)
        return [{"normalized_contact": f"contact{n}@example.com"}
                for n in range(offset, min(offset + 2, 5))]

    rows = _complete_safety_projection(
        request, "outbound_suppressions", {"select": "normalized_contact"},
        page_size=2,
    )
    assert len(rows) == 5
    assert offsets == [0, 2, 4]
    assert rows[-1]["normalized_contact"] == "contact4@example.com"
