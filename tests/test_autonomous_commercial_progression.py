from empire_os.predictive_cloud_fabric import ExecutionAuthority

INTERNAL = ExecutionAuthority.EXECUTE_BOUNDED

from empire_os.autonomous_commercial_progression import (
    build_progression_plan,
    classify_authority,
    execute_one_internal_progression,
    select_next_internal_action,
)


def action(
    name,
    *,
    company,
    authority="internal_write",
    founder=False,
    waiting=False,
):
    return {
        "entity_id": f"entity:{company.lower().replace(' ', '-')}",
        "company_name": company,
        "prospect_id": f"prospect:{company.lower().replace(' ', '-')}",
        "recommended_action": name,
        "authority": authority,
        "founder_gate_required": founder,
        "waiting_external": waiting,
    }


def test_internal_write_is_auto_internal():
    row = action(
        "verify_decision_maker",
        company="Primus Capital",
    )

    assert classify_authority(row) == "AUTO_INTERNAL"


def test_external_and_founder_actions_remain_gated():
    row = action(
        "terms_candidate",
        company="Primus Capital",
        authority="founder_gate",
        founder=True,
    )

    assert classify_authority(row) == "GATED_EXTERNAL"


def test_progression_beats_lower_value_internal_work():
    snapshot = {
        "actions": [
            action(
                "enrich_identity",
                company="Buyer A",
            ),
            action(
                "prepare_buyer_review",
                company="Primus Capital",
            ),
            action(
                "research_more",
                company="Buyer B",
            ),
        ]
    }

    selected = select_next_internal_action(snapshot)

    assert selected is not None
    assert selected["company_name"] == "Primus Capital"
    assert selected["recommended_action"] == "prepare_buyer_review"
    assert selected["internal_mutation_authorized"] is False
    assert selected["mutation_authorized"] is False
    assert selected["execution_authority"] == "none"


def test_external_action_is_never_selected_for_auto_execution():
    snapshot = {
        "actions": [
            action(
                "conversation_follow_up",
                company="External Buyer",
                authority="governed_external",
            )
        ]
    }

    assert select_next_internal_action(snapshot) is None


def test_execute_one_internal_action_records_learning_receipt():
    snapshot = {
        "actions": [
            action(
                "verify_decision_maker",
                company="Primus Capital",
            )
        ]
    }

    called = []

    def handler(row):
        called.append(row["company_name"])
        return {
            "status": "ADVANCED",
            "recovery_strategy": "first_party_identity_binding",
            "blocker": None,
            "evidence_ref": "test:first_party_identity",
            "internal_mutation_performed": True,
        }

    receipt = execute_one_internal_progression(
        snapshot,
        execution_authority=INTERNAL,
        handlers={
            "verify_decision_maker": handler,
        },
    )

    assert called == ["Primus Capital"]
    assert receipt.mode == "AUTO_INTERNAL"
    assert receipt.status == "ADVANCED"
    assert receipt.internal_mutation_performed is True
    assert receipt.external_execution_performed is False
    assert receipt.outbound_sent is False
    assert receipt.call_placed is False
    assert receipt.payment_action is False

    payload = receipt.as_dict()

    assert payload["learning_event"]["recovery_strategy"] == (
        "first_party_identity_binding"
    )
    assert (
        payload["learning_event"][
            "eligible_for_outcome_conditioned_economic_memory"
        ]
        is False
    )


def test_plan_exposes_external_gate_without_authorizing_it():
    snapshot = {
        "actions": [
            action(
                "verify_decision_maker",
                company="Primus Capital",
            ),
            action(
                "terms_candidate",
                company="Another Buyer",
                authority="founder_gate",
                founder=True,
            ),
        ]
    }

    plan = build_progression_plan(snapshot)

    assert plan["mode"] == "AUTO_INTERNAL"
    assert plan["safe_internal_action_available"] is True
    assert plan["execution_authority"] == "none"
    assert plan["external_gate_count"] == 1
    assert plan["outreach_authorized"] is False
    assert plan["call_authorized"] is False
    assert plan["binding_terms_authorized"] is False
    assert plan["payment_authorized"] is False
    assert plan["external_execution_authorized"] is False
