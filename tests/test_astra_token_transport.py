import pytest

from empire_os.astra_token_transport import AstraTokenRpc
from empire_os.outcome_role_transport import OutcomeTransportError


class FakeBackend:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def call(self, name, params):
        self.calls.append((name, dict(params)))
        return self.result


def test_feedback_rpc_allows_only_expected_parameters():
    backend = FakeBackend([{"actual_revenue_cents": 10000}])
    rpc = AstraTokenRpc(backend)

    result = rpc(
        "get_commercial_outcome_feedback",
        {"p_limit": 25},
    )

    assert result[0]["actual_revenue_cents"] == 10000
    assert backend.calls == [
        ("get_commercial_outcome_feedback", {"p_limit": 25})
    ]


def test_operational_rpc_has_no_parameters():
    backend = FakeBackend({"failed_jobs": 2})
    rpc = AstraTokenRpc(backend)

    assert rpc("get_astra_operational_evidence", {}) == {"failed_jobs": 2}


def test_write_functions_are_rejected_locally():
    rpc = AstraTokenRpc(FakeBackend())

    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("recognize_bsc_revenue", {})
    with pytest.raises(OutcomeTransportError, match="not allowed"):
        rpc("record_commercial_outcome", {})


def test_wrong_parameter_shape_is_rejected_before_backend():
    backend = FakeBackend()
    rpc = AstraTokenRpc(backend)

    with pytest.raises(OutcomeTransportError, match="unexpected"):
        rpc("get_commercial_outcome_feedback", {})

    assert backend.calls == []
