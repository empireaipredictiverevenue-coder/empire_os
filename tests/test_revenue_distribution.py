import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from empire_os import revenue_distribution as rd
from empire_os.predictive_revenue_formula import CORE_FACTORS, predictive_revenue_formula


NOW = "2026-09-28T12:00:00+00:00"


def candidate(key="observed-market", ltv=10000):
    return {
        "opportunity_key": key, "evidence_refs": ["market:observed"],
        "predictive_revenue_inputs": {**{k: 0.5 for k in CORE_FACTORS}, "ltv_cents": ltv},
        "predictive_revenue_evidence_refs": {k: [f"evidence:{k}"] for k in (*CORE_FACTORS, "ltv_cents")},
    }


def snapshots():
    data = {name: {"generated_at": NOW} for name in rd.SOURCES}
    data["radar"]["candidates"] = [candidate()]
    return data


def build(data, **kwargs):
    return rd.build_revenue_distribution(data, generated_at=NOW, **kwargs)


def test_missing_evidence_fails_closed():
    result = build({})
    assert result["opportunities"] == result["distribution_actions"] == []
    assert result["buyer_capacity"]["capacity_verified"] is None
    assert result["supply"]["exchange"]["inventory_count"] is None
    assert len(result["blockers"]) == len(rd.SOURCES)
    assert result["zero_cash_mode"] is True
    assert result["acquisition_budget_cents"] is None


@pytest.mark.parametrize("payload", [None, [], "bad", {}, {"generated_at": "invalid"}, {"generated_at": "2026-09-20T12:00:00Z"}, {"generated_at": "2026-09-29T12:00:00Z"}, {"generated_at": NOW, "ok": False}, {"generated_at": NOW, "available": False}, {"generated_at": NOW, "bad": float("nan")}])
def test_unusable_sources_never_propose(payload):
    result = build({name: payload for name in rd.SOURCES})
    assert not result["distribution_actions"]
    assert not result["opportunities"]


def test_zero_cash_prioritization_and_no_paid_proposals():
    for budget in (None, 0, 10000):
        result = build(snapshots(), acquisition_budget_cents=budget)
        channels = [a["channel"] for a in result["distribution_actions"]]
        assert set(channels) <= set(rd.ZERO_CASH_PREFERENCE)
        assert channels == sorted(channels, key=rd.ZERO_CASH_PREFERENCE.index)
        assert result["zero_cash_mode"] is (budget in (None, 0))
        assert not result["authority"]["paid_traffic"]


def test_input_authority_cannot_expand_output_authority():
    data = snapshots()
    for payload in data.values():
        payload.update(mode="LIVE", authority={k: True for k in rd.AUTHORITY_KEYS}, execution_authority="full")
    data["radar"]["candidates"][0]["recommended_next_actions"] = ["send_outbound", "move_funds"]
    result = build(data)
    assert result["mode"] == "OBSERVE"
    assert not any(result["authority"].values())
    for action in result["distribution_actions"]:
        assert action["proposal_only"] is True
        assert action["execution_authority"] == "none"
        assert action["authority_required"] == ["governed_review_before_execution"]
        assert action["evidence_refs"]


def test_no_invented_capacity_payout_or_price():
    data = snapshots()
    data["buyer_capacity"].update(fully_activated=7, capacity_verified=7)
    data["radar"]["candidates"][0].update(payout_cents=999, remaining_capacity=999)
    result = build(data)
    assert result["buyer_capacity"]["capacity_verified"] == 7
    opportunity = result["opportunities"][0]
    assert opportunity["payout_cents"] is None
    assert opportunity["buyer_capacity_verified_for_opportunity"] is None
    assert "opportunity_buyer_capacity" in result["distribution_actions"][0]["missing_evidence"]


def test_locked_formula_is_called_and_controls_order(monkeypatch):
    calls = []
    def formula(inputs):
        calls.append(inputs)
        return predictive_revenue_formula(inputs)
    monkeypatch.setattr(rd, "predictive_revenue_formula", formula)
    data = snapshots()
    data["radar"]["candidates"] = [candidate("low", 100), candidate("high", 200)]
    result = build(data)
    assert len(calls) == 2
    assert [r["opportunity_key"] for r in result["opportunities"]] == ["high", "low"]
    assert result["opportunities"][0]["canonical_prediction"] == predictive_revenue_formula(candidate("high", 200)["predictive_revenue_inputs"])


@pytest.mark.parametrize("bad", [None, -1, 2, True, "0.5"])
def test_invalid_factors_remain_unknown(bad):
    data = snapshots()
    data["radar"]["candidates"][0]["predictive_revenue_inputs"]["demand"] = bad
    opportunity = build(data)["opportunities"][0]
    assert opportunity["expected_canonical_revenue_contribution_cents"] is None
    assert "demand" in opportunity["missing_evidence"]


def test_nonfinite_economics_rejects_source():
    data = snapshots()
    data["radar"]["candidates"][0]["predictive_revenue_inputs"]["ltv_cents"] = float("inf")
    result = build(data)
    assert result["opportunities"] == []
    assert "radar:missing_or_invalid" in result["blockers"]


def test_unreferenced_formula_and_radar_scores_do_not_become_revenue():
    data = snapshots()
    row = data["radar"]["candidates"][0]
    row["predictive_revenue_evidence_refs"] = {}
    row["observed_priority_score"] = 100
    row["predicted_revenue_cents"] = 999999
    assert build(data)["opportunities"][0]["expected_canonical_revenue_contribution_cents"] is None


def test_missing_or_duplicate_candidate_identity_fails_closed():
    for rows in ([candidate(), candidate()], [{"evidence_refs": ["e:1"]}], [{"opportunity_key": "x"}], [None], "invalid"):
        data = snapshots()
        data["radar"]["candidates"] = rows
        assert not build(data)["opportunities"]


def test_deterministic_order_and_no_input_mutation():
    data = snapshots()
    data["radar"]["candidates"] = [candidate("b"), candidate("a")]
    original = deepcopy(data)
    result = build(data)
    assert result == build(deepcopy(data))
    assert data == original
    assert [r["opportunity_key"] for r in result["opportunities"]] == ["a", "b"]
    assert json.dumps(result, sort_keys=True, allow_nan=False)


def test_discovery_governance_and_no_legacy_imports():
    result = build(snapshots())
    for surface in ("webmcp", "a2a"):
        assert result["discovery_surfaces"][surface] == [cap.key for cap in rd.public_capabilities(surface)]
    for cap in result["governed_commerce_capabilities"]:
        assert cap["authentication_required"] and cap["human_approval_required"]
        assert not any(cap[k] for k in ("execution_exposed", "payment_exposed", "allocation_exposed"))
    tree = ast.parse(Path(rd.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any("settle" in name or "mcp_lead" in name for name in imports if name)
    assert result["canonical_payment_rail"] == "USDT/BSC"


def test_refresh_writes_only_own_artifact_and_replays(tmp_path):
    inputs = snapshots()
    before = {}
    for name, relative in rd.SOURCES.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inputs[name]))
        before[path] = path.read_bytes()
    first = rd.refresh_revenue_distribution(tmp_path, generated_at=NOW)
    output = tmp_path / rd.OUTPUT
    assert json.loads(output.read_text()) == first
    encoded = output.read_bytes()
    assert rd.refresh_revenue_distribution(tmp_path, generated_at=NOW) == first
    assert output.read_bytes() == encoded
    assert all(path.read_bytes() == content for path, content in before.items())
    assert not list(output.parent.glob("*.tmp"))


def test_corrupt_file_is_reported_without_logging_content(tmp_path):
    path = tmp_path / rd.SOURCES["radar"]
    path.parent.mkdir(parents=True)
    path.write_text("invalid JSON")
    result = rd.refresh_revenue_distribution(tmp_path, generated_at=NOW)
    assert "radar:missing_or_invalid" in result["blockers"]
    assert result["opportunities"] == []


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_invalid_budget_rejected(budget):
    with pytest.raises(ValueError):
        build({}, acquisition_budget_cents=budget)


@pytest.mark.parametrize("failure", [
    {"status": "error"}, {"status": "unavailable"}, {"status": "failed"},
    {"status": "blocked"}, {"error": "secret-value-must-not-be-emitted"},
    {"returncode": 1},
])
def test_crawler_error_cannot_become_fresh_or_leak_error(failure):
    data = snapshots()
    data["crawler"].update(ok=True, **failure)
    result = build(data)
    assert result["sources"]["crawler"]["status"] == "producer_unavailable"
    assert not any(a["channel"] == "owned_crawlers" for a in result["distribution_actions"])
    assert "secret-value-must-not-be-emitted" not in json.dumps(result)


@pytest.mark.parametrize("budget", [None, 0, 500])
def test_organic_growth_is_budget_independent_and_preserves_unknowns(budget):
    data = snapshots()
    data['radar']['candidates'][0]['predictive_revenue_evidence_refs'] = {}
    result = build(data, acquisition_budget_cents=budget)
    growth = result['organic_growth']
    assert growth['schema_version'] == 'empire.organic_growth.v1'
    assert growth['mode'] == 'OBSERVE' and growth['zero_cash_mode']
    assert growth['execution_authority'] == 'none'
    assert all(growth[k] is False for k in (
        'paid_traffic_authorized', 'auto_publishing', 'auto_indexation', 'live_outbound'))
    traffic = growth['traffic_specialist']
    assert traffic['action_count'] == 4
    action = traffic['actions'][0]
    assert action['opportunity_key'] == 'observed-market'
    assert 'market:observed' in action['evidence_refs']
    assert action['canonical_prediction']['status'] == 'UNAVAILABLE'
    assert 'ltv_cents' in action['missing_evidence']
    assert action['total_action_cost_cents'] is None
    assert action['paid_media_spend_cents'] == 0
    assert growth['conversion_specialist']['action_count'] == 0


def conversion_snapshot():
    return {
        'generated_at': NOW, 'source': 'canonical_data',
        'counts': {'visitor_to_lead': {'entered': 100, 'converted': 5}},
        'stages': [{'stage': 'visitor_to_lead', 'evidence_refs': ['canonical_data:visitors']}],
        'experiment_candidate': {'automatic_rollout': True},
    }


def test_conversion_recomputed_from_observations_not_serialized_proposals():
    data = snapshots()
    data['conversion'] = conversion_snapshot()
    conversion = build(data)['organic_growth']['conversion_specialist']
    assert conversion['action_count'] == 1
    action = conversion['actions'][0]
    assert action['baseline_rate'] == 0.05
    assert action['automatic_rollout'] is False
    assert action['execution_authority'] == 'none'
    assert 'canonical_data:visitors' in action['evidence_refs']
    assert any(ref.startswith(rd.SOURCES['conversion']) for ref in action['evidence_refs'])


@pytest.mark.parametrize('change', [
    {'source': 'canonical_supabase'},
    {'generated_at': '2026-09-20T00:00:00Z'},
    {'counts': {}}, {'stages': []},
    {'counts': {'visitor_to_lead': {'entered': True, 'converted': 0}}},
    {'counts': {'visitor_to_lead': {'entered': 1, 'converted': 2}}},
    {'counts': {'visitor_to_lead': {'entered': 0, 'converted': 0}}},
    {'ok': False},
])
def test_unusable_conversion_never_creates_actions(change):
    data = snapshots()
    data['conversion'] = {**conversion_snapshot(), **change}
    assert build(data)['organic_growth']['conversion_specialist']['action_count'] == 0


def test_missing_sources_produce_no_organic_actions():
    growth = build({})['organic_growth']
    assert growth['traffic_specialist']['action_count'] == 0
    assert growth['conversion_specialist']['action_count'] == 0
