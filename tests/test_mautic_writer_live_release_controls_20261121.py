"""Fail-closed Mautic empty-source writer release controls.

No real credentials, PostgreSQL changes, webhooks or customer data.
"""
from __future__ import annotations

from pathlib import Path
import ast
import os
import re
from types import SimpleNamespace

import pytest

from scripts import provision_mautic_empty_source_writer_20261121 as w
from scripts import verify_live_mautic_inbox_tenant_readonly_20261121 as probe


def test_scram_credential_derives_nonplain_postgres_verifier():
    result = w.scram_verifier("fixture-password-kept-private")
    assert result.startswith("SCRAM-SHA-256$4096:")
    assert "fixture-password-kept-private" not in result
    assert len(result.split("$")) == 3
    assert len(result.split(":")) == 3
    assert w.scram_verifier("fixture-password-kept-private") != result


def test_preflight_no_root_requires_no_file_or_db_changes(monkeypatch):
    monkeypatch.setattr(w.os, "geteuid", lambda: 1000)
    with pytest.raises(RuntimeError, match="host_root_approver_required"):
        w.execute(apply=False)
    monkeypatch.setattr(probe.os, "geteuid", lambda: 1000)
    assert probe.run()["status"] == "HELD_OR_UNAVAILABLE"
    assert probe.run()["database_writes"] is False


def test_exact_scram_hba_patch_never_opens_unscoped_roles(tmp_path,monkeypatch):
    target=tmp_path/"pg_hba.conf"
    target.write_text(
        "local   empiredb   empire_crm_tenant_708efd4b53b2   scram-sha-256\n"
        "local   all             postgres                         peer\n"
        "local   all             all                              peer\n"
    )
    target.chmod(0o640)
    monkeypatch.setattr(w,"HBA",target)
    monkeypatch.setattr(w.pwd,"getpwnam",lambda _:SimpleNamespace(pw_uid=os.getuid()))
    original,_,_,_,revised=w.hba_ready("empire_mautic_tenant_708efd4b53b2")
    assert b"local   empiredb   empire_mautic_tenant_708efd4b53b2   scram-sha-256\n" in revised
    assert revised.count(b"empire_mautic_tenant") == 1
    assert revised.replace(
        b"local   empiredb   empire_mautic_tenant_708efd4b53b2   scram-sha-256\n",b""
    ) == original
    target.write_bytes(revised)
    with pytest.raises(RuntimeError, match="existing_mautic_hba_requires_reconciliation"):
        w.hba_ready("empire_mautic_tenant_708efd4b53b2")


def test_untrusted_hba_order_fails_closed(tmp_path,monkeypatch):
    target=tmp_path/"pg_hba.conf"
    target.write_text("local all all trust\n")
    target.chmod(0o640)
    monkeypatch.setattr(w,"HBA",target)
    monkeypatch.setattr(w.pwd,"getpwnam",lambda _:SimpleNamespace(pw_uid=os.getuid()))
    with pytest.raises(RuntimeError, match="unknown_postgresql_hba_order"):
        w.hba_ready("empire_mautic_tenant_708efd4b53b2")


def test_writer_source_can_only_perform_zero_event_login_canary():
    p=Path(w.__file__)
    source=p.read_text()
    assert 'evidence_hmacs=[],reviews=[]' in source
    assert 'GRANT CONNECT ON DATABASE empiredb TO {}' in source
    assert 'WITH INHERIT FALSE,SET TRUE' in source
    assert 'NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE' in source
    assert 'systemctl","reload",PG_UNIT' in source
    assert 'systemctl","restart",PG_UNIT' not in source
    assert 'DELETE FROM public.empire_tenant_role_bindings' in source
    assert 'DROP ROLE {}' in source
    assert "postgresql_reload_only" in source
    assert "no_customer_events_inserted" in source
    assert "no_webhooks_or_campaigns_enabled" in source


def test_live_reader_probe_does_not_mint_founder_identity():
    src=Path(probe.__file__).read_text()
    assert 'founder_bearer_session_authenticated": False' in src
    assert "SET TRANSACTION READ ONLY" in src
    assert "PostgresRevenueCrmRepository" in src
    assert "INBOX_SELECT_SQL" in src
    assert "access_token" not in src
    assert "password_login" not in src
