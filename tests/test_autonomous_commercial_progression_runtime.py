from empire_os.predictive_cloud_fabric import ExecutionAuthority

INTERNAL = ExecutionAuthority.EXECUTE_BOUNDED

from datetime import datetime, timezone

import pytest

import empire_os.autonomous_commercial_progression_runtime as runtime


@pytest.fixture(autouse=True)
def isolated_identity_bridge(monkeypatch):
    # Existing generic-source tests must not access the runtime gateway.
    monkeypatch.setattr(runtime, "materialize_buyer_scout_identity", lambda **kwargs: {
        "status": "NO_BUYER_SCOUT_ACQUISITION", "ok": False,
        "internal_mutation_performed": False,
    })


class FakeResult:
    def __init__(self, payload):
        self.payload = payload

    def as_dict(self):
        return dict(
            self.payload
        )


def test_real_handler_records_review_write(
    monkeypatch,
):
    def fake_materializer(**kwargs):
        assert kwargs[
            "prospect_ids"
        ] == ["prospect-1"]

        return FakeResult({
            "proposed": 1,
            "review_ready": 1,
            "skipped_existing": 0,
            "rejection_counts": {},
            "errors": [],
        })

    monkeypatch.setattr(
        runtime,
        "run_buyer_review_materializer",
        fake_materializer,
    )

    result = (
        runtime._targeted_review_progression({
            "prospect_id": "prospect-1",
        }, execution_authority=INTERNAL)
    )

    assert result["status"] == (
        "ADVANCED_REVIEW_PROPOSED"
    )

    assert (
        result[
            "internal_mutation_performed"
        ]
        is True
    )

    assert result[
        "outbound_sent"
    ] is False

    assert result[
        "call_placed"
    ] is False

    assert result[
        "payment_action"
    ] is False


def test_blocked_handler_does_not_claim_write(
    monkeypatch,
):
    def fake_materializer(**_kwargs):
        return FakeResult({
            "proposed": 0,
            "review_ready": 0,
            "skipped_existing": 0,
            "rejection_counts": {
                "no_decision_maker": 1,
            },
            "errors": [],
        })

    monkeypatch.setattr(
        runtime,
        "run_buyer_review_materializer",
        fake_materializer,
    )

    result = (
        runtime._targeted_review_progression({
            "prospect_id": "prospect-2",
        }, execution_authority=INTERNAL)
    )

    assert (
        result["status"]
        == "BLOCKED"
    )

    assert (
        result[
            "internal_mutation_performed"
        ]
        is False
    )


def test_learning_is_progression_only():
    memory = runtime._strategy_memory([
        {
            "action":
                "verify_decision_maker",
            "recovery_strategy":
                "targeted_source_probe_identity_recovery_review",
            "status":
                "ADVANCED_REVIEW_PROPOSED",
        },
        {
            "action":
                "verify_decision_maker",
            "recovery_strategy":
                "targeted_source_probe_identity_recovery_review",
            "status":
                "BLOCKED",
        },
    ])

    assert (
        memory["attempt_count"]
        == 2
    )

    row = memory[
        "strategies"
    ][0]

    assert row[
        "advance_rate"
    ] == 0.5

    assert (
        memory[
            "commercial_outcome_learning"
        ]
        is False
    )

    assert (
        memory[
            "synthetic_revenue_allowed"
        ]
        is False
    )


def test_blocked_action_enters_cooldown():
    now = datetime.now(
        timezone.utc
    ).isoformat()

    action = {
        "recommended_action":
            "verify_decision_maker",
        "entity_id":
            "entity-1",
        "prospect_id":
            "prospect-1",
    }

    attempts = [{
        "generated_at": now,
        "action":
            "verify_decision_maker",
        "entity_id":
            "entity-1",
        "prospect_id":
            "prospect-1",
        "status":
            "BLOCKED",
    }]

    assert (
        runtime._cooldown_active(
            action,
            attempts,
        )
        is True
    )


def test_research_more_uses_research_executor(
    monkeypatch,
):
    seen = []

    def fake_fetch(prospect_id):
        assert prospect_id == "prospect-r"
        return {
            "id": prospect_id,
            "business_name": "Research Buyer",
            "website": "https://example.com",
        }

    def fake_probe(row):
        seen.append(row["id"])
        return {
            "review_ready": False,
            "outreach_ready": False,
            "rejection_reason":
                "no_contact_evidence",
        }

    monkeypatch.setattr(
        runtime,
        "_fetch_canonical_prospect",
        fake_fetch,
    )

    monkeypatch.setattr(
        runtime,
        "_source_probe",
        fake_probe,
    )

    result = (
        runtime._targeted_research_progression({
            "prospect_id": "prospect-r",
        }, execution_authority=INTERNAL)
    )

    assert seen == ["prospect-r"]
    assert result["status"] == "BLOCKED"
    assert result["blocker"] == (
        "no_contact_evidence"
    )
    assert result["executor"] == (
        "first_party_research"
    )


def test_handler_map_does_not_send_research_to_review():
    handlers = runtime.build_handlers()

    assert handlers["research_more"].func is (
        runtime._targeted_research_progression
    )

    assert handlers["refresh_evidence"].func is (
        runtime._targeted_research_progression
    )

    assert handlers["verify_decision_maker"].func is (
        runtime._targeted_review_progression
    )

    assert handlers["prepare_buyer_review"].func is (
        runtime._targeted_review_progression
    )


def test_legacy_research_misroute_is_not_learned():
    memory = runtime._strategy_memory([
        {
            "action": "research_more",
            "recovery_strategy":
                "targeted_source_probe_identity_recovery_review",
            "status": "BLOCKED",
        },
        {
            "action": "research_more",
            "recovery_strategy":
                "targeted_first_party_research_probe",
            "status": "ADVANCED_EVIDENCE_DISCOVERED",
        },
    ])

    assert memory["attempt_count"] == 2

    assert (
        memory[
            "learning_eligible_attempt_count"
        ]
        == 1
    )

    assert (
        memory[
            "excluded_attempt_count"
        ]
        == 1
    )

    assert len(
        memory["strategies"]
    ) == 1

    row = memory["strategies"][0]

    assert (
        row["recovery_strategy"]
        == "targeted_first_party_research_probe"
    )

    assert row["advance_rate"] == 1.0


def test_idle_canonical_queue_can_admit_precanonical_candidate(
    monkeypatch,
):
    monkeypatch.setattr(
        runtime,
        "write_progression_plan",
        lambda *_args, **_kwargs: None,
    )

    monkeypatch.setattr(
        runtime,
        "_write_json",
        lambda *_args, **_kwargs: None,
    )

    logged = []

    monkeypatch.setattr(
        runtime,
        "_append_attempt",
        lambda payload:
            logged.append(payload),
    )

    monkeypatch.setattr(
        runtime,
        "_precanonical_cooldown_ids",
        lambda: set(),
    )

    monkeypatch.setattr(
        runtime,
        "run_precanonical_admission",
        lambda **_kwargs: {
            "generated_at":
                "2026-10-04T18:00:00+00:00",
            "status":
                "ADVANCED_CANONICAL_PROSPECT_CREATED",
            "action":
                "canonicalize_buyer_scout_candidate",
            "blocker": None,
            "recovery_strategy":
                "review_ready_person_bound_to_canonical_prospect",
            "candidate_id":
                "candidate-primus",
            "company_name":
                "Primus Capital",
            "canonical_prospect_id":
                "prospect-primus",
            "internal_mutation_performed":
                True,
            "external_execution_performed":
                False,
            "outbound_sent":
                False,
            "call_placed":
                False,
            "payment_action":
                False,
        },
    )

    monkeypatch.setattr(
        runtime,
        "refresh_strategy_memory",
        lambda: {
            "attempt_count": 1,
        },
    )

    result = runtime.run_internal_cycle(
        {"actions": []},
        execute=True,
        execution_authority=INTERNAL,
    )

    receipt = result["receipt"]

    assert (
        receipt["action"]
        == "canonicalize_buyer_scout_candidate"
    )

    assert (
        receipt["company_name"]
        == "Primus Capital"
    )

    assert (
        receipt[
            "internal_mutation_performed"
        ]
        is True
    )

    assert (
        receipt[
            "external_execution_performed"
        ]
        is False
    )

    assert len(logged) == 1


def test_scout_recovery_uses_exact_canonical_review_input_without_recrawl(monkeypatch):
    probe_result={'review_ready':True,'outreach_ready':True}
    seen=[]
    def bridge(**kwargs):
        seen.append(kwargs['prospect_id'])
        return {'ok':True,'status':'CANONICALIZED','decision_status':'RESOLVED',
                'review_input':probe_result,'internal_mutation_performed':True}
    monkeypatch.setattr(runtime,'materialize_buyer_scout_identity',bridge)
    monkeypatch.setattr(runtime,'_source_probe',lambda row:pytest.fail('must not recrawl Scout'))
    def materializer(**kwargs):
        assert kwargs['prospect_ids']==['exact-id']
        assert kwargs['probe']({'id':'exact-id'}) is probe_result
        with pytest.raises(ValueError,match='mismatch'):
            kwargs['probe']({'id':'wrong-id'})
        return FakeResult({'proposed':1})
    monkeypatch.setattr(runtime,'run_buyer_review_materializer',materializer)
    result=runtime._targeted_review_progression({'prospect_id':'exact-id'}, execution_authority=INTERNAL)
    assert seen==['exact-id']
    assert result['status']=='ADVANCED_REVIEW_PROPOSED'


def test_scout_bridge_blocker_does_not_fall_through_to_crawl(monkeypatch):
    monkeypatch.setattr(runtime,'materialize_buyer_scout_identity',lambda **kwargs: {
        'ok':True,'status':'CANONICALIZED','decision_status':'AMBIGUOUS_DECISION_MAKER',
        'internal_mutation_performed':True,
    })
    monkeypatch.setattr(runtime,'run_buyer_review_materializer',lambda **kwargs:pytest.fail('ambiguous decision maker'))
    result=runtime._targeted_review_progression({'prospect_id':'exact-id'}, execution_authority=INTERNAL)
    assert result['status']=='BLOCKED'
    assert result['blocker']=='AMBIGUOUS_DECISION_MAKER'
    assert result['internal_mutation_performed']


def test_scout_research_action_recovers_immutable_identity_without_recrawl(monkeypatch):
    monkeypatch.setattr(runtime,'_fetch_canonical_prospect',lambda pid:{'id':pid})
    monkeypatch.setattr(runtime,'materialize_buyer_scout_identity',lambda **kwargs:{'status':'OBSERVE','ok':True})
    monkeypatch.setattr(runtime,'_source_probe',lambda row:pytest.fail('Scout must not be recrawled'))
    seen=[]
    def review(action, **kwargs):
        seen.append(action['prospect_id'])
        return {'status':'BLOCKED','blocker':'AMBIGUOUS_DECISION_MAKER'}
    monkeypatch.setattr(runtime,'_targeted_review_progression',review)
    result=runtime._targeted_research_progression({'prospect_id':'exact-id'}, execution_authority=INTERNAL)
    assert seen==['exact-id']
    assert result['blocker']=='AMBIGUOUS_DECISION_MAKER'
