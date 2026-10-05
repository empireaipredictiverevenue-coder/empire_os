from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from empire_os import ops_github_bridge as bridge


def request(operation="repo_status", **overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": "empire.ops_bridge.request.v1",
        "request_id": "a" * 32,
        "operation": operation,
        "arguments": {},
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "requested_by": "chatgpt-github-connector",
        "result_certificate_pem": (
            "-----BEGIN CERTIFICATE-----\n"
            "placeholder\n"
            "-----END CERTIFICATE-----\n"
        ),
    }
    payload.update(overrides)
    return payload


def test_bridge_rejects_arbitrary_shell():
    with pytest.raises(bridge.BridgePolicyError, match="not allowlisted"):
        bridge.validate_request(
            request(operation="run_command"),
            path="bridge/requests/" + "a" * 32 + ".json",
        )


def test_bridge_requires_request_id_to_match_path():
    with pytest.raises(bridge.BridgePolicyError, match="id/path mismatch"):
        bridge.validate_request(
            request(),
            path="bridge/requests/" + "b" * 32 + ".json",
        )


def test_bridge_rejects_expired_request():
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(bridge.BridgePolicyError, match="expired"):
        bridge.validate_request(
            request(expires_at=expired.isoformat()),
            path="bridge/requests/" + "a" * 32 + ".json",
        )


def test_bridge_operation_surface_has_no_consequential_runtime_actions():
    assert "service_control" not in bridge._ALLOWED_OPERATIONS
    assert "database_query" not in bridge._ALLOWED_OPERATIONS
    assert "send_outbound" not in bridge._ALLOWED_OPERATIONS
    assert "run_command" not in bridge._ALLOWED_OPERATIONS


def test_bridge_result_api_is_ciphertext_only():
    source = Path("empire_os/ops_bridge_api.py").read_text()
    assert "runtime/ops_bridge/results" in source
    assert ".pem" in source
    assert "Cache-Control" in source
    assert "no-store" in source
