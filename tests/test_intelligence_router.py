from types import SimpleNamespace

from empire_os.intelligence_router import (
    intelligence_architecture,
    preview_intelligence_route,
)


def test_quant_tasks_route_to_deterministic_quant():
    result = preview_intelligence_route(
        task="monte_carlo",
        messages=[],
    )
    assert result["engine"] == "quant_brain"
    assert result["intelligence_class"] == "deterministic_quant"
    assert result["authority_inherited_from_intelligence"] is False
    assert result["execution_authority"] == "none"


class FakeRouter:
    def __init__(self, *, provider="ollama", reasoning=False, route=None):
        self.provider = provider
        self.reasoning = reasoning
        self.route_name = route or (
            "ROUTE_REASONING" if reasoning else "ROUTE_NONREASONING"
        )

    def route(self, **kwargs):
        model = SimpleNamespace(
            provider=self.provider,
            model="test-model",
            model_id=f"{self.provider}:test-model",
            reasoning=self.reasoning,
            vision=False,
        )
        return SimpleNamespace(
            model=model,
            route=self.route_name,
            candidates=(model.model_id,),
            rationale="test",
        )


def test_local_model_classification():
    result = preview_intelligence_route(
        task="classification",
        messages=[{"role": "user", "content": "classify this"}],
        router=FakeRouter(provider="ollama", reasoning=False),
    )
    assert result["intelligence_class"] == "local_fast"
    assert result["engine"] == "llm_gateway"


def test_frontier_reasoning_classification():
    result = preview_intelligence_route(
        task="reasoning",
        messages=[{"role": "user", "content": "complex strategy"}],
        router=FakeRouter(provider="gemini", reasoning=True),
    )
    assert result["intelligence_class"] == "frontier_reasoning"
    assert result["reasoning"] is True
    assert result["execution_authority"] == "none"


def test_future_slots_are_compatibility_not_availability_claims():
    architecture = intelligence_architecture()
    assert "future_general_intelligence" in architecture["classes"]
    assert "future_superintelligence" in architecture["classes"]
    assert architecture[
        "future_intelligence_currently_claimed_available"
    ] is False
    assert architecture["model_provider_agnostic"] is True
