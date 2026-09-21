from empire_os.timesfm_shadow import (
    DisabledTimesFmProvider,
    TimesFm25LocalProvider,
)


def test_disabled_provider_fails_closed():
    provider = DisabledTimesFmProvider()
    result = provider.forecast(
        metric="search_clicks",
        values=[1, 2, 3, 4, 5, 6, 7],
        horizon_steps=7,
    )
    assert result.available is False
    assert result.point_forecast == ()
    assert result.execution_authority == "none"
    assert result.creates_actuals is False


def test_local_provider_short_history_does_not_load_model():
    provider = TimesFm25LocalProvider(max_horizon=30)
    result = provider.forecast(
        metric="search_clicks",
        values=[1, 2, 3],
        horizon_steps=7,
    )
    assert result.available is False
    assert result.reason == "minimum_7_observations_required"
    assert provider._model is None
