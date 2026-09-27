from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.experiment_api import create_experiment_router
from empire_os.experiment_conclusion import ExperimentConclusionRecord
from empire_os.experiment_conclusion_registry_transport import (
    READ_SQL,
    READER_ROLE,
    RPC_NAME,
    WRITER_ROLE,
    ExperimentConclusionTransportError,
    PostgresExperimentConclusionReader,
    PostgresExperimentConclusionRpc,
    RpcExperimentConclusionRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record_conclusion(self, item: ExperimentConclusionRecord):
        item.validate()
        key = item.conclusion.conclusion_key
        if key in self.rows:
            return {
                "status": "existing",
                "conclusion_id": self.rows[key]["conclusion_id"],
            }
        row = {
            "conclusion_id": f"conclusion-{len(self.rows) + 1}",
            "conclusion_key": key,
            "effect_direction": item.conclusion.effect_direction,
        }
        self.rows[key] = row
        return {"status": "recorded", **row}


    def list_conclusions(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(create_experiment_router(registry))
    return TestClient(app)


def body(**overrides):
    payload = {
        "conclusion_key": "exp-1-conclusion-v1",
        "experiment_key": "exp-1",
        "metric": "revenue_per_subject",
        "control_values": [10, 10, 10, 10, 10],
        "treatment_values": [12, 12, 12, 12, 12],
        "evidence_refs": ["assignment:a", "exposure:b", "outcome:c"],
        "assignment_integrity_verified": True,
        "exposure_integrity_verified": True,
        "outcome_window_closed": True,
        "minimum_per_arm": 5,
        "evidence": {"source": "canonical_experiment_outcomes"},
    }
    payload.update(overrides)
    return payload


def test_preview_builds_causal_review_packet_without_significance_claim():
    response = client().post(
        "/v1/experiments/conclusions/preview",
        json=body(),
    )
    assert response.status_code == 200
    conclusion = response.json()["conclusion"]
    assert conclusion["absolute_lift"] == 2.0
    assert conclusion["relative_lift"] == 0.2
    assert conclusion["effect_direction"] == "positive_observed_lift"
    assert conclusion["causal_review_eligible"] is True
    assert conclusion["statistical_significance_available"] is False
    assert conclusion["interpretation"] == (
        "eligible_for_causal_review_not_significance_claim"
    )
    assert conclusion["execution_authority"] == "none"
    assert conclusion["traffic_mutation"] is False
    assert conclusion["rollout_enabled"] is False
    assert conclusion["pricing_mutation"] is False


def test_integrity_failure_cannot_create_conclusion():
    response = client().post(
        "/v1/experiments/conclusions/preview",
        json=body(exposure_integrity_verified=False),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "experiment not eligible for causal conclusion"
    )


def test_negative_observed_lift_is_preserved_without_rollout_judgment():
    response = client().post(
        "/v1/experiments/conclusions/preview",
        json=body(
            treatment_values=[8, 8, 8, 8, 8],
        ),
    )
    assert response.status_code == 200
    conclusion = response.json()["conclusion"]
    assert conclusion["absolute_lift"] == -2.0
    assert conclusion["effect_direction"] == "negative_observed_lift"
    assert conclusion["rollout_enabled"] is False


def test_unbound_conclusion_registry_fails_closed():
    response = client().post(
        "/v1/experiments/conclusions/register",
        json=body(),
    )
    assert response.status_code == 503


def test_conclusion_registry_is_idempotent_and_history_is_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/experiments/conclusions/register", json=body())
    second = c.post("/v1/experiments/conclusions/register", json=body())
    history = c.get("/v1/experiments/conclusions")
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"
    assert second.json()["status"] == "existing"
    assert history.status_code == 200
    assert history.json()["read_only"] is True
    assert history.json()["execution_authority"] == "none"
    assert history.json()["count"] == 1


def test_conclusion_registry_requires_registry_evidence():
    payload = body(evidence={})
    response = client(FakeRegistry()).post(
        "/v1/experiments/conclusions/register",
        json=payload,
    )
    assert response.status_code == 422
    assert "registry requires evidence" in response.json()["detail"]


def test_transport_sends_means_not_client_lift_or_significance():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "conclusion_id": "c1"}

    repo = RpcExperimentConclusionRepository(rpc)
    response = client(repo).post(
        "/v1/experiments/conclusions/register",
        json=body(),
    )
    assert response.status_code == 200
    name, params = calls[0]
    assert name == RPC_NAME
    assert params["p_control_mean"] == 10.0
    assert params["p_treatment_mean"] == 12.0
    assert params["p_assignment_integrity_verified"] is True
    assert params["p_exposure_integrity_verified"] is True
    assert params["p_outcome_window_closed"] is True
    assert "p_absolute_lift" not in params
    assert "p_statistical_significance" not in params


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("id"),
            Description("conclusion_key"),
            Description("effect_direction"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [("c1", "conclusion-1", "positive_observed_lift")]

    def fetchone(self):
        return ({"status": "recorded", "conclusion_id": "c1"},)


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def test_reader_uses_dedicated_role_and_static_query():
    cursor = Cursor()
    reader = PostgresExperimentConclusionReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["conclusion_key"] == "conclusion-1"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_writer_rejects_rollout_rpc_before_connect():
    rpc = PostgresExperimentConclusionRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        ExperimentConclusionTransportError,
        match="cannot execute",
    ):
        rpc("rollout_experiment_winner", {})


def test_writer_uses_dedicated_role():
    cursor = Cursor()
    rpc = PostgresExperimentConclusionRpc(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    result = rpc(
        RPC_NAME,
        {
            "p_conclusion_key": "conclusion-1",
            "p_experiment_key": "exp-1",
            "p_metric": "revenue_per_subject",
            "p_control_count": 5,
            "p_treatment_count": 5,
            "p_control_mean": 10.0,
            "p_treatment_mean": 12.0,
            "p_assignment_integrity_verified": True,
            "p_exposure_integrity_verified": True,
            "p_outcome_window_closed": True,
            "p_evidence_refs": ["assignment:a", "outcome:c"],
            "p_evidence": {"source": "canonical"},
        },
    )
    assert result["status"] == "recorded"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + WRITER_ROLE, None)
