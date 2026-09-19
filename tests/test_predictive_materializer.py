import pytest

from empire_os.predictive_materializer import materialize_daily_actuals


def rows(values):
    return [
        {
            "snapshot_date": f"2026-09-{index + 1:02d}",
            "actual_revenue_cents": value,
            "source": "canonical_phase3f_daily_actuals",
        }
        for index, value in enumerate(values)
    ]


def test_materializer_builds_forecast_from_canonical_actuals_only():
    result = materialize_daily_actuals(
        metric="actual_revenue_cents",
        rows=rows([100, 120, 140, 160, 180, 200, 220]),
        value_field="actual_revenue_cents",
        date_field="snapshot_date",
        horizon_days=3,
    )
    assert len(result.observations) == 7
    assert result.forecast.available is True
    assert result.forecast.direction == "up"
    assert result.forecast.predicted_value == 280.0
    assert result.write_authority == "none"


def test_short_actual_history_stays_insufficient():
    result = materialize_daily_actuals(
        metric="actual_revenue_cents",
        rows=rows([100, 120, 140]),
        value_field="actual_revenue_cents",
        date_field="snapshot_date",
        horizon_days=7,
    )
    assert result.forecast.available is False
    assert result.forecast.direction == "insufficient_history"


def test_missing_source_provenance_fails_closed():
    data = rows([100])
    data[0]["source"] = ""
    with pytest.raises(ValueError, match="source provenance"):
        materialize_daily_actuals(
            metric="actual_revenue_cents",
            rows=data,
            value_field="actual_revenue_cents",
            date_field="snapshot_date",
            horizon_days=7,
        )


def test_conflicting_actuals_for_same_day_are_rejected():
    data = rows([100])
    data.append({
        "snapshot_date": "2026-09-01",
        "actual_revenue_cents": 200,
        "source": "canonical_reconciled_actuals",
    })
    with pytest.raises(ValueError, match="conflicting canonical actuals"):
        materialize_daily_actuals(
            metric="actual_revenue_cents",
            rows=data,
            value_field="actual_revenue_cents",
            date_field="snapshot_date",
            horizon_days=7,
        )


def test_identical_duplicate_actual_is_deduplicated():
    data = rows([100, 120, 140, 160, 180, 200, 220])
    data.append(dict(data[-1]))
    result = materialize_daily_actuals(
        metric="actual_revenue_cents",
        rows=data,
        value_field="actual_revenue_cents",
        date_field="snapshot_date",
        horizon_days=1,
    )
    assert len(result.observations) == 7
