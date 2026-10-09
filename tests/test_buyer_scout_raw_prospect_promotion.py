from empire_os.buyer_scout_raw_prospect_promotion import (
    run_raw_prospect_promotion,
)


def candidate(**overrides):
    row = {
        "id": "candidate-1",
        "review_state": "review_ready",
        "reconciliation_state": "REVIEW_READY",
    }
    row.update(overrides)
    return row


def test_historical_false_direct_buyer_row_is_ineligible_for_manual_and_acp():
    from empire_os.buyer_claim_provenance import classify_buyer_source_pages
    from scripts.promote_buyer_scout_raw_prospects import _identity_safe_rows
    from empire_os.buyer_scout_raw_prospect_promotion import run_raw_prospect_promotion
    from empire_os.buyer_scout_acp_adapter import eligible_for_acp_admission
    row = candidate(
        id="historical-direct", website="https://buyer.example",
        business_name="Buyer Company", domain="buyer.example",
        target_buyer_pools=["direct_demand_buyers"],
        target_product_codes=["managed_service"],
        explicit_direct_buyer_evidence=True,
        site_evidence={"first_party_people": [{
            "name": "Jane Smith", "title": "CEO",
            "email": "jane@buyer.example", "source": "first_party_site",
            "source_url": "https://buyer.example/team",
            "mx_verified": True, "person_explicitly_named": True,
            "email_directly_bound_to_person": True,
        }]},
    )
    assert _identity_safe_rows([row]) == []
    calls = []
    result = run_raw_prospect_promotion(
        [row], rpc_call=lambda *args: calls.append(args),
        execute=True, actor="founder-approved",
    )
    assert result["promoted_count"] == 0
    assert calls == []
    assert eligible_for_acp_admission(row) is False

    claim = classify_buyer_source_pages(
        [{"url": "https://buyer.example/buyers/",
          "visible_text": "We buy qualified leads."}],
        company_website="https://buyer.example",
    )
    row["site_evidence"]["buyer_claim_provenance"] = claim
    assert len(_identity_safe_rows([row])) == 1
    assert eligible_for_acp_admission(row) is True


def test_manual_promotion_filters_historical_official_identity_mismatch():
    from scripts.promote_buyer_scout_raw_prospects import _identity_safe_rows

    mismatched = candidate(
        business_name="Harvey",
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey AI"],
        },
    )
    assert _identity_safe_rows([mismatched]) == []


def test_promotion_core_rechecks_official_identity_even_when_review_ready():
    calls = []
    unsafe = candidate(
        business_name="Harvey",
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey AI"],
        },
    )
    result = run_raw_prospect_promotion(
        [unsafe], rpc_call=lambda *args: calls.append(args),
        execute=True, actor="founder-approved",
    )
    assert result["eligible_review_ready_count"] == 0
    assert result["promoted_count"] == 0
    assert result["database_write_performed"] is False
    assert calls == []


def test_dry_run_never_calls_rpc_or_writes():
    calls = []

    result = run_raw_prospect_promotion(
        [candidate()],
        rpc_call=lambda *args: calls.append(args),
    )

    assert result["mode"] == "OBSERVE"
    assert result["eligible_review_ready_count"] == 1
    assert result["promoted_count"] == 0
    assert result["database_write_performed"] is False
    assert result["canonical_promotion_performed"] is False
    assert result["autonomous_execution"] is False
    assert result["standing_authority"] is False
    assert result["execution_authority"] == "none"
    assert calls == []


def test_non_ready_rows_are_not_eligible():
    result = run_raw_prospect_promotion(
        [
            candidate(
                review_state="discovered",
                reconciliation_state="NEW_EXTERNAL_BUYER_CANDIDATE",
            )
        ],
        rpc_call=lambda *args: (_ for _ in ()).throw(
            AssertionError("rpc should not run")
        ),
        execute=True,
        actor="founder",
    )

    assert result["eligible_review_ready_count"] == 0
    assert result["promoted_count"] == 0
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False


def test_execute_calls_only_governed_rpc_and_preserves_boundaries():
    calls = []

    def rpc(method, path, body):
        calls.append((method, path, body))
        return {
            "decision": "raw_prospect_created",
            "candidate_id": body["p_candidate_id"],
            "canonical_prospect_id": "prospect-1",
            "prospect_created": True,
            "database_write_performed": True,
            "canonical_promotion_performed": True,
            "buy_signal_score_policy": "UNKNOWN_NULL",
            "qualification_created": False,
            "buyer_created": False,
            "outbound_sent": False,
            "terms_accepted": False,
            "actual_revenue": False,
        }

    result = run_raw_prospect_promotion(
        [candidate()],
        rpc_call=rpc,
        execute=True,
        actor="founder-approved",
    )

    assert calls == [(
        "POST",
        "/rest/v1/rpc/promote_buyer_scout_candidate_to_prospect",
        {
            "p_candidate_id": "candidate-1",
            "p_actor": "founder-approved",
        },
    )]
    assert result["mode"] == "GOVERNED"
    assert result["promoted_count"] == 1
    assert result["database_write_performed"] is True
    assert result["canonical_promotion_performed"] is True
    assert result["buy_signal_score_policy"] == "UNKNOWN_NULL"
    assert result["qualification_created"] is False
    assert result["buyer_created"] is False
    assert result["outbound_sent"] is False
    assert result["payment_action"] is False
    assert result["actual_revenue"] is False
    assert result["autonomous_execution"] is False
    assert result["standing_authority"] is False
    assert result["execution_authority"] == (
        "founder_governed_raw_prospect_promotion"
    )


def test_execute_requires_actor_when_eligible():
    try:
        run_raw_prospect_promotion(
            [candidate()],
            rpc_call=lambda *args: None,
            execute=True,
        )
    except ValueError as exc:
        assert "actor is required" in str(exc)
    else:
        raise AssertionError("missing actor should fail closed")


def test_acp_can_execute_bounded_internal_promotion():
    calls = []

    def rpc(method, path, body):
        calls.append(
            (
                method,
                path,
                body,
            )
        )

        return {
            "decision":
                "raw_prospect_created",
            "candidate_id":
                body["p_candidate_id"],
            "canonical_prospect_id":
                "prospect-acp-1",
            "prospect_created":
                True,
            "database_write_performed":
                True,
            "canonical_promotion_performed":
                True,
            "qualification_created":
                False,
            "buyer_created":
                False,
            "outbound_sent":
                False,
            "terms_accepted":
                False,
            "payment_action":
                False,
            "actual_revenue":
                False,
        }

    result = run_raw_prospect_promotion(
        [candidate()],
        rpc_call=rpc,
        execute=True,
        actor=(
            "empire_autonomous_"
            "commercial_progression"
        ),
        authority_mode="auto_internal",
    )

    assert result["mode"] == (
        "AUTO_INTERNAL"
    )

    assert (
        result[
            "autonomous_execution"
        ]
        is True
    )

    assert (
        result[
            "bounded_internal_authority"
        ]
        is True
    )

    assert result[
        "execution_authority"
    ] == "internal_write"

    assert (
        result[
            "standing_external_authority"
        ]
        is False
    )

    assert (
        result[
            "external_execution_authorized"
        ]
        is False
    )

    assert (
        result[
            "outreach_authorized"
        ]
        is False
    )

    assert (
        result[
            "call_authorized"
        ]
        is False
    )

    assert result[
        "outbound_sent"
    ] is False

    assert result[
        "payment_action"
    ] is False


def test_acp_internal_promotion_requires_exact_actor():
    try:
        run_raw_prospect_promotion(
            [candidate()],
            rpc_call=lambda *_args: None,
            execute=True,
            actor="buyer-scout",
            authority_mode="auto_internal",
        )
    except ValueError as exc:
        assert (
            "ACP actor"
            in str(exc)
        )
    else:
        raise AssertionError(
            "wrong AUTO_INTERNAL actor should fail closed"
        )
