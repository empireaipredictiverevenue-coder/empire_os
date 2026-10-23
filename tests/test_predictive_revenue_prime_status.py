"""Founder PRIME read route: aggregate-only, fail-closed, no raw commercial rows."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.predictive_cloud_status_api import create_predictive_cloud_status_router
from empire_os.predictive_revenue_prime_status import read_prime_founder_status

NOW = datetime(2026, 10, 23, 22, tzinfo=timezone.utc)


def _root(tmp_path, *, invalid=False):
    stormdir = tmp_path / "runtime" / "storm_opportunity"
    stormdir.mkdir(parents=True)
    storms = {
        "schema_version": "empire.storm_opportunity_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": (NOW - timedelta(days=2)).isoformat(),
        "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "candidates": [],
        "candidate_count": 0,
        "secret_account_name": "never-expose-personal-data",
    }
    if invalid:
        storms["execution_authority"] = "execute_bounded"
    (stormdir / "latest.json").write_text(json.dumps(storms))
    inbox = tmp_path / "runtime" / "acquisition"
    inbox.mkdir(parents=True)
    (inbox / "signal_inbox.json").write_text("{}")
    return tmp_path


def test_private_route_contract_is_readonly_aggregate_and_no_raw_records(tmp_path):
    root = _root(tmp_path)
    service = FastAPI()
    service.include_router(create_predictive_cloud_status_router(
        tmp_path / "status.json", prime_repo_root=root,
    ))
    client = TestClient(service)
    res = client.get("/v1/predictive-cloud/prime/status")
    assert res.status_code == 200
    row = res.json()
    assert row["schema_version"] == "empire.predictive_revenue.prime_source_review.v2"
    assert row["storm_snapshot_available"] is True
    assert row["storm_snapshot_freshness"] == "STALE"
    assert row["storm_opportunity_count"] == 0
    assert row["permit_observation_count"] == 0
    assert row["crm_status"] == "NOT_CONNECTED_NOT_A_VERIFIED_ZERO"
    assert row["realized_revenue_cents"] is None
    assert row["revenue_verified"] is False
    assert row["database_writes"] is False
    assert row["outbound_sent"] is False
    assert row["execution_authority"] == "none"
    assert "never-expose" not in res.text
    assert "tenant_id" not in res.text


def test_invalid_storm_source_does_not_become_fake_zero(tmp_path):
    status = read_prime_founder_status(
        repo_root=_root(tmp_path, invalid=True), as_of=NOW,
    )
    assert status["status"] == "READ_ONLY_SOURCE_REVIEW_UNAVAILABLE"
    assert status["storm_opportunity_count"] is None
    assert status["permit_observation_count"] is None
    assert status["revenue_verified"] is False
    assert status["execution_authority"] == "none"


def test_missing_sources_are_reported_not_guessed(tmp_path):
    status = read_prime_founder_status(repo_root=tmp_path, as_of=NOW)
    assert status["storm_snapshot_available"] is False
    assert status["storm_snapshot_freshness"] == "NOT_CONNECTED"
    assert status["permit_observation_count"] == 0
    assert "signal_inbox_unavailable" in status["permit_source_blockers"]
    assert status["crm_status"] == "NOT_CONNECTED_NOT_A_VERIFIED_ZERO"


def test_synthetic_source_cannot_advertise_outbound_or_payments(tmp_path):
    root = _root(tmp_path)
    candidate = {
        "tenant_id": "empire-internal",
        "opportunity_key": "synth:1", "event_id": "synth",
        "evaluated_at": (NOW - timedelta(minutes=1)).isoformat(),
        "event_truth_class": "OBSERVED",
        "evidence_refs": ["source:claimed"], "execution_authority": "execute_bounded",
        "payment_authority": "execute_bounded",
    }
    path = root / "runtime" / "storm_opportunity" / "latest.json"
    snapshot = json.loads(path.read_text())
    snapshot["candidates"] = [candidate]
    path.write_text(json.dumps(snapshot))
    status = read_prime_founder_status(repo_root=root, as_of=NOW)
    assert status["status"] == "READ_ONLY_SOURCE_REVIEW_UNAVAILABLE"
    assert status["revenue_verified"] is False
    assert status["realized_revenue_cents"] is None
