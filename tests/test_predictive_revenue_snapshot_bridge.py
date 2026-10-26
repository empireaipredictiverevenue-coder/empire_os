import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os.predictive_cloud_core_jev_observer import SOURCES
from empire_os.predictive_revenue_demo import _intelligence_snapshot_evidence
from empire_os.predictive_revenue_demo_api import create_predictive_revenue_demo_router

NOW = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)


def snapshots(root, **overrides):
    for name, (relative, schema, clock) in SOURCES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": schema, "mode": "OBSERVE",
                   "execution_authority": "none", clock: NOW.isoformat(),
                   "tenant_id": "private-tenant", "product_estimates": [{"private": "secret"}]}
        payload.update(overrides)
        path.write_text(json.dumps(payload))


def test_original_sources_keep_exact_digest_clock_and_no_tenant_data(tmp_path):
    snapshots(tmp_path)
    result = _intelligence_snapshot_evidence(tmp_path, NOW)
    assert len(result["sources"]) == 3
    for row in result["sources"]:
        assert row["state"] == "OBSERVED"
        assert row["snapshot_generated_at"] == NOW.isoformat()
        assert row["snapshot_digest"] == hashlib.sha256((tmp_path / row["evidence_ref"]).read_bytes()).hexdigest()
    assert "private-tenant" not in json.dumps(result)
    assert "secret" not in json.dumps(result)
    assert result["forecast_state"] == "HOLD"
    assert result["execution_authority"] == "none"
    assert result == _intelligence_snapshot_evidence(tmp_path, NOW)


@pytest.mark.parametrize("change,state", [
    ({"mode": "LIVE"}, "HOLD"),
    ({"execution_authority": "trade"}, "HOLD"),
    ({"schema_version": "forged"}, "HOLD"),
    ({"generated_at": "invalid", "generated_at_utc": "invalid"}, "UNKNOWN"),
    ({"generated_at": "2026-10-26T10:00:00", "generated_at_utc": "2026-10-26T10:00:00"}, "UNKNOWN"),
    ({"generated_at": (NOW + timedelta(days=1)).isoformat(), "generated_at_utc": (NOW + timedelta(days=1)).isoformat()}, "UNKNOWN"),
    ({"generated_at": (NOW - timedelta(days=3)).isoformat(), "generated_at_utc": (NOW - timedelta(days=3)).isoformat()}, "STALE"),
])
def test_bad_contracts_and_clocks_never_become_observed(tmp_path, change, state):
    snapshots(tmp_path, **change)
    result = _intelligence_snapshot_evidence(tmp_path, NOW)
    assert {row["state"] for row in result["sources"]} == {state}
    assert result["forecast_state"] == "HOLD"


def test_missing_and_malformed_are_distinct(tmp_path):
    result = _intelligence_snapshot_evidence(tmp_path, NOW)
    assert {row["state"] for row in result["sources"]} == {"NO_SOURCE"}
    snapshots(tmp_path)
    for relative, _, _ in SOURCES.values():
        (tmp_path / relative).write_text("{bad-json")
    result = _intelligence_snapshot_evidence(tmp_path, NOW)
    assert {row["state"] for row in result["sources"]} == {"UNAVAILABLE"}


def test_forged_readiness_does_not_enable_forecast_or_cash(tmp_path):
    snapshots(tmp_path, verified=True, model_accuracy=1, recognized_revenue_cents=1000000)
    result = _intelligence_snapshot_evidence(tmp_path, NOW)
    assert result["forecast_state"] == "HOLD"
    assert result["economic_verification"] == "UNKNOWN"
    assert result["source_rights_verification"] == "UNKNOWN"


def test_existing_api_exposes_same_contract_without_writes(tmp_path):
    snapshots(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    app = FastAPI()
    app.include_router(create_predictive_revenue_demo_router(tmp_path))
    client = TestClient(app)
    result = client.get("/v1/predictive-revenue/demo").json()
    evidence = result["intelligence_snapshot_evidence"]
    assert result["generated_at"] == evidence["generated_at"]
    assert evidence["scope"] == "SYSTEM_AGGREGATE_METADATA_ONLY"
    assert {p: p.read_bytes() for p in tmp_path.rglob("*.json")} == before
    assert client.post("/v1/predictive-revenue/demo").status_code == 405


@pytest.mark.parametrize("value", [None, True, "0", "bad", 0.5])
def test_absent_or_invalid_cash_does_not_become_zero(tmp_path, value):
    from empire_os.predictive_revenue_demo import build_predictive_revenue_demo
    path = tmp_path / "runtime/revenue_pulse/latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"recognized_revenue_truth": {"recognized_revenue_cents": value}}))
    result = build_predictive_revenue_demo(tmp_path)
    assert result["revenue_truth"]["recognized_revenue_cents"] is None
    assert result["revenue_truth"]["actual_revenue"] is None
    assert result["proof_chain"][-1]["observed"] is None


def test_explicit_zero_cash_is_preserved(tmp_path):
    from empire_os.predictive_revenue_demo import build_predictive_revenue_demo
    path = tmp_path / "runtime/revenue_pulse/latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"recognized_revenue_truth": {"recognized_revenue_cents": 0}}))
    result = build_predictive_revenue_demo(tmp_path)
    assert result["revenue_truth"]["recognized_revenue_cents"] == 0
    assert result["revenue_truth"]["actual_revenue"] is False
