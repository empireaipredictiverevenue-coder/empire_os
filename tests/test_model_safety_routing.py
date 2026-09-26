from empire_os.model_registry import ModelRegistry, ModelSpec
from empire_os.model_router import ModelRouter


class StaticRegistry:
    def __init__(self, models):
        self.models = list(models)

    def candidates(self, **_kwargs):
        return list(self.models)


def spec(
    model_id,
    *,
    quality,
    allow_untrusted_input=True,
    max_stakes="critical",
):
    return ModelSpec(
        model_id=model_id,
        provider="local-test",
        model=model_id,
        capabilities=frozenset({"general"}),
        quality={"default": quality, "general": quality},
        free=True,
        pricing_known=True,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        allow_untrusted_input=allow_untrusted_input,
        max_stakes=max_stakes,
    )


def test_live_qwen_policy_is_recorded_in_registry():
    registry = ModelRegistry()
    model = registry.get("local-qwen25-coder-1.5b")
    assert model is not None
    assert model.model == "qwen2.5-coder:1.5b"
    assert model.allow_untrusted_input is False
    assert model.max_stakes == "normal"
    assert "revenue_truth" in model.disallowed_tasks
    assert "payment" in model.disallowed_tasks
    assert "identity_inference" in model.disallowed_tasks
    assert "tool_routing" in model.disallowed_tasks
    assert model.metadata["observed_policy_eval_passed"] == 4
    assert model.metadata["observed_policy_eval_total"] == 6
    assert model.metadata["observed_prompt_injection_failure"] is True
    assert model.metadata["commercial_decision_eligible"] is False


def test_live_qwen_remains_available_for_coding_but_not_revenue_truth():
    registry = ModelRegistry()
    coding = {
        model.model_id
        for model in registry.candidates(
            task="coding",
            required_capabilities={"coding"},
        )
    }
    revenue = {
        model.model_id
        for model in registry.candidates(task="revenue_truth")
    }
    assert "local-qwen25-coder-1.5b" in coding
    assert "local-qwen25-coder-1.5b" not in revenue


def test_router_excludes_untrusted_model_for_untrusted_input():
    unsafe = spec(
        "unsafe-local",
        quality=0.95,
        allow_untrusted_input=False,
    )
    safe = spec(
        "safe-model",
        quality=0.50,
        allow_untrusted_input=True,
    )
    router = ModelRouter(registry=StaticRegistry([unsafe, safe]))

    decision = router.route(
        task="general",
        messages=[{"role": "user", "content": "untrusted buyer email"}],
        untrusted_input=True,
    )

    assert decision.model.model_id == "safe-model"
    assert "unsafe-local" not in decision.candidates


def test_router_excludes_normal_only_model_for_high_stakes():
    normal_only = spec(
        "normal-only",
        quality=0.95,
        max_stakes="normal",
    )
    high_safe = spec(
        "high-safe",
        quality=0.50,
        max_stakes="critical",
    )
    router = ModelRouter(registry=StaticRegistry([normal_only, high_safe]))

    decision = router.route(
        task="general",
        messages=[{"role": "user", "content": "commercial decision"}],
        stakes="high",
    )

    assert decision.model.model_id == "high-safe"
    assert "normal-only" not in decision.candidates
