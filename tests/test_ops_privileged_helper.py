from types import SimpleNamespace

import pytest

from empire_os.ops_privileged_helper import (
    PrivilegedHelperPolicyError,
    execute_request,
    validate_request,
)


def request(action="service_status", unit="empire-public-gateway.service"):
    return {"request_id": "req-1", "action": action, "unit": unit}


def test_allowlisted_status_maps_to_fixed_systemctl_argv():
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="ActiveState=active\n", stderr="")

    result = execute_request(request(), runner=runner)
    assert result["ok"] is True
    assert calls[0][0] == [
        "systemctl",
        "show",
        "empire-public-gateway.service",
        "--property=ActiveState,SubState,UnitFileState",
    ]


def test_restart_is_allowlisted_but_no_arbitrary_command():
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    execute_request(
        request("service_restart", "empire-revenue-pulse.service"),
        runner=runner,
    )
    assert calls == [["systemctl", "restart", "empire-revenue-pulse.service"]]


def test_arbitrary_action_is_rejected():
    with pytest.raises(PrivilegedHelperPolicyError, match="action not allowlisted"):
        validate_request(request("shell"))


def test_arbitrary_unit_is_rejected():
    with pytest.raises(PrivilegedHelperPolicyError, match="unit not allowlisted"):
        validate_request(request(unit="ssh.service"))


def test_start_is_narrower_than_restart_allowlist():
    with pytest.raises(PrivilegedHelperPolicyError, match="not allowlisted for start"):
        validate_request(
            request("service_start", "empire-public-gateway.service")
        )
