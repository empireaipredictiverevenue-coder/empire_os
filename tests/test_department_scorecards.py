from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.department_scorecards import KPIEvidence, build_department_scorecards
from empire_os.departments import default_departments

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
AGE = timedelta(hours=1)


def evidence(**changes):
    row = KPIEvidence(
        department_key="sales_revenue", kpi="recognized_revenue", current=80,
        observed_at=NOW, evidence_refs=("empiredb:commercial_events:fixture",),
        unit="USD", period="2026-10", truth_class="VERIFIED_OUTCOME",
        target=100, target_evidence_refs=("approved-plan:fixture",),
    )
    return replace(row, **changes)


def metric(rows=(), **kwargs):
    cards = build_department_scorecards(rows, now=NOW, max_age=AGE, **kwargs)
    return next(k for d in cards if d.department_key == "sales_revenue"
                for k in d.kpis if k.kpi == "recognized_revenue")


def test_evidenced_variance_and_serialization():
    row = metric([evidence()])
    assert (row.current, row.target, row.variance) == (80, 100, -20)
    assert (row.freshness, row.status, row.age_seconds) == ("FRESH", "KNOWN", 0)
    assert row.evidence_refs == evidence().evidence_refs
    assert row.target_evidence_refs == evidence().target_evidence_refs
    assert row.unknown_reasons == ()
    cards = build_department_scorecards([evidence()], now=NOW, max_age=AGE)
    assert '"authority": "OBSERVE"' in json.dumps(cards[0].as_dict(), allow_nan=False)


def test_registry_complete_and_no_ranking_or_invented_targets():
    cards = build_department_scorecards(now=NOW, max_age=AGE)
    assert [c.department_key for c in cards] == [d.key for d in default_departments()]
    for card, department in zip(cards, default_departments()):
        assert [k.kpi for k in card.kpis] == list(department.kpis)
        assert "rank" not in card.as_dict()
        for k in card.kpis:
            assert k.current is k.target is k.variance is None
            assert k.status == k.freshness == "UNKNOWN"


@pytest.mark.parametrize("changes", [
    {"current": None}, {"current": True}, {"current": float("nan")},
    {"current": float("inf")}, {"current": "80"},
    {"evidence_refs": ()}, {"evidence_refs": (" ",)},
    {"observed_at": None}, {"observed_at": NOW.replace(tzinfo=None)},
    {"observed_at": NOW + timedelta(seconds=1)}, {"truth_class": "FORECAST"},
])
def test_invalid_evidence_fails_closed(changes):
    row = metric([evidence(**changes)])
    assert row.current is row.variance is None
    assert row.status == "UNKNOWN"


def test_freshness_boundary_stale_and_recovery():
    assert metric([evidence(observed_at=NOW - AGE)]).freshness == "FRESH"
    row = metric([evidence(observed_at=NOW - AGE - timedelta(seconds=1))])
    assert row.freshness == "STALE"
    assert row.current is row.variance is None
    assert row.evidence_refs
    assert metric([evidence()]).status == "KNOWN"


@pytest.mark.parametrize("changes", [
    {"target": None}, {"target": float("nan")}, {"target": False},
    {"target_evidence_refs": ()}, {"unit": None}, {"period": None},
])
def test_unknown_comparison_preserves_observed_current(changes):
    row = metric([evidence(**changes)])
    assert row.current == 80
    assert row.variance is None
    assert row.status == "UNKNOWN"


def test_zero_is_observed_not_missing():
    row = metric([evidence(current=0, target=0)])
    assert (row.current, row.target, row.variance, row.status) == (0, 0, 0, "KNOWN")


def test_duplicate_rows_are_ambiguous():
    row = metric([evidence(), evidence(current=99)])
    assert row.current is row.target is row.variance is None
    assert "ambiguous_evidence" in row.unknown_reasons


def test_department_scope_does_not_leak_shared_kpis():
    cards = build_department_scorecards(
        [evidence(kpi="realized_gross_profit")], now=NOW, max_age=AGE,
    )
    strategy = next(c for c in cards if c.department_key == "strategy")
    assert next(k for k in strategy.kpis if k.kpi == "realized_gross_profit").current is None


def test_invalid_contract_rejected():
    with pytest.raises(ValueError):
        build_department_scorecards([evidence(department_key="invented")], max_age=AGE)
    with pytest.raises(ValueError):
        build_department_scorecards(max_age=timedelta(seconds=-1))
    with pytest.raises(ValueError):
        build_department_scorecards(max_age=AGE, now=NOW.replace(tzinfo=None))
    with pytest.raises(TypeError):
        build_department_scorecards([{}], max_age=AGE)
