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
