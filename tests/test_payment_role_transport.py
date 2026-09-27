import json

import pytest

from empire_os.payment_governance import PaymentGovernanceError
from empire_os.payment_role_transport import PostgresRoleRpc


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (self.result,)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


class Factory:
    def __init__(self, result):
        self.cursor = FakeCursor(result)
        self.dsns = []

    def __call__(self, dsn):
        self.dsns.append(dsn)
        return FakeConnection(self.cursor)

def test_approver_transport_sets_role_and_calls_only_approval_rpc():
    result = {"decision": "approved", "actual_revenue": False}
    factory = Factory(result)
    rpc = PostgresRoleRpc("postgresql://secret", "empire_payment_approver",
                          connect_factory=factory)
    value = rpc("approve_bsc_payment_request", {
        "p_request_id": "00000000-0000-0000-0000-000000000001",
        "p_approved_by": "human",
        "p_approval_note": "reviewed terms",
    })
    assert value == result
    assert factory.dsns == ["postgresql://secret"]
    assert factory.cursor.calls[0] == ("SET LOCAL ROLE empire_payment_approver", None)
    assert factory.cursor.calls[1][0] == (
        "select public.approve_bsc_payment_request(%s,%s,%s)"
    )


def test_approver_transport_cannot_record():
    rpc = PostgresRoleRpc("postgresql://secret", "empire_payment_approver",
                          connect_factory=Factory({}))
    with pytest.raises(PaymentGovernanceError, match="not allowed"):
        rpc("record_bsc_payment_evidence", {
            "p_request_id": "00000000-0000-0000-0000-000000000001",
            "p_evidence": {},
        })


def test_verifier_transport_serializes_evidence_and_cannot_approve():
    factory = Factory({"decision": "recorded", "actual_revenue": False})
    rpc = PostgresRoleRpc("postgresql://secret", "empire_bsc_verifier",
                          connect_factory=factory)
    evidence = {"verified": True, "token_decimals": 18}
    rpc("record_bsc_payment_evidence", {
        "p_request_id": "00000000-0000-0000-0000-000000000002",
        "p_evidence": evidence,
    })
    assert factory.cursor.calls[0] == ("SET LOCAL ROLE empire_bsc_verifier", None)
    values = factory.cursor.calls[1][1]
    assert json.loads(values[1]) == evidence
    with pytest.raises(PaymentGovernanceError, match="not allowed"):
        rpc("approve_bsc_payment_request", {})


def test_transport_rejects_wrong_parameter_shape_and_unknown_role():
    rpc = PostgresRoleRpc("postgresql://secret", "empire_bsc_verifier",
                          connect_factory=Factory({}))
    with pytest.raises(PaymentGovernanceError, match="unexpected.*parameters"):
        rpc("get_bsc_payment_request_review", {"wrong": "value"})
    with pytest.raises(PaymentGovernanceError, match="unsupported payment database role"):
        PostgresRoleRpc("postgresql://secret", "service_role",
                        connect_factory=Factory({}))
    with pytest.raises(PaymentGovernanceError, match="DSN required"):
        PostgresRoleRpc("", "empire_bsc_verifier", connect_factory=Factory({}))


def test_escrow_verifier_transport_is_separate_and_serializes_evidence():
    factory = Factory({"decision": "recorded", "actual_revenue": False})
    rpc = PostgresRoleRpc("postgresql://secret", "empire_escrow_verifier",
                          connect_factory=factory)
    evidence = {"verified": True, "action": "funded"}
    rpc("record_bsc_escrow_lifecycle", {
        "p_agreement_id": "00000000-0000-0000-0000-000000000003",
        "p_action": "funded",
        "p_evidence": evidence,
    })
    assert factory.cursor.calls[0] == ("SET LOCAL ROLE empire_escrow_verifier", None)
    assert json.loads(factory.cursor.calls[1][1][2]) == evidence
    with pytest.raises(PaymentGovernanceError, match="not allowed"):
        rpc("record_bsc_payment_evidence", {})
