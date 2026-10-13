"""Fail-closed direct USDT verifier identity provisioner invariants."""
from unittest.mock import patch
import pytest

from scripts import activate_direct_bsc_verifier_identity as operator
from scripts.inspect_direct_bsc_verifier_readiness import GROUP, LOGIN


def safe_report(*, hba=False):
    return {
        "status": "DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED",
        "canonical_empiredb": True,
        "permission_role_safe": True,
        "app_financial_separation_verified": True,
        "exact_direct_payment_rpc_grants": True,
        "login_present": False,
        "effective_local_scram": hba,
    }


def test_one_exact_additive_hba_and_preserves_original_bytes():
    previous = b"# existing finance rules\nlocal all all peer\n"
    output = operator.additive_hba(previous)
    assert output.endswith(previous)
    assert output.count(b"local   empiredb   empire_bsc_verifier_login   scram-sha-256") == 1
    assert b"empire_payment_approver_login" not in output[:len(output)-len(previous)]


@pytest.mark.parametrize("content", (
    b"", b"abc\x00", b"hello\r\n",
    b"# BEGIN EMPIRE_DIRECT_BSC_VERIFIER_V1\nlocal all all peer\n",
    b"local empiredb empire_bsc_verifier_login trust\n",
))
def test_hba_rejects_duplicates_invalid_encodings(content):
    with pytest.raises(ValueError):
        operator.additive_hba(content)


@pytest.mark.parametrize("patch", (
    {"status": "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"},
    {"canonical_empiredb": False},
    {"permission_role_safe": False},
    {"app_financial_separation_verified": False},
    {"exact_direct_payment_rpc_grants": False},
    {"login_present": True},
))
def test_missing_role_or_auth_drift_fails_closed(patch):
    report = {**safe_report(), **patch}
    assert not operator._base_safe(report)


def test_hba_and_login_have_two_distinct_exact_flags():
    assert operator._root_main(["--apply-hba"]) == 3
    assert operator._root_main(["--apply-login"]) == 3
    assert operator._root_main(["--apply"]) == 3
    assert operator._root_main(["--approved-one-direct-verifier-login"]) == 3
    assert operator._root_main(["--apply-hba", "--approved-one-direct-verifier-login"]) == 3
    assert operator._root_main(["--apply-login", "--approved-one-direct-verifier-scram-rule"]) == 3


def test_nongoverned_mode_cannot_mutate(monkeypatch):
    monkeypatch.setattr(operator.os, "geteuid", lambda: 1001)
    assert operator._root_main(["--apply-hba", "--approved-one-direct-verifier-scram-rule"]) == 3
    assert operator._root_main(["--apply-login", "--approved-one-direct-verifier-login"]) == 3


def test_sql_create_requires_post_hba_catalog_proof():
    with patch.object(operator, "inspect", return_value=safe_report(hba=False)):
        with pytest.raises(RuntimeError, match="preflight drift"):
            operator._create_identity({"scram_verifier": "SCRAM-SHA-256$4096:" + "x"*80})


def test_sql_create_rejects_bad_verifier_payload():
    with pytest.raises(RuntimeError, match="SCRAM verifier"):
        operator._create_identity({})
    with pytest.raises(RuntimeError, match="SCRAM verifier"):
        operator._create_identity({"scram_verifier": "plaintext-secret"})


def test_two_preexisting_operator_logins_preserved():
    assert LOGIN not in operator.existing.NAMES
    assert operator.existing.NAMES == (
        "empire_payment_approver_login", "empire_escrow_verifier_login",
    )
    assert GROUP == "empire_bsc_verifier"


def test_no_payment_runtime_write_imports():
    import inspect
    code = inspect.getsource(operator)
    for phrase in ("approve_bsc_payment_request(", "record_bsc_payment_evidence(",
                   "eth_sendRawTransaction", "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON"):
        assert phrase not in code
