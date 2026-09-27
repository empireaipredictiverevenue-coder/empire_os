from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.digital_twin_api import create_digital_twin_router
from empire_os.digital_twin_registry import DigitalTwinRealizationRecord
from empire_os.digital_twin_realization_registry_transport import (
    READ_SQL,
    READER_ROLE,
    RPC_NAME,
    WRITER_ROLE,
    DigitalTwinRealizationTransportError,
    PostgresDigitalTwinRealizationReader,
    PostgresDigitalTwinRealizationRpc,
    RpcDigitalTwinRealizationRepository,
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}

    def record_realization(self, item: DigitalTwinRealizationRecord):
        item.validate()
        if item.realization_key in self.rows:
            return {
                "status": "existing",
                "realization_id": self.rows[item.realization_key]["realization_id"],
            }
        row = {
            "realization_id": f"realization-{len(self.rows) + 1}",
            "realization_key": item.realization_key,
            "scenario_key": item.scenario_key,
        }
        self.rows[item.realization_key] = row
        return {"status": "recorded", **row}

    def list_realizations(self, *, limit):
        return list(self.rows.values())[:limit]


def body():
    return {
        "realization_key": "roofing-london-v1-realization-1",
        "scenario_key": "roofing-london-demand-up-v1",
        "baseline": {
            "niche": "roofing",
            "metro": "London",
            "observed_demand_units": 100,
            "observed_capacity_units": 80,
            "observed_price_per_unit_cents": 10000,
            "observed_at": "2026-09-19T20:00:00+00:00",
            "evidence_ref": "exchange:roofing-london:2026-09-19",
        },
        "scenario": {
            "scenario_id": "scenario-1",
            "demand_multiplier": 1.2,
            "capacity_multiplier": 1.25,
            "price_multiplier": 1.0,
        },
        "observed_served_units": 90,
        "observed_revenue_cents": 900000,
        "revenue_recognized": True,
        "observed_at": "2026-09-20T12:00:00+00:00",
        "evidence_refs": [
            "market:served:1",
            "revenue:recognized:1",
        ],
        "evidence": {"source": "canonical_realization_evidence"},
    }


def client(registry=None):
    app = FastAPI()
    app.include_router(create_digital_twin_router(registry))
    return TestClient(app)


def test_unbound_realization_registry_fails_closed():
    response = client().post(
        "/v1/digital-twin/realizations/register",
        json=body(),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "digital_twin_realization_registry_not_activated"
    )


def test_realization_registers_without_execution_or_actual_revenue():
    repo = FakeRegistry()
    response = client(repo).post(
        "/v1/digital-twin/realizations/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "OBSERVE"
    assert data["simulation_only"] is True
    assert data["creates_actual_revenue"] is False
    assert data["execution_authority"] == "none"
    assert data["capital_execution"] is False
    assert data["campaign_execution"] is False
    assert data["pricing_execution"] is False
    assert data["realization_record"]["review"][
        "revenue_comparison_available"
    ] is True


def test_realization_registry_is_idempotent_and_history_is_read_only():
    repo = FakeRegistry()
    c = client(repo)
    first = c.post("/v1/digital-twin/realizations/register", json=body())
    second = c.post("/v1/digital-twin/realizations/register", json=body())
    history = c.get("/v1/digital-twin/realizations")
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert history.status_code == 200
    assert history.json()["read_only"] is True
    assert history.json()["count"] == 1


def test_unrecognized_revenue_is_not_exposed_as_observed_revenue():
    payload = body()
    payload["revenue_recognized"] = False
    response = client(FakeRegistry()).post(
        "/v1/digital-twin/realizations/register",
        json=payload,
    )
    assert response.status_code == 200
    record = response.json()["realization_record"]
    assert record["observed"]["observed_revenue_cents"] is None
    assert record["review"]["observed_revenue_cents"] is None
    assert record["review"]["revenue_error_cents"] is None
    assert record["review"]["revenue_comparison_available"] is False


def test_transport_maps_only_observed_inputs_to_realization_rpc():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "realization_id": "r1"}

    repo = RpcDigitalTwinRealizationRepository(rpc)
    response = client(repo).post(
        "/v1/digital-twin/realizations/register",
        json=body(),
    )
    assert response.status_code == 200
    name, params = calls[0]
    assert name == RPC_NAME
    assert params["p_scenario_key"] == "roofing-london-demand-up-v1"
    assert params["p_observed_served_units"] == 90
    assert params["p_observed_revenue_cents"] == 900000
    assert params["p_evidence"]["source"] == "canonical_realization_evidence"
    assert "p_revenue_error_cents" not in params


class Description:
    def __init__(self, name):
        self.name = name


class Cursor:
    def __init__(self):
        self.calls = []
        self.description = [
            Description("realization_id"),
            Description("realization_key"),
            Description("scenario_key"),
        ]


    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return [("r1", "realization-1", "scenario-1")]

    def fetchone(self):
        return ({"status": "recorded", "realization_id": "r1"},)


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
    reader = PostgresDigitalTwinRealizationReader(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    rows = reader(limit=20)
    assert rows[0]["realization_key"] == "realization-1"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + READER_ROLE, None)
    assert cursor.calls[1] == (READ_SQL, (20,))


def test_writer_rejects_non_realization_rpc_before_connect():
    rpc = PostgresDigitalTwinRealizationRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        DigitalTwinRealizationTransportError,
        match="cannot execute",
    ):
        rpc("execute_digital_twin_scenario", {})


def test_writer_uses_dedicated_role():
    cursor = Cursor()
    rpc = PostgresDigitalTwinRealizationRpc(
        "postgresql://example",
        connect_factory=lambda dsn: Connection(cursor),
    )
    result = rpc(
        RPC_NAME,
        {
            "p_realization_key": "realization-1",
            "p_scenario_key": "scenario-key-1",
            "p_observed_served_units": 10,
            "p_observed_revenue_cents": 1000,
            "p_revenue_recognized": True,
            "p_observed_at": "2026-09-20T12:00:00+00:00",
            "p_evidence_refs": ["outcome:1"],
            "p_evidence": {"source": "canonical"},
        },
    )
    assert result["status"] == "recorded"
    assert cursor.calls[0] == ("SET LOCAL ROLE " + WRITER_ROLE, None)
