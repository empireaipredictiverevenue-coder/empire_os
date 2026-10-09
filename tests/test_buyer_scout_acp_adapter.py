from empire_os.predictive_cloud_fabric import ExecutionAuthority

INTERNAL = ExecutionAuthority.EXECUTE_BOUNDED

import pytest

import empire_os.buyer_scout_acp_adapter as adapter


@pytest.fixture(autouse=True)
def isolated_identity_bridge(monkeypatch):
    monkeypatch.setattr(adapter, "materialize_buyer_scout_identity", lambda **kwargs: {
        "ok": True, "status": "CANONICALIZED", "decision_status": "RESOLVED",
        "internal_mutation_performed": True,
    })


def candidate(
    *,
    candidate_id,
    business,
    fit,
    people,
    canonical_prospect_id=None,
):
    return {
        "id": candidate_id,
        "domain":
            business.lower()
            .replace(" ", "")
            + ".example",
        "business_name":
            business,
        "website":
            "https://example.com",
        "review_state":
            "review_ready",
        "reconciliation_state":
            "REVIEW_READY",
        "canonical_prospect_id":
            canonical_prospect_id,
        "canonical_buyer_id":
            None,
        "direct_buyer_score":
            0,
        "explicit_direct_buyer_evidence":
            False,
        "target_buyer_pools": [
            "enterprise_and_data_buyers"
        ],
        "target_product_codes": [
            "private_capital_rollup"
        ],
        "provenance": {
            "predictive_revenue_enterprise_candidate":
                True,
            "predictive_revenue_enterprise_fit_score":
                fit,
        },
        "site_evidence": {
            "first_party_people":
                people,
        },
    }


def person(name, email):
    return {
        "name": name,
        "title":
            "Managing Director",
        "email": email,
        "source":
            "first_party_site",
        "source_url":
            "https://example.com/team",
        "mx_verified":
            True,
        "person_explicitly_named":
            True,
        "email_directly_bound_to_person":
            True,
    }


def test_rank_selects_highest_enterprise_fit():
    rows = [
        candidate(
            candidate_id="lower",
            business="Lower Buyer",
            fit=54,
            people=[
                person(
                    "Person A",
                    "a@lower.example",
                )
            ],
        ),
        candidate(
            candidate_id="primus",
            business="Primus Capital",
            fit=78,
            people=[
                person(
                    "Chris Welch",
                    "cwelch@primus.example",
                ),
                person(
                    "Aaron Davis",
                    "adavis@primus.example",
                ),
            ],
        ),
    ]

    ranked = (
        adapter.rank_precanonical_candidates(
            rows
        )
    )

    assert (
        ranked[0]["id"]
        == "primus"
    )

    assert (
        ranked[0][
            "_acp_enterprise_fit"
        ]
        == 78
    )


def test_candidate_requires_person_bound_first_party_contact():
    row = candidate(
        candidate_id="bad",
        business="Bad Buyer",
        fit=90,
        people=[{
            "name": "Unknown",
            "email": "x@bad.example",
            "source":
                "first_party_site",
            "source_url":
                "https://bad.example/team",
            "mx_verified":
                True,
            "person_explicitly_named":
                True,
            "email_directly_bound_to_person":
                False,
        }],
    )

    assert (
        adapter.eligible_for_acp_admission(
            row
        )
        is False
    )


def test_historical_false_official_registry_identity_is_not_acp_eligible():
    row = candidate(
        candidate_id="false-ready",
        business="Harvey",
        fit=100,
        people=[person("Jane Smith", "jane@harvey.ai")],
    )
    row["domain"] = "harvey.ai"
    row["query_evidence"] = [{
        "query": '"HARVEY HVAC SERVICES LLC" TX',
        "source_refs": ["official:texas_tdlr_ac:118954"],
    }]
    row["site_evidence"]["site_business_names"] = ["Harvey AI"]
    row["site_evidence"]["business_name_source"] = "first_party_site_identity"
    assert adapter.eligible_for_acp_admission(row) is False


def test_existing_canonical_prospect_is_not_repromoted():
    row = candidate(
        candidate_id="existing",
        business="Existing Buyer",
        fit=99,
        people=[
            person(
                "Person E",
                "e@existing.example",
            )
        ],
        canonical_prospect_id=
            "already-canonical",
    )

    assert (
        adapter.eligible_for_acp_admission(
            row
        )
        is False
    )


def test_admission_uses_existing_atomic_rpc(
    monkeypatch,
):
    primus = candidate(
        candidate_id="primus",
        business="Primus Capital",
        fit=78,
        people=[
            person(
                "Chris Welch",
                "cwelch@primus.example",
            )
        ],
    )

    monkeypatch.setattr(
        adapter,
        "fetch_precanonical_candidates",
        lambda: [primus],
    )

    seen = {}

    def fake_promotion(
        rows,
        *,
        rpc_call,
        execute,
        actor,
        authority_mode,
    ):
        seen["rows"] = rows
        seen["execute"] = execute
        seen["actor"] = actor
        seen["authority_mode"] = (
            authority_mode
        )

        return {
            "canonical_promotion_performed":
                True,
            "database_write_performed":
                True,
            "results": [{
                "candidate_id":
                    "primus",
                "canonical_prospect_id":
                    "prospect-primus",
                "decision":
                    "raw_prospect_created",
            }],
            "outbound_sent":
                False,
            "payment_action":
                False,
        }

    monkeypatch.setattr(
        adapter,
        "run_raw_prospect_promotion",
        fake_promotion,
    )

    result = (
        adapter.run_precanonical_admission(execution_authority=INTERNAL)
    )

    assert (
        result["status"]
        == "ADVANCED_CANONICAL_PROSPECT_CREATED"
    )

    assert (
        result[
            "canonical_prospect_id"
        ]
        == "prospect-primus"
    )

    assert (
        result[
            "internal_mutation_performed"
        ]
        is True
    )

    assert (
        seen["actor"]
        == adapter.ACP_ACTOR
    )

    assert (
        seen["authority_mode"]
        == "auto_internal"
    )

    assert seen["execute"] is True

    assert (
        result[
            "external_execution_performed"
        ]
        is False
    )


def test_preselected_candidate_is_not_refetched_or_reselected(
    monkeypatch,
):
    primus = candidate(
        candidate_id="primus-exact",
        business="Primus Capital",
        fit=78,
        people=[
            person(
                "Chris Welch",
                "cwelch@primus.example",
            ),
            person(
                "Aaron Davis",
                "adavis@primus.example",
            ),
        ],
    )

    def forbidden_fetch(*_args, **_kwargs):
        raise AssertionError(
            "preselected admission must not refetch candidates"
        )

    monkeypatch.setattr(
        adapter,
        "fetch_precanonical_candidates",
        forbidden_fetch,
    )

    seen = {}

    def fake_promotion(
        rows,
        *,
        rpc_call,
        execute,
        actor,
        authority_mode,
    ):
        seen["candidate_id"] = rows[0]["id"]
        seen["business_name"] = rows[0]["business_name"]

        return {
            "canonical_promotion_performed": True,
            "database_write_performed": True,
            "results": [{
                "candidate_id": rows[0]["id"],
                "canonical_prospect_id":
                    "prospect-primus-exact",
                "decision":
                    "raw_prospect_created",
            }],
            "outbound_sent": False,
            "payment_action": False,
        }

    monkeypatch.setattr(
        adapter,
        "run_raw_prospect_promotion",
        fake_promotion,
    )

    result = adapter.run_precanonical_admission(
        selected_candidate=primus,
        execution_authority=INTERNAL,
    )

    assert seen["candidate_id"] == "primus-exact"
    assert seen["business_name"] == "Primus Capital"

    assert (
        result["company_name"]
        == "Primus Capital"
    )

    assert (
        result["canonical_prospect_id"]
        == "prospect-primus-exact"
    )


@pytest.mark.parametrize('fails', [False, True])
def test_bridge_receives_exact_promoted_prospect_and_preserves_promotion(monkeypatch, fails):
    selected = candidate(candidate_id='selected',business='Selected',fit=90,
                         people=[person('Actual Person','person@selected.example')])
    monkeypatch.setattr(adapter,'fetch_precanonical_candidates',lambda:pytest.fail('must not refetch'))
    def promotion(rows,**kwargs):
        assert rows[0]['id']=='selected'
        return {'canonical_promotion_performed':True,'database_write_performed':True,
                'results':[{'candidate_id':'selected','canonical_prospect_id':'exact-promoted-id'}]}
    monkeypatch.setattr(adapter,'run_raw_prospect_promotion',promotion)
    seen=[]
    def bridge(**kwargs):
        seen.append(kwargs)
        if fails:
            raise RuntimeError('injected bridge failure')
        return {'ok':True,'decision_status':'RESOLVED'}
    monkeypatch.setattr(adapter,'materialize_buyer_scout_identity',bridge)
    result=adapter.run_precanonical_admission(selected_candidate=selected, execution_authority=INTERNAL)
    assert seen[0]['prospect_id']=='exact-promoted-id'
    assert seen[0]['write_authorized'] is True
    assert result['status']=='ADVANCED_CANONICAL_PROSPECT_CREATED'
    assert result['canonical_prospect_id']=='exact-promoted-id'
    assert result['internal_mutation_performed']
    if fails:
        assert result['retryable']
        assert result['blocker']=='CANONICAL_PERSON_BRIDGE_FAILED'
