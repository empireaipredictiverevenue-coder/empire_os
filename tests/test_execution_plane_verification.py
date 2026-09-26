from empire_os.execution_plane_verification import (
    enqueue_promptfoo_verification,
    plan_candidate_verification,
)


def test_revenue_path_selects_revenue_swarm_lane():
    plan = plan_candidate_verification(
        request_id="verify-1",
        allowed_paths=("empire_os/bsc_payment_evidence.py",),
        required_tests=("tests/test_bsc_payment_evidence.py",),
    )
    assert "revenue_payments" in plan.swarm_lanes
    assert plan.production_promotion_allowed is False
    assert plan.execution_authority == "none"


def test_unknown_path_falls_back_to_integration_qa():
    plan = plan_candidate_verification(
        request_id="verify-2",
        allowed_paths=("empire_os/new_module.py",),
        required_tests=("tests/test_new_module.py",),
    )
    assert plan.swarm_lanes == ("integration_qa",)


def test_ai_behavior_change_requires_promptfoo():
    plan = plan_candidate_verification(
        request_id="verify-3",
        allowed_paths=("empire_os/closer_reply_worker.py",),
        required_tests=("tests/test_closer_reply_worker.py",),
        ai_behavior_change=True,
    )
    assert plan.promptfoo_required is True
    assert plan.promptfoo_config == (
        "evals/empire_core_policy/promptfooconfig.yaml"
    )



def test_promptfoo_request_is_queued_only_for_ai_behavior_change(tmp_path):
    plan = plan_candidate_verification(
        request_id="verify-ai",
        allowed_paths=("empire_os/closer_reply_worker.py",),
        required_tests=("tests/test_closer_reply_worker.py",),
        ai_behavior_change=True,
    )
    queued = enqueue_promptfoo_verification(
        tmp_path,
        plan,
        candidate_ref="pi/job-verify-ai",
    )
    assert queued is not None
    assert queued["queued"] is True
    assert queued["execution_authority"] == "none"

    non_ai = plan_candidate_verification(
        request_id="verify-code",
        allowed_paths=("empire_os/example.py",),
        required_tests=("tests/test_example.py",),
        ai_behavior_change=False,
    )
    assert enqueue_promptfoo_verification(
        tmp_path,
        non_ai,
        candidate_ref="branch",
    ) is None
