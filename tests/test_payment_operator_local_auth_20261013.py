"""Offline assertions for root-only payment approver CLI credentials.

No real DB connections, buyer rows, wallet operations or approval writes.
"""
from __future__ import annotations

import stat
from types import SimpleNamespace

import pytest

from scripts import payment_operator as op
from empire_os.payment_governance import PaymentGovernanceError


class FakePath:
    def __init__(self, *, secret="test-" + "A" * 48, mode=0o600, parent_mode=0o700):
        self._secret=secret
        self._mode=mode
        self.parent=SimpleNamespace(lstat=lambda: SimpleNamespace(
            st_mode=stat.S_IFDIR | parent_mode,st_uid=0,
        ))

    def lstat(self):
        return SimpleNamespace(st_mode=stat.S_IFREG | self._mode,st_uid=0,st_gid=0)

    def read_text(self, *, encoding):
        assert encoding=="utf-8"
        return (
            "/var/run/postgresql:5432:empiredb:empire_payment_approver_login:"
            + self._secret + "\n"
        )


def test_unprivileged_cli_never_reads_protected_approver_secret(monkeypatch):
    monkeypatch.setattr(op.os,"geteuid",lambda:1000)
    monkeypatch.setattr(op,"_ROOT_APPROVER_PASSFILE",FakePath())
    with pytest.raises(PaymentGovernanceError, match="root local operator"):
        op._local_root_approver_transport()


@pytest.mark.parametrize("bad_mode,parent_mode",[(0o644,0o700),(0o600,0o755)])
def test_operator_secret_permissions_fail_closed(monkeypatch,bad_mode,parent_mode):
    monkeypatch.setattr(op.os,"geteuid",lambda:0)
    monkeypatch.setattr(op,"_ROOT_APPROVER_PASSFILE",
                        FakePath(mode=bad_mode,parent_mode=parent_mode))
    with pytest.raises(PaymentGovernanceError,match="protected operator credential"):
        op._local_root_approver_transport()


def test_secret_only_supplied_to_in_process_connection_factory(monkeypatch):
    monkeypatch.setattr(op.os,"geteuid",lambda:0)
    secret="not-a-real-credential-"+"B"*48
    monkeypatch.setattr(op,"_ROOT_APPROVER_PASSFILE",FakePath(secret=secret))
    import psycopg
    received=[]
    sentinel=object()
    def connect(dsn,*,password):
        received.append((dsn,password))
        return sentinel
    monkeypatch.setattr(psycopg,"connect",connect)
    transport=op._local_root_approver_transport()
    assert transport.role=="empire_payment_approver"
    assert "password" not in transport.dsn.lower()
    assert secret not in transport.dsn
    assert transport._connect(transport.dsn) is sentinel
    assert received==[(op._ROOT_APPROVER_DSN,secret)]


def test_approve_requires_installed_exact_chain_config(monkeypatch,tmp_path):
    from scripts import deploy_direct_bsc_readonly_checkout as dep
    p=tmp_path/"dropin.conf"
    p.write_bytes(b"tampered")
    monkeypatch.setattr(dep,"TARGET",p)
    with pytest.raises(PaymentGovernanceError,match="reviewed BSC chain"):
        op._load_live_direct_chain_config()


def test_approve_chain_env_uses_exact_installed_public_config(monkeypatch,tmp_path):
    from scripts import deploy_direct_bsc_readonly_checkout as dep
    p=tmp_path/"dropin.conf"
    p.write_bytes(dep.EXPECTED)
    monkeypatch.setattr(dep,"TARGET",p)
    monkeypatch.delenv("BSC_RPC_URL",raising=False)
    monkeypatch.delenv("BSC_TREASURY_ADDRESS",raising=False)
    op._load_live_direct_chain_config()
    assert op.os.environ["BSC_RPC_URL"]==dep.RPC
    assert op.os.environ["BSC_TREASURY_ADDRESS"]==dep.TREASURY
    assert op.os.environ["BSC_MIN_CONFIRMATIONS"]=="12"
