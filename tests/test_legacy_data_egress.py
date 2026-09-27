from pathlib import Path

import pytest

from empire_os.legacy_data_egress import (
    LegacyDataEgressGovernor,
    LegacyEgressConfig,
)


def _governor(tmp_path: Path, now, *, hourly=3, component=2, daily=10, probe=60):
    config = LegacyEgressConfig(
        state_path=tmp_path / "state.json",
        lock_path=tmp_path / "state.lock",
        hourly_budget=hourly,
        component_hourly_budget=component,
        daily_budget=daily,
        probe_seconds=probe,
    )
    return LegacyDataEgressGovernor(
        config,
        environ={"EMPIRE_COMPONENT": "qualification"},
        now=lambda: now[0],
    )


def test_component_budget_opens_shared_circuit(tmp_path: Path):
    now = [3600.0]
    governor = _governor(tmp_path, now)

    governor.reserve()
    governor.reserve()

    with pytest.raises(RuntimeError, match="component_hourly_request_budget_exceeded"):
        governor.reserve()

    state = governor.load_state()
    assert state["circuit"]["open"] is True
    assert state["circuit"]["source"] == "local_request_budget"


def test_open_circuit_blocks_ordinary_calls_until_probe_window(tmp_path: Path):
    now = [1000.0]
    governor = _governor(tmp_path, now)
    governor.open("exceed_egress_quota")

    with pytest.raises(RuntimeError, match="next probe"):
        governor.reserve()

    now[0] = 1061.0
    with pytest.raises(RuntimeError, match="probe reserved"):
        governor.reserve()

    governor.reserve(allow_probe=True)
    state = governor.load_state()
    assert state["circuit"]["open"] is True
    assert state["circuit"]["last_probe_reserved_at"] == 1061.0


def test_successful_probe_closes_circuit(tmp_path: Path):
    now = [1000.0]
    governor = _governor(tmp_path, now)
    governor.open("exceed_egress_quota")
    now[0] = 1061.0
    governor.reserve(allow_probe=True)

    governor.success()

    state = governor.load_state()
    assert state["circuit"]["open"] is False
    assert state["circuit"]["reason"] == "probe_succeeded"


def test_402_quota_response_opens_circuit(tmp_path: Path):
    now = [5000.0]
    governor = _governor(tmp_path, now)

    assert governor.observe_http_error(
        402,
        '{"message":"restricted due to the following violations: exceed_egress_quota"}',
    ) is True
    assert governor.is_contained() is True


def test_non_quota_http_error_does_not_open_circuit(tmp_path: Path):
    now = [5000.0]
    governor = _governor(tmp_path, now)

    assert governor.observe_http_error(500, "server error") is False
    assert governor.is_contained() is False


def test_new_environment_names_override_legacy_compatibility_names(tmp_path: Path):
    config = LegacyEgressConfig.from_environment({
        "EMPIRE_LEGACY_DATA_EGRESS_STATE_PATH": str(tmp_path / "new-state.json"),
        "EMPIRE_SUPABASE_EGRESS_STATE_PATH": str(tmp_path / "old-state.json"),
        "EMPIRE_LEGACY_DATA_MAX_REQUESTS_PER_HOUR": "12",
        "EMPIRE_SUPABASE_MAX_REQUESTS_PER_HOUR": "99",
    })

    assert config.state_path == tmp_path / "new-state.json"
    assert config.hourly_budget == 12
