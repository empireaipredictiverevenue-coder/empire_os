from types import SimpleNamespace

from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    Sensitivity,
    TaskKind,
)
from empire_os.hybrid_compute_v2 import (
    build_capability_view,
    build_current_route_view,
    build_health_view,
    observe_hybrid_route,
)


class FakeModel:
    def __init__(
        self,
        model_id: str,
        *,
        provider: str,
        local: bool,
        quality: float | None,
        cost_known: bool,
    ) -> None:
        self.model_id = model_id
        self.provider = provider
        self.local = local
        self._quality = quality
        self._cost_known = cost_known
        self.capabilities = {"text"}

    def quality_for(self, task: str):
        return self._quality

    def cost_known(self):
        return self._cost_known


class FakeRegistry:
    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return list(self.rows)

    def candidates(
        self,
        *,
        task,
        required_capabilities=None,
        require_reasoning=False,
        require_vision=False,
    ):
        return list(self.rows)


class BrokenRegistry:
    def all(self):
        raise RuntimeError("registry down")

    def candidates(self, **kwargs):
        raise RuntimeError("registry down")


class FakeHealth:
    def __init__(self):
        self.saved = False

    def calculate(self):
        return {
            "status": "healthy",
            "models": {},
        }

    def save(self):
        self.saved = True
        raise AssertionError(
            "Hybrid V2 must not persist health"
        )


class BrokenHealth:
    def calculate(self):
        raise RuntimeError("receipt failure")


class FakeRouter:
    def __init__(
        self,
        *,
        provider="openrouter",
        model="frontier-x",
        local=False,
    ):
        self.provider = provider
        self.model = model
        self.local = local
        self.calls = 0

    def route(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            provider=self.provider,
            model=self.model,
            local=self.local,
            reason="canonical_test_route",
        )


class SpySink:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)


def _registry():
    return FakeRegistry(
        [
            FakeModel(
                "qwen-local",
                provider="llama_cpp",
                local=True,
                quality=0.91,
                cost_known=True,
            ),
            FakeModel(
                "frontier-x",
                provider="openrouter",
                local=False,
                quality=0.96,
                cost_known=False,
            ),
        ]
    )


def test_capability_view_uses_canonical_registry():
    result = build_capability_view(
        registry=_registry(),
        task="reasoning",
    )

    assert result["status"] == "AVAILABLE"
    assert result["all_model_count"] == 2
    assert result["candidate_count"] == 2
    assert result["local_candidate_count"] == 1
    assert result["remote_candidate_count"] == 1


def test_registry_failure_stays_unavailable():
    result = build_capability_view(
        registry=BrokenRegistry(),
        task="reasoning",
    )

    assert result["status"] == "UNAVAILABLE"
    assert (
        result["reason"]
        == "canonical_registry_read_failed"
    )


def test_health_is_read_only():
    health = FakeHealth()

    result = build_health_view(
        health=health,
    )

    assert result["status"] == "AVAILABLE"
    assert health.saved is False


def test_health_failure_stays_unavailable():
    result = build_health_view(
        health=BrokenHealth(),
    )

    assert result["status"] == "UNAVAILABLE"
    assert (
        result["reason"]
        == "canonical_health_read_failed"
    )


def test_shadow_observation_never_applies_route():
    router = FakeRouter()

    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            sensitivity=Sensitivity.INTERNAL,
            complexity=0.2,
            quality_floor=0.90,
        ),
        messages=[
            {
                "role": "user",
                "content": "private body",
            }
        ],
        registry=_registry(),
        health=FakeHealth(),
        router=router,
    )

    assert router.calls == 1
    assert result.production_authority is False
    assert result.route_applied is False
    assert result.execution_performed is False
    assert (
        result.hybrid_decision[
            "recommended_route"
        ]
        == Route.LOCAL_SMALL.value
    )


def test_local_recommendation_observes_local_candidate():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            quality_floor=0.90,
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    capability = result.recommended_capability

    assert (
        capability["status"]
        == "CANDIDATE_OBSERVED"
    )
    assert capability["candidate_count"] == 1
    assert (
        capability[
            "quality_meeting_candidate_count"
        ]
        == 1
    )


def test_frontier_recommendation_observes_remote_candidate():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.REASON,
            complexity=0.95,
            quality_floor=0.95,
            expected_value_gbp=25_000,
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.hybrid_decision[
            "recommended_route"
        ]
        == Route.FRONTIER.value
    )
    assert (
        result.recommended_capability[
            "candidate_count"
        ]
        == 1
    )


def test_predictive_route_preserves_canonical_owner():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.PREDICTIVE_REVENUE
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.recommended_capability["status"]
        == "EXTERNAL_CANONICAL_OWNER"
    )
    assert (
        result.recommended_capability["owner"]
        == "predictive_cloud"
    )


def test_governed_action_requires_no_model_promotion():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.PAYMENT,
            risk=1.0,
            expected_value_gbp=100_000,
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.hybrid_decision[
            "recommended_route"
        ]
        == Route.HUMAN_GATE.value
    )
    assert (
        result.recommended_capability["status"]
        == "NO_MODEL_REQUIRED"
    )
    assert result.production_authority is False


def test_restricted_external_research_human_gate():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.RESEARCH,
            sensitivity=Sensitivity.RESTRICTED,
            requires_external_knowledge=True,
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.hybrid_decision[
            "recommended_route"
        ]
        == Route.HUMAN_GATE.value
    )
    assert (
        result.recommended_capability["status"]
        == "NO_MODEL_REQUIRED"
    )


def test_telemetry_contains_metadata_not_message_body():
    sink = SpySink()

    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.REASON,
        ),
        messages=[
            {
                "role": "user",
                "content": "TOP SECRET BODY",
            }
        ],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
        telemetry_sink=sink,
    )

    assert result.execution_performed is False
    assert len(sink.events) == 1

    rendered = repr(sink.events[0])

    assert "TOP SECRET BODY" not in rendered
    assert "hybrid_compute.shadow_route" in rendered


def test_nested_model_spec_identity_is_preserved():
    spec = FakeModel(
        "opencode-free",
        provider="opencode",
        local=False,
        quality=0.87,
        cost_known=False,
    )
    spec.model = "nemotron-3-ultra-free"
    spec.deployment = "cloud"

    class NestedRouter:
        def route(self, **kwargs):
            return SimpleNamespace(
                model=spec,
                reason="canonical_nested_spec",
                estimated_cost=0.0,
            )

    result = build_current_route_view(
        router=NestedRouter(),
        task="reasoning",
        messages=[],
        system=None,
        stakes="normal",
        require_reasoning=False,
        require_vision=False,
        budget_remaining=None,
        remaining_queries=None,
    )

    assert result["provider"] == "opencode"
    assert result["model_id"] == "opencode-free"
    assert (
        result["model"]
        == "nemotron-3-ultra-free"
    )
    assert result["deployment"] == "cloud"
    assert result["local"] is False


def test_unknown_cost_is_not_promoted_to_zero():
    spec = FakeModel(
        "free-but-unverified",
        provider="remote",
        local=False,
        quality=0.90,
        cost_known=False,
    )
    spec.model = "candidate"
    spec.deployment = "cloud"

    class CostRouter:
        def route(self, **kwargs):
            return SimpleNamespace(
                model=spec,
                reason="test",
                estimated_cost=0.0,
            )

    result = build_current_route_view(
        router=CostRouter(),
        task="reasoning",
        messages=[],
        system=None,
        stakes="normal",
        require_reasoning=False,
        require_vision=False,
        budget_remaining=None,
        remaining_queries=None,
    )

    assert result["cost_known"] is False
    assert result["cost"] is None


def test_unknown_placement_is_not_false_no_candidate():
    model = FakeModel(
        "placement-unknown",
        provider="provider-x",
        local=False,
        quality=0.91,
        cost_known=True,
    )
    del model.local
    model.deployment = "unknown"

    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            quality_floor=0.90,
        ),
        messages=[],
        registry=FakeRegistry([model]),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.recommended_capability["status"]
        == "PLACEMENT_UNVERIFIED"
    )
    assert (
        result.recommended_capability[
            "unknown_placement_count"
        ]
        == 1
    )


def test_optimization_route_preserves_canonical_owner():
    result = observe_hybrid_route(
        request=HybridRequest(
            task_kind=TaskKind.OPTIMIZE
        ),
        messages=[],
        registry=_registry(),
        health=FakeHealth(),
        router=FakeRouter(),
    )

    assert (
        result.hybrid_decision[
            "recommended_route"
        ]
        == Route.OPTIMIZATION.value
    )

    assert (
        result.recommended_capability[
            "status"
        ]
        == "EXTERNAL_CANONICAL_OWNER"
    )

    assert (
        result.recommended_capability[
            "owner"
        ]
        == "optimization_runtime"
    )

    assert result.production_authority is False
    assert result.route_applied is False
    assert result.execution_performed is False
