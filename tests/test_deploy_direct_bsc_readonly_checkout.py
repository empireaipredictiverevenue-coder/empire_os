"""Offline, no-production-write tests for the direct BSC read-only config operator."""
from unittest.mock import patch
import pytest
from scripts import deploy_direct_bsc_readonly_checkout as deploy


def test_staged_config_exactly_direct_and_financial_gates_off():
    assert deploy.SOURCE.read_bytes() == deploy.EXPECTED
    assert deploy.EXPECTED.count(b"AUTHORIZED=OFF") == 2
    assert b"SETTLEMENT_MODE=direct" in deploy.EXPECTED
    assert b"BSC_MIN_CONFIRMATIONS=12" in deploy.EXPECTED
    assert b"BSC_RPC_URL=https://bsc-dataseed.bnbchain.org" in deploy.EXPECTED
    assert b"0x1339b487046B0ad924a10c20b1791608EA8595a8" in deploy.EXPECTED
    assert b"AUTHORIZED=ON" not in deploy.EXPECTED
    assert b"SETTLEMENT_MODE=escrow" not in deploy.EXPECTED


@pytest.mark.parametrize("missing", (
    "payment_proposal_authorized", "binding_order_creation_authorized",
    "payment_execution", "revenue_recognition",
))
def test_missing_or_unsafe_financial_switch_blocks(missing):
    good = {"payment_proposal_authorized": False,
            "binding_order_creation_authorized": False,
            "payment_execution": False,
            "revenue_recognition": False}
    assert deploy._financial_gates_off(good)
    bad = dict(good)
    bad.pop(missing)
    assert not deploy._financial_gates_off(bad)
    bad[missing] = True
    assert not deploy._financial_gates_off(bad)


def test_no_apply_without_exact_separate_founder_restarters(monkeypatch):
    monkeypatch.setattr(deploy.os, "geteuid", lambda: 0)
    assert deploy._root_main(["--apply"]) == 3
    assert deploy._root_main(["--approved-direct-bsc-readonly-config-and-checkout-restart"]) == 3
    assert deploy._root_main(["--apply", "--approved-exact-two-bsc-db-connect-grants"]) == 3
    assert deploy._root_main(["--apply", "--approved-one-direct-verifier-login"]) == 3
    assert deploy._root_main(["--apply", "--approved-one-direct-verifier-scram-rule"]) == 3


def test_unprivileged_apply_blocked(monkeypatch):
    monkeypatch.setattr(deploy.os, "geteuid", lambda: 1000)
    assert deploy._root_main(["--apply",
                              "--approved-direct-bsc-readonly-config-and-checkout-restart"]) == 3


def test_preflight_never_installs_or_restarts(monkeypatch, capsys):
    monkeypatch.setattr(deploy.os, "geteuid", lambda: 0)
    monkeypatch.setattr(deploy, "_verify_existing", lambda: {
        "status": "READY_FOR_SEPARATELY_APPROVED_READONLY_BSC_CONFIG_DEPLOYMENT"
    })
    class DummyLock:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def fileno(self): return 1
    monkeypatch.setattr(deploy.LOCK.__class__, "open", lambda *args, **kwargs: DummyLock())
    monkeypatch.setattr(deploy.fcntl, "flock", lambda *_: None)
    with patch.object(deploy, "_backup") as backup, patch.object(deploy, "_postcheck") as post:
        assert deploy._root_main(["--preflight"]) == 0
    backup.assert_not_called()
    post.assert_not_called()


def test_source_guard_does_not_allow_unreviewed_blob(monkeypatch):
    monkeypatch.setattr(deploy.SOURCE.__class__, "read_bytes",
                        lambda _self: b"Environment=AUTHORIZED=ON")
    with pytest.raises(RuntimeError, match="source drift"):
        deploy._checked_source()


def test_catalog_verifier_fail_closed(monkeypatch):
    class Resp:
        returncode = 0
        stdout = '{"status":"DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED"}'
    monkeypatch.setattr(deploy.subprocess, "run", lambda *args, **kwargs: Resp())
    with pytest.raises(RuntimeError, match="incomplete"):
        deploy._catalog_verifier()


def test_postcheck_cannot_claim_success_without_both_disabled(monkeypatch):
    monkeypatch.setattr(deploy.TARGET.__class__, "read_bytes",
                        lambda _self: deploy.EXPECTED)
    monkeypatch.setattr(deploy, "_health", lambda: {
        "status": "online", "payment_proposal_authorized": True,
        "binding_order_creation_authorized": False,
        "payment_execution": False, "revenue_recognition": False,
        "checkout_settlement_mode": "direct",
        "bsc_payment_configuration_status": "BSC_CONFIGURED_CHAIN_UNVERIFIED"
    })
    with pytest.raises(RuntimeError, match="gate drift"):
        deploy._postcheck()
