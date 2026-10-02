from empire_os.economic_memory import (
    build_economic_memory_snapshot,
)


def _evaluation():
    return {
        "plan_id": "astra_plan_test",
        "evaluation_state": "BLOCKED",
    }


def _work(status="DONE"):
    return {
        "id": "dept-work-1",
        "plan_id": "astra_plan_test",
        "step_id": "step-1",
        "goal_key": "complete_opportunity_evidence",
        "department_keys": ["data_quant"],
        "target_component": "predictive_intelligence",
        "action": "resolve_quant_input:probability_success",
        "status": status,
        "evidence_refs": ["opportunity:1"],
        "result_evidence_refs": [
            "runtime:predictive_intelligence:latest"
        ],
        "result": {"available_product_codes": ["managed_service"]},
    }


def _verified_packet():
    return {
        "entity_id": "entity-1",
        "company_name": "Example Co",
        "verification": {
            "payment_verified": True,
            "fulfilment_verified": True,
            "recognized_revenue": True,
        },
        "label": {
            "available": True,
            "kind": "verified_customer_conversion",
            "value": 1,
            "conversion_outcome": "won",
            "outcome_ref": "canonical:commercial_outcomes:outcome-1",
            "evidence_refs": [
                "canonical:commercial_outcomes:outcome-1",
                "canonical:bsc_payment_evidence:payment-1",
                "canonical:fulfilment_orders:order-1",
                "canonical:account_revenue_truth:entity-1",
            ],
            "synthetic": False,
            "forecast_derived": False,
        },
        "calibration_feedback": {
            "available": True,
            "qualification_score": 82.0,
            "verified_label": 1,
            "model_weight_mutation_authorized": False,
        },
    }


def test_department_done_is_episode_not_verified_outcome():
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[_work("DONE")],
        cortex_learning={"packet_count": 0, "packets": []},
    )
    assert result["department_episode_count"] == 1
    episode = result["department_episodes"][0]
    assert episode["memory_type"] == "episodic"
    assert episode["status"] == "DONE"
    assert episode["verified_outcome"] is False
    assert episode["department_done_is_verified_outcome"] is False
    assert result["outcome_conditioned_memory_count"] == 0


def test_verified_cortex_label_becomes_outcome_conditioned_memory():
    packet = _verified_packet()
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[_work()],
        cortex_learning={
            "packet_count": 1,
            "learning_ready_count": 1,
            "packets": [packet],
        },
    )
    assert result["outcome_conditioned_memory_count"] == 1
    memory = result["outcome_conditioned_memories"][0]
    assert memory["memory_type"] == "outcome_conditioned"
    assert memory["verified_outcome"] is True
    assert memory["outcome_ref"] == (
        "canonical:commercial_outcomes:outcome-1"
    )
    assert memory["label_value"] == 1
    assert memory["accepted_for_retrieval"] is True
    assert result["model_weight_mutation_authorized"] is False
    assert result["execution_authority"] == "none"


def test_unready_or_forecast_label_never_enters_outcome_memory():
    unready = _verified_packet()
    unready["label"] = {
        **unready["label"],
        "available": False,
    }
    forecast = _verified_packet()
    forecast["entity_id"] = "entity-2"
    forecast["label"] = {
        **forecast["label"],
        "forecast_derived": True,
    }
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[],
        cortex_learning={
            "packet_count": 2,
            "learning_ready_count": 1,
            "packets": [unready, forecast],
        },
    )
    assert result["outcome_memory_candidate_count"] == 0
    assert result["outcome_conditioned_memory_count"] == 0
    assert result["forecast_used_as_outcome"] is False
    assert result["synthetic_outcomes_allowed"] is False


def test_missing_outcome_provenance_is_rejected():
    packet = _verified_packet()
    packet["label"] = {
        **packet["label"],
        "outcome_ref": None,
        "evidence_refs": [],
    }
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[],
        cortex_learning={
            "packet_count": 1,
            "learning_ready_count": 1,
            "packets": [packet],
        },
    )
    assert result["outcome_memory_candidate_count"] == 1
    assert result["outcome_conditioned_memory_count"] == 0
    assert result["rejected_outcome_memory_count"] == 1


def test_explicit_causal_outcome_ref_links_plan_step_to_verified_outcome():
    packet = _verified_packet()
    work = _work('DONE')
    work['result'] = {
        **work['result'],
        'causal_outcome_refs':['canonical:commercial_outcomes:outcome-1'],
    }
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[work],
        cortex_learning={
            'packet_count':1,
            'learning_ready_count':1,
            'packets':[packet],
        },
    )
    assert result['plan_outcome_attribution_count'] == 1
    row = result['plan_outcome_attributions'][0]
    assert row['plan_id'] == 'astra_plan_test'
    assert row['step_id'] == 'step-1'
    assert row['work_id'] == 'dept-work-1'
    assert row['outcome_ref'] == 'canonical:commercial_outcomes:outcome-1'
    assert row['entity_id'] == 'entity-1'
    assert row['attribution_basis'] == 'explicit_causal_outcome_ref'
    assert row['causal_attribution_claimed'] is True
    assert result['unattributed_verified_outcome_count'] == 0
    assert result['causal_attribution_requires_explicit_outcome_ref'] is True


def test_entity_or_generic_evidence_overlap_never_creates_causal_attribution():
    packet = _verified_packet()
    work = _work('DONE')
    work['result'] = {
        **work['result'],
        'entity_id':'entity-1',
        'evidence_refs':['canonical:commercial_outcomes:outcome-1'],
    }
    work['result_evidence_refs'] = ['canonical:commercial_outcomes:outcome-1']
    result = build_economic_memory_snapshot(
        executive_evaluation=_evaluation(),
        department_work=[work],
        cortex_learning={
            'packet_count':1,
            'learning_ready_count':1,
            'packets':[packet],
        },
    )
    assert result['outcome_conditioned_memory_count'] == 1
    assert result['plan_outcome_attribution_count'] == 0
    assert result['unattributed_verified_outcome_count'] == 1
