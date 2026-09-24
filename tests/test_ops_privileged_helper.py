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


def test_runtime_self_heal_units_are_allowlisted_without_outbound_authority():
    from empire_os.ops_privileged_helper import ALLOWED_UNITS

    expected = {
        "empire-self-serve-checkout.service",
        "empire-ops-mcp.service",
        "empire-commercial-product-catalog.service",
        "empire-commercial-product-catalog.timer",
        "empire-commercial-exchange.service",
        "empire-commercial-exchange.timer",
        "empire-buyer-acquisition-team.service",
        "empire-buyer-acquisition-team.timer",
        "empire-source-health.service",
        "empire-source-health.timer",
        "empire-revenue-pulse.timer",
        "empire-acquisition.timer",
        "empire-qualification.timer",
        "empire-hermes-control.timer",
        "empire-buyer-deferred-enrichment.service",
        "empire-buyer-deferred-enrichment.timer",
        "empire-predictive-revenue-enterprise-activation.service",
        "empire-predictive-revenue-enterprise-activation.timer",
        "empire-enterprise-contact-sync.service",
        "empire-enterprise-contact-repair.service",
        "empire-enterprise-contact-repair.timer",
    }
    assert expected.issubset(ALLOWED_UNITS)
    assert all("outbound" not in unit for unit in ALLOWED_UNITS)
    assert all("payment" not in unit for unit in ALLOWED_UNITS)
    assert all("settlement" not in unit for unit in ALLOWED_UNITS)
