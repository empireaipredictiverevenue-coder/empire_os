from empire_os.jev_strategy import (
    build_jev_eval_plan,
    compare_decision_providers,
    review_jev_use_case,
)


def use_case():
    return {
        "task_key": "agent_routing",
        "risk_class": "low",
        "decision_schema_ref": "schema:agent-routing:v1",
        "baseline_ref": "baseline:router:v1",
        "evaluation_dataset_refs": ["evalset:routing:v1"],
        "deterministic_possible": False,
        "open_ended_generation": False,
        "requires_exact_math": False,
        "consequential_authority": False,
    }


def test_jev_use_case_stays_eval_only():
    r=review_jev_use_case(use_case())
    assert r["review_ready"] is True
    assert r["offline_eval_required"] is True
    assert r["shadow_required"] is True
    assert r["provider_activation"] is False
    assert r["execution_authority"]=="none"


def test_consequential_authority_is_never_delegated_to_jev():
    row=use_case()
    row["risk_class"]="consequential"
    row["consequential_authority"]=True
    r=review_jev_use_case(row)
    assert "jev_cannot_authorize_consequential_action" in r["warnings"]
    assert r["authority_expansion"] is False


def test_eval_plan_does_not_require_credentials():
    r=build_jev_eval_plan([use_case()])
    assert r["ready_for_offline_eval"]==["agent_routing"]
    assert r["credentials_required_now"] is False
    assert r["external_data_send"] is False


def test_private_eval_provider_comparison_is_observed_only():
    r=compare_decision_providers([
        {
            "provider_key":"jev",
            "accuracy":.91,
            "brier_score":.09,
            "p95_latency_ms":300,
            "cost_per_million_input_tokens":.042,
            "operational_failure_rate":.01,
            "evidence_refs":["private-eval:jev:v1"],
        },
        {
            "provider_key":"small-llm",
            "accuracy":.88,
            "brier_score":.14,
            "p95_latency_ms":800,
            "cost_per_million_input_tokens":.20,
            "operational_failure_rate":.02,
            "evidence_refs":["private-eval:small:v1"],
        },
    ])
    assert r["providers"][0]["provider_key"]=="jev"
    assert r["provider_activation"] is False
    assert r["recommendation_only"] is True
