"""Original registry transport: secure EmpireDB native owner-controlled path."""
from datetime import date

import pytest

from empire_os.predictive_registry_transport import (
    EmpireDbProspectiveForecastRegistration,
    NATIVE_FORECAST_REGISTER_SQL,
    NATIVE_FORECAST_REGISTRAR_ROLE,
    PredictiveRegistryTransportError,
    RPC_NAME,
    WRITE_SQL,
)

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _bad_connection(*_a, **_kw):
    raise AssertionError("no source connection allowed")


def _kwargs(**overrides):
    record = {
        "tenant_id": TENANT,
        "model_name": "empire_baseline",
        "model_version": "v1",
        "observed_through": date(2026, 11, 14),
        "horizon_days": 7,
        "sample_count": 14,
        "predicted_cents": 12345,
        "r_squared": 0.8,
        "evidence_confidence": 0.75,
        "direction": "up",
        "source_evidence_sha256": "f" * 64,
    }
    record.update(overrides)
    return record


def test_owner_gate_refuses_constructor_before_connection():
    with pytest.raises(PredictiveRegistryTransportError, match="not authorised"):
        EmpireDbProspectiveForecastRegistration(
            "dbname=empiredb", connect_factory=_bad_connection
        )
    with pytest.raises(PredictiveRegistryTransportError, match="not authorised"):
        EmpireDbProspectiveForecastRegistration(
            "dbname=empiredb", enabled=1, connect_factory=_bad_connection
        )
    with pytest.raises(PredictiveRegistryTransportError, match="credential"):
        EmpireDbProspectiveForecastRegistration(
            " ", enabled=True, connect_factory=_bad_connection
        )


@pytest.mark.parametrize("override", [
    {"tenant_id": "not-a-uuid"},
    {"tenant_id": True},
    {"model_name": "unsafe; DROP TABLE"},
    {"model_version": ""},
    {"observed_through": "2026-11-14"},
    {"horizon_days": True},
    {"horizon_days": 0},
    {"sample_count": 6},
    {"sample_count": 121},
    {"predicted_cents": 12345.5},
    {"predicted_cents": True},
    {"predicted_cents": -1},
    {"r_squared": float("nan")},
    {"r_squared": 1.5},
    {"evidence_confidence": float("inf")},
    {"direction": "forecast-and-send"},
    {"source_evidence_sha256": "f" * 63},
    {"source_evidence_sha256": "F" * 64},
])
def test_invalid_input_refused_before_database_access(override):
    writer = EmpireDbProspectiveForecastRegistration(
        "dbname=empiredb", enabled=True, connect_factory=_bad_connection
    )
    with pytest.raises(PredictiveRegistryTransportError,
                       match="input invalid"):
        writer.register(**_kwargs(**override))


def test_original_public_rpc_not_rewired_to_private_native_registration():
    assert RPC_NAME == "record_predictive_forecast"
    assert "record_predictive_forecast" in WRITE_SQL
    assert "register_predictive_revenue_forecast_v1" in NATIVE_FORECAST_REGISTER_SQL
    assert NATIVE_FORECAST_REGISTRAR_ROLE == "empire_predictive_forecast_registrar"
    assert "SET LOCAL ROLE" not in NATIVE_FORECAST_REGISTER_SQL
    assert NATIVE_FORECAST_REGISTER_SQL.count("%s") == 10


def test_authenticated_database_failure_does_not_expose_connection_details():
    writer = EmpireDbProspectiveForecastRegistration(
        "password=private-secret", enabled=True,
        connect_factory=lambda *_a, **_kw: (_ for _ in ()).throw(
            RuntimeError("private-secret SQL policy details"))
    )
    with pytest.raises(PredictiveRegistryTransportError,
                       match="registration unavailable") as exc:
        writer.register(**_kwargs())
    assert "private-secret" not in str(exc.value)
    assert exc.value.__cause__ is None
