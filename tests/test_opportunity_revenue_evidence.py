from copy import deepcopy
from datetime import datetime

import pytest

from empire_os.opportunity_radar import build_opportunity_radar
from empire_os.opportunity_revenue_evidence import FACTORS
from empire_os.predictive_revenue_formula import predictive_revenue_formula

NOW = "2026-09-28T12:00:00+00:00"
KEY = "market:roofing:denver"


def observation(factor="demand", value=0.5):
    return dict(opportunity_key=KEY, factor=factor, value=value,
                observed_at=NOW, evidence_refs=["canonical:observation:1"],
                semantic_class="predictive_revenue_factor")


def source():
    return dict(generated_at=NOW, research_queue=[dict(
        opportunity_key=KEY, niche="roofing", metro="denver",
        research_priority_score=99, evidence_refs=["canonical:market:1"],
        predictive_revenue_observations=[observation()])])


def build(data):
    return build_opportunity_radar(market_gps=data, community_intent=None,
                                   competitor_market=None, generated_at=NOW)


def test_partial_evidence_is_partial_and_unknown_with_no_authority():
    result = build(source())
    row = result["candidates"][0]
    assert row["predictive_revenue_inputs"] == {"demand": 0.5}
    assert row["predictive_revenue_evidence_refs"] == {"demand": ["canonical:observation:1"]}
    formula = predictive_revenue_formula(row["predictive_revenue_inputs"])
    assert formula["status"] == "UNAVAILABLE"
    assert set(formula["missing_fields"]) == set(FACTORS) - {"demand"}
    assert formula["actual_revenue"] is False
    assert "ltv_cents" not in row["predictive_revenue_inputs"]
    assert result["mode"] == "OBSERVE"
    assert result["automatic_external_execution_allowed"] is False
    for field in ("outreach_authority", "commercial_authority", "payment_authority",
                  "revenue_recognition_authority", "execution_authority"):
        assert result[field] == "none"


@pytest.mark.parametrize("stamp", [None, "2026-09-17T00:00:00+00:00", "2026-09-29T00:00:00+00:00", "2026-09-28T12:00:00"])
@pytest.mark.parametrize("where", ["source", "observation"])
def test_stale_unknown_naive_future_evidence_rejected(stamp, where):
    data = source()
    if where == "source":
        data["generated_at"] = stamp
    else:
        data["research_queue"][0]["predictive_revenue_observations"][0]["observed_at"] = stamp
    assert build(data)["candidates"][0]["predictive_revenue_inputs"] == {}


@pytest.mark.parametrize("change", ["duplicate_row", "duplicate_factor", "wrong_opportunity", "no_refs", "proxy", "no_identity"])
def test_ambiguous_unrelated_unsupported_observations_rejected(change):
    data = source()
    row = data["research_queue"][0]
    obs = row["predictive_revenue_observations"][0]
    if change == "duplicate_row":
        data["research_queue"].append(deepcopy(row))
    elif change == "duplicate_factor":
        row["predictive_revenue_observations"].append(deepcopy(obs))
    elif change == "wrong_opportunity":
        obs["opportunity_key"] = "market:other:elsewhere"
    elif change == "no_refs":
        obs["evidence_refs"] = []
    elif change == "proxy":
        obs["semantic_class"] = "modeled_proxy"
    else:
        row.pop("opportunity_key")
    assert all(r["predictive_revenue_inputs"] == {} for r in build(data)["candidates"])


@pytest.mark.parametrize("factor", FACTORS)
@pytest.mark.parametrize("value", [-1, True, "0.5", float("nan"), float("inf"), None])
def test_invalid_values_never_emitted(factor, value):
    data = source()
    data["research_queue"][0]["predictive_revenue_observations"] = [observation(factor, value)]
    assert build(data)["candidates"][0]["predictive_revenue_inputs"] == {}


@pytest.mark.parametrize("factor", FACTORS)
def test_each_explicit_factor_preserves_value_and_refs(factor):
    data = source()
    data["research_queue"][0]["predictive_revenue_observations"] = [observation(factor, 0)]
    row = build(data)["candidates"][0]
    assert row["predictive_revenue_inputs"] == {factor: 0}
    assert row["predictive_revenue_evidence_refs"][factor]


def test_priority_capacity_visibility_policy_price_are_not_factors():
    data = source()
    row = data["research_queue"][0]
    row.pop("predictive_revenue_observations")
    row.update(buyer_capacity={"buyer_id": "unrelated", "capacity": 100},
               observed_search_presence_share=1, pilot_price_cents=100000,
               normalized_signals={"demand": 0.9}, ltv_cents=100000)
    candidate = build(data)["candidates"][0]
    assert candidate["predictive_revenue_inputs"] == {}
    assert candidate["predictive_revenue_evidence_refs"] == {}


def test_probability_above_one_rejected():
    data = source()
    data["research_queue"][0]["predictive_revenue_observations"] = [observation(value=1.01)]
    assert build(data)["candidates"][0]["predictive_revenue_inputs"] == {}


@pytest.mark.parametrize("flag", ["available", "ok"])
def test_unavailable_producer_cannot_supply_factors(flag):
    data = source()
    data[flag] = False
    assert build(data)["candidates"][0]["predictive_revenue_inputs"] == {}
