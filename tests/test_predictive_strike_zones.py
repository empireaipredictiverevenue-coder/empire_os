from copy import deepcopy
from datetime import datetime, timezone
from itertools import permutations

import pytest

from empire_os.commercial_opportunity_decay import assess_opportunity_decay
from empire_os.predictive_strike_zones import project_predictive_strike_zones


def candidate(key="market:1", ev=100):
    return {
        "opportunity_key": key,
        "expected_revenue_value_cents": ev,
        "erv_evidence_ref": "erv:1",
        "decay_state": "ACTIVE",
        "buyer_capacity_remaining": 2,
        "buyer_capacity_evidence_ref": "capacity:1",
        "evidence_refs": ["market-observation:1"],
    }


def project(row):
    return project_predictive_strike_zones([row])["rows"][0]


def test_ranking_uses_only_ev_with_deterministic_identity_ties():
    rows = [candidate("b", 100), candidate("a", 100), candidate("c", 200)]
    rows[0].update(research_priority_score=999, pilot_price_cents=999999)
    for order in permutations(rows):
        ranked = project_predictive_strike_zones(order)["ranked_candidates"]
        assert [row["opportunity_key"] for row in ranked] == ["c", "a", "b"]
        assert [row["rank"] for row in ranked] == [1, 2, 3]


def test_price_and_other_revenue_never_replace_missing_ev():
    row = candidate()
    del row["expected_revenue_value_cents"]
    row.update(pilot_price_cents=100000, predicted_revenue_cents=20000,
               recognized_revenue_cents=30000, research_priority_score=100)
    result = project(row)
    assert result["status"] == "UNKNOWN"
    assert result["expected_revenue_value_cents"] is None
    assert result["rank"] is None


@pytest.mark.parametrize("field", [
    "opportunity_key", "erv_evidence_ref", "buyer_capacity_evidence_ref",
    "evidence_refs", "buyer_capacity_remaining", "decay_state",
])
def test_missing_required_input_is_unknown(field):
    row = candidate()
    del row[field]
    result = project(row)
    assert result["status"] == "UNKNOWN"
    assert result["blockers"]
    assert result["rank"] is None


@pytest.mark.parametrize("field", ["expected_revenue_value_cents", "buyer_capacity_remaining"])
@pytest.mark.parametrize("value", [True, False, "100", float("nan"), float("inf"), -float("inf"), {}, None])
def test_invalid_numbers_fail_closed(field, value):
    row = candidate()
    row[field] = value
    assert project(row)["status"] == "UNKNOWN"


@pytest.mark.parametrize("field", ["expected_revenue_value_cents", "buyer_capacity_remaining"])
@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_ev_or_capacity_blocks(field, value):
    row = candidate()
    row[field] = value
    result = project(row)
    assert result["status"] == "BLOCKED"
    assert result["rank"] is None


@pytest.mark.parametrize("state,status", [
    ("STALE", "BLOCKED"), ("EXPIRED", "BLOCKED"),
    ("UNKNOWN", "UNKNOWN"), ("invented", "UNKNOWN"),
])
def test_decay_gate(state, status):
    row = candidate()
    row["decay_state"] = state
    assert project(row)["status"] == status


@pytest.mark.parametrize("value", [None, True, 12, {}, "", "  "])
@pytest.mark.parametrize("field", ["opportunity_key", "erv_evidence_ref", "buyer_capacity_evidence_ref"])
def test_invalid_text_cannot_become_evidence_or_identity(field, value):
    row = candidate()
    row[field] = value
    assert project(row)["status"] == "UNKNOWN"


@pytest.mark.parametrize("value", ["source:1", [None, False, {}, " "]])
def test_invalid_market_evidence_fails_closed(value):
    row = candidate()
    row["evidence_refs"] = value
    assert project(row)["status"] == "UNKNOWN"


def test_all_duplicate_copies_block_even_if_one_is_incomplete():
    duplicate = candidate(" market:1 ", None)
    result = project_predictive_strike_zones([candidate(), duplicate, candidate("market:2")])
    assert [row["opportunity_key"] for row in result["ranked_candidates"]] == ["market:2"]
    for row in result["rows"][:2]:
        assert row["status"] == "BLOCKED"
        assert "duplicate_opportunity_key" in row["blockers"]
        assert row["rank"] is None


def test_existing_decay_owner_output_can_be_projected():
    row = candidate()
    decay = assess_opportunity_decay({
        "opportunity_key": row["opportunity_key"],
        "source_expires_at": "2026-10-02T00:00:00Z",
        "evidence_refs": row["evidence_refs"],
    }, as_of=datetime(2026, 10, 1, tzinfo=timezone.utc))
    row["decay_state"] = decay.state
    assert project(row)["status"] == "STRIKE_CANDIDATE"


def test_pure_projection_and_authority_cannot_be_overridden():
    row = candidate()
    row.update(execution_authority="live", allocation=True, outbound=True,
               crawler_execution=True, ad_spend=True, revenue_recognition=True)
    before = deepcopy(row)
    result = project_predictive_strike_zones([row])
    assert row == before
    for output in [result, *result["rows"], *result["ranked_candidates"]]:
        assert output["mode"] == "OBSERVE"
        assert output["execution_authority"] == "none"
        assert output["recommendation_only"] is True
        for field in ("allocation", "outbound", "crawler_execution", "ad_spend",
                      "revenue_recognition", "actual_revenue"):
            assert output[field] is False
        assert not any("probability" in key or "score" in key for key in output)
    result["rows"][0]["evidence_refs"].append("other")
    assert row == before


def test_empty_projection():
    result = project_predictive_strike_zones([])
    assert result["rows"] == result["ranked_candidates"] == []
