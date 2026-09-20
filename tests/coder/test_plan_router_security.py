import pytest

from empire_os.coder.models import TaskPhase
from empire_os.coder.orchestrator import local_ollama_profiles
from empire_os.coder.plan import PlanStep, PlanStepStatus, TaskPlan
from empire_os.coder.router import ModelProfile, ModelRouter
from empire_os.coder.security import scan_text, scrub_text
from empire_os.coder.self_build import SelfBuildScopeError, validate_self_build_scope


def test_plan_dependency_and_parallel_file_conflict_rules():
    plan = TaskPlan([
        PlanStep("a", "inspect", TaskPhase.UNDERSTAND),
        PlanStep("b", "module b", TaskPhase.PATCH, ("a",), ("a.py",)),
        PlanStep("c", "module c", TaskPhase.PATCH, ("a",), ("c.py",)),
        PlanStep("d", "same file", TaskPhase.PATCH, ("a",), ("a.py",)),
    ])
    plan.validate()
    assert [step.id for step in plan.ready()] == ["a"]
    plan.mark("a", PlanStepStatus.COMPLETED)
    groups = plan.parallel_groups()
    assert {step.id for step in groups[0]} == {"b", "c"}
    assert [step.id for step in groups[1]] == ["d"]


def test_plan_cycles_are_rejected():
    plan = TaskPlan([
        PlanStep("a", "a", TaskPhase.PLAN, ("b",)),
        PlanStep("b", "b", TaskPhase.PLAN, ("a",)),
    ])
    with pytest.raises(ValueError, match="cycle"):
        plan.validate()


def test_router_prefers_cheapest_capable_model():
    router = ModelRouter([
        ModelProfile("local", "tiny", capability=1, cost_tier=0, local=True),
        ModelProfile("hosted", "mid", capability=2, cost_tier=1),
        ModelProfile("hosted", "strong", capability=3, cost_tier=3),
    ])
    assert router.route("Implement a new endpoint and tests").model == "mid"


def test_router_keeps_planner_only_model_out_of_writer_route():
    router = ModelRouter([
        ModelProfile(
            "ollama",
            "fast-planner",
            capability=2,
            cost_tier=0,
            local=True,
            roles=("planner",),
        ),
        ModelProfile(
            "ollama",
            "strong-writer",
            capability=3,
            cost_tier=0,
            local=True,
            roles=("writer",),
        ),
    ])
    objective = "Review the current implementation plan"
    assert router.route(
        objective,
        role="planner",
    ).model == "fast-planner"
    assert router.route(
        objective,
        role="writer",
    ).model == "strong-writer"


def test_local_planner_ladder_routes_by_complexity():
    router = ModelRouter(local_ollama_profiles([
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "qwen3-coder:30b",
    ]))

    assert router.route(
        "Review the current implementation plan",
        role="planner",
    ).model == "qwen2.5-coder:7b"

    assert router.route(
        "Implement a new endpoint and tests",
        role="planner",
    ).model == "qwen2.5-coder:7b"

    assert router.route(
        "Review the current implementation plan",
        role="writer",
    ).model == "qwen2.5-coder:14b"

    assert router.route(
        "Implement a new endpoint and tests",
        role="writer",
    ).model == "qwen2.5-coder:14b"

    assert router.route(
        "Refactor payment database architecture",
        role="writer",
    ).model == "qwen3-coder:30b"

    assert router.route(
        "Plan a security database migration architecture",
        role="planner",
    ).model == "qwen2.5-coder:7b"


def test_router_does_not_escalate_on_negated_safety_guards():
    objective = (
        "Review the current Phase 4 plan. "
        "No payments, no database changes, no security changes, "
        "and do not migration."
    )
    assert ModelRouter.complexity(objective) == 1


def test_security_scrubs_secret_and_flags_dangerous_code():
    text = "OPENAI_API_KEY=sk-" + ("x" * 30)
    assert "[REDACTED]" in scrub_text(text)
    findings = scan_text("subprocess.run(cmd, shell=True)")
    assert any(f.kind == "dangerous_code" for f in findings)


def test_security_does_not_flag_public_token_variable_assignment():
    findings = scan_text(
        'token = os.getenv("BSC_USDT_TOKEN_CONTRACT", BSC_USDT_CONTRACT).strip()'
    )
    assert not any(f.kind == "secret_material" for f in findings)


def test_security_still_flags_literal_secret_assignments():
    findings = scan_text(
        'SERVICE_TOKEN = "abcdefghijklmnopqrstuvwx123456"'
    )
    assert any(f.kind == "secret_material" for f in findings)


def test_self_build_scope_cannot_escape_coder():
    assert validate_self_build_scope(["empire_os/coder/repo.py", "tests/coder/test_repo.py"])
    with pytest.raises(SelfBuildScopeError):
        validate_self_build_scope(["empire_os/payments.py"])
