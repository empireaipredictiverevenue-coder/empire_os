from empire_os.model_registry import ModelSpec
from empire_os.model_router import ModelRouter


class Registry:
    def __init__(self, rows):
        self.rows = list(rows)

    def candidates(self, **kwargs):
        return list(self.rows)


def spec(
    model_id,
    *,
    quality,
    health="unknown",
    available=True,
    provider="test-provider",
):
    return ModelSpec(
        model_id=model_id,
        provider=provider,
        model=model_id,
        capabilities=frozenset({
            "general",
            "coding",
            "summarization",
        }),
        reasoning=False,
        vision=False,
        quality={
            "default": quality,
            "reasoning": quality,
        },
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        free=True,
        enabled=True,
        priority=10,
        pricing_known=True,
        available=available,
        health=health,
        deployment="local",
        allow_untrusted_input=True,
        max_stakes="critical",
    )


def route(router, **kwargs):
    return router.route(
        task="reasoning",
        messages=[
            {
                "role": "user",
                "content": "internal test",
            }
        ],
        **kwargs,
    )


def test_unavailable_is_not_selected():
    d = route(
        ModelRouter(
            Registry([
                spec(
                    "dead",
                    quality=0.99,
                    available=False,
                ),
                spec(
                    "good",
                    quality=0.70,
                ),
            ])
        )
    )

    assert d.model.model_id == "good"


def test_unhealthy_is_not_selected():
    d = route(
        ModelRouter(
            Registry([
                spec(
                    "dead",
                    quality=0.99,
                    health="unhealthy",
                ),
                spec(
                    "good",
                    quality=0.70,
                ),
            ])
        )
    )

    assert d.model.model_id == "good"


def test_unknown_health_remains_unknown_and_eligible():
    d = route(
        ModelRouter(
            Registry([
                spec(
                    "unknown",
                    quality=0.90,
                    health="unknown",
                ),
                spec(
                    "lower",
                    quality=0.70,
                ),
            ])
        )
    )

    assert d.model.model_id == "unknown"


def test_failed_model_can_be_excluded():
    d = route(
        ModelRouter(
            Registry([
                spec(
                    "first",
                    quality=0.95,
                ),
                spec(
                    "second",
                    quality=0.80,
                ),
            ])
        ),
        excluded_model_ids={
            "first"
        },
    )

    assert d.model.model_id == "second"


def test_failed_provider_can_be_excluded():
    d = route(
        ModelRouter(
            Registry([
                spec(
                    "first",
                    quality=0.95,
                    provider="blocked",
                ),
                spec(
                    "second",
                    quality=0.80,
                    provider="healthy",
                ),
            ])
        ),
        excluded_providers={
            "blocked"
        },
    )

    assert d.model.model_id == "second"


def test_degraded_model_with_sufficient_samples_is_not_route_eligible(tmp_path):
    import json
    from empire_os.model_registry import ModelRegistry
    from empire_os.model_router import ModelRouter

    registry_path = tmp_path / "registry.json"
    health_path = tmp_path / "health.json"

    registry_path.write_text(json.dumps({
        "models": [
            {
                "model_id": "bad",
                "provider": "test",
                "model": "bad-model",
                "capabilities": ["general"],
                "quality": {"default": 0.99},
                "free": True,
                "enabled": True
            },
            {
                "model_id": "good",
                "provider": "test",
                "model": "good-model",
                "capabilities": ["general"],
                "quality": {"default": 0.50},
                "free": True,
                "enabled": True
            }
        ]
    }))

    health_path.write_text(json.dumps({
        "models": {
            "test:bad-model": {
                "status": "degraded",
                "samples": 5,
                "successes": 0,
                "failures": 5
            },
            "test:good-model": {
                "status": "healthy",
                "samples": 5,
                "successes": 5,
                "failures": 0
            }
        }
    }))

    zen_path = tmp_path / "missing-zen-catalog.json"

    import os
    previous_zen = os.environ.get("EMPIRE_ZEN_CATALOG_CACHE")
    os.environ["EMPIRE_ZEN_CATALOG_CACHE"] = str(zen_path)

    try:
        registry = ModelRegistry(
            path=str(registry_path),
            health_path=str(health_path),
        )
    finally:
        if previous_zen is None:
            os.environ.pop("EMPIRE_ZEN_CATALOG_CACHE", None)
        else:
            os.environ["EMPIRE_ZEN_CATALOG_CACHE"] = previous_zen

    decision = ModelRouter(registry).route(
        task="reasoning",
        messages=[{"role": "user", "content": "Analyse this."}],
    )

    assert decision.model.model_id == "good"


def test_sparse_degraded_health_is_probationary_not_preferred():
    probation = spec(
        "probation",
        quality=0.90,
        health="degraded",
    )
    probation = __import__("dataclasses").replace(
        probation,
        metadata={
            "runtime_health_evidence": {
                "status": "degraded",
                "samples": 3,
                "successes": 1,
                "failures": 2,
                "success_rate": 0.3333,
            }
        },
    )

    proven = spec(
        "proven",
        quality=0.75,
        health="healthy",
    )
    proven = __import__("dataclasses").replace(
        proven,
        metadata={
            "runtime_health_evidence": {
                "status": "healthy",
                "samples": 10,
                "successes": 10,
                "failures": 0,
                "success_rate": 1.0,
            }
        },
    )

    d = route(ModelRouter(Registry([probation, proven])))

    assert d.model.model_id == "proven"
    assert "health=healthy_evidenced" in d.rationale


def test_probationary_model_remains_eligible_when_it_is_best_available():
    probation = spec(
        "probation",
        quality=0.90,
        health="degraded",
    )
    probation = __import__("dataclasses").replace(
        probation,
        metadata={
            "runtime_health_evidence": {
                "status": "degraded",
                "samples": 3,
                "successes": 1,
                "failures": 2,
            }
        },
    )

    lower = spec(
        "lower",
        quality=0.40,
        health="unknown",
    )

    d = route(ModelRouter(Registry([probation, lower])))

    assert d.model.model_id == "probation"
    assert "health=probation" in d.rationale
    assert "health_penalty=0.200" in d.rationale
