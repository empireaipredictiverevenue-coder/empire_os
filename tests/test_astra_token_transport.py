import json

import pytest

from empire_os.astra_token_transport import SupabaseTokenAstraRpc
from empire_os.outcome_role_transport import OutcomeTransportError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout=15):
        self.requests.append((request, timeout))
        return FakeResponse(self.payload)


def make_rpc(tmp_path, payload):
    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")
    token_file.chmod(0o600)
    opener = FakeOpener(payload)
    rpc = SupabaseTokenAstraRpc(
        "https://example.supabase.co",
        "sb_publishable_test",
        token_file,
        opener=opener,
    )
    return rpc, opener


def test_feedback_rpc_uses_token_wrapper_only(tmp_path):
    rpc, opener = make_rpc(tmp_path, [{"actual_revenue_cents": 10000}])
    result = rpc(
        "get_commercial_outcome_feedback",
        {"p_limit": 25},
    )
    assert result[0]["actual_revenue_cents"] == 10000
    request, timeout = opener.requests[0]
    assert timeout == 15
    assert request.full_url.endswith(
        "/rest/v1/rpc/get_commercial_outcome_feedback_token"
    )
    body = json.loads(request.data.decode("utf-8"))
    assert body["p_token"] == "a" * 64
    assert body["p_limit"] == 25
    assert request.headers["Apikey"] == "sb_publishable_test"


def test_operational_rpc_uses_token_wrapper_only(tmp_path):
    rpc, opener = make_rpc(tmp_path, {"failed_jobs": 2})
    result = rpc("get_astra_operational_evidence", {})
    assert result["failed_jobs"] == 2
    request, _ = opener.requests[0]
    assert request.full_url.endswith(
        "/rest/v1/rpc/get_astra_operational_evidence_token"
    )


def test_write_functions_are_rejected_locally(tmp_path):
    rpc, _ = make_rpc(tmp_path, {})
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("recognize_bsc_revenue", {})
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("record_commercial_outcome", {})


def test_https_and_token_file_are_required(tmp_path):
    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")
    with pytest.raises(OutcomeTransportError, match="HTTPS"):
        SupabaseTokenAstraRpc(
            "http://example.supabase.co",
            "sb_publishable_test",
            token_file,
        )
    with pytest.raises(OutcomeTransportError, match="token file"):
        SupabaseTokenAstraRpc(
            "https://example.supabase.co",
            "sb_publishable_test",
            tmp_path / "missing",
        )
