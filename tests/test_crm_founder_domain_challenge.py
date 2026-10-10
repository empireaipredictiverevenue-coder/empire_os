"""One-time DNS TXT ownership signal, never founder identity or CRM authority."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

import pytest

from scripts import crm_founder_domain_challenge as c


def test_prepare_is_private_idempotent_and_scoped(tmp_path):
    state = tmp_path / "private" / "challenge.json"
    first = c.prepare(state, now=100000)
    second = c.prepare(state, now=100100)
    assert first["record_value"] == second["record_value"]
    assert first["record_name"] == c.FQDN
    assert first["record_type"] == "TXT"
    assert first["record_value"].startswith("empire-crm-founder-v1=")
    assert first["crm_membership_activated"] is False
    assert first["legal_company_ownership_verified"] is False
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.parent.stat().st_mode) == 0o700
    data=json.loads(state.read_text())
    assert data["tenant_id"] == c.TENANT_ID
    assert data["subject"] == c.SUBJECT
    with pytest.raises(ValueError, match="expired"):
        c.prepare(state, now=100000 + c.VALID_SECONDS)


def test_both_authoritative_nameservers_required_for_positive_signal(tmp_path, monkeypatch):
    path = tmp_path / "private" / "challenge.json"
    challenge = c.prepare(path, now=200000)
    token = challenge["record_value"]
    monkeypatch.setattr(c, "_dig_txt", lambda fqdn, ns: {token})
    result = c.verify(path, now=200100)
    assert result["dns_control_challenge_verified"] is True
    assert result["status"] == "DOMAIN_DNS_TXT_MATCH_REVIEW_ONLY"
    assert result["crm_membership_activated"] is False
    assert result["founder_human_identity_verified"] is False
    assert result["legal_company_ownership_verified"] is False
    assert result["login_or_credentials_created"] is False
    assert result["outbound_authorized"] is False
    assert result["payment_authorized"] is False


@pytest.mark.parametrize("values", [
    [None, None],
    [{"unrelated"}, {"unrelated"}],
    [{"correct"}, set()],
    [set(), {"correct"}],
])
def test_missing_or_ambiguous_dns_never_verifies(tmp_path, monkeypatch, values):
    path = tmp_path / "private" / "challenge.json"
    challenge = c.prepare(path, now=300000)
    real = challenge["record_value"]
    lookup = iter(values)
    monkeypatch.setattr(c, "_dig_txt",
                        lambda fqdn, ns: {real} if (v := next(lookup)) == {"correct"} else v)
    result = c.verify(path, now=300001)
    assert result["dns_control_challenge_verified"] is False
    assert result["status"] == "AWAITING_AUTHORITATIVE_DNS_MATCH"


def test_expired_state_never_queries_dns(tmp_path, monkeypatch):
    path = tmp_path / "private" / "challenge.json"
    c.prepare(path, now=5000)
    monkeypatch.setattr(c, "_dig_txt", lambda *args: pytest.fail("DNS call must not occur"))
    expired = c.verify(path, now=5000+c.VALID_SECONDS)
    assert expired["status"] == "CHALLENGE_EXPIRED_FAIL_CLOSED"
    assert expired["dns_control_challenge_verified"] is False


def test_rejects_symlinks_and_lax_file_permissions(tmp_path):
    private = tmp_path / "private"
    state = private / "challenge.json"
    c.prepare(state, now=1000)
    state.chmod(0o644)
    with pytest.raises(ValueError, match="private regular"):
        c.verify(state, now=1002)
    state.chmod(0o600)
    link = private / "link.json"
    link.symlink_to(state)
    with pytest.raises(ValueError, match="private regular"):
        c.verify(link, now=1002)
    private.chmod(0o755)
    with pytest.raises(ValueError, match="directory"):
        c.verify(state, now=1002)


def test_tampered_tenant_binding_fails_closed(tmp_path):
    state = tmp_path / "private" / "challenge.json"
    c.prepare(state, now=1000)
    document = json.loads(state.read_text())
    document["tenant_id"] = "00000000-0000-0000-0000-000000000000"
    state.write_text(json.dumps(document))
    state.chmod(0o600)
    with pytest.raises(ValueError, match="identity"):
        c.verify(state, now=1002)


def test_authoritative_txt_must_match_exactly(monkeypatch):
    class Result:
        returncode = 0
        stdout = '"empire-crm-founder-v1=exact"\n"unrelated"\n'
    monkeypatch.setattr(c.subprocess, "run", lambda *a, **kw: Result())
    assert c._dig_txt(c.FQDN, c.EXPECTED_NAMESERVERS[0]) == {
        "empire-crm-founder-v1=exact", "unrelated"
    }


def test_program_contract_contains_no_db_dns_mutations():
    src=Path(c.__file__).read_text()
    for forbidden in ("psycopg", "cloudflare_api", "ALTER ROLE",
                      "UPDATE public.empire_crm_tenant_memberships",
                      "INSERT INTO public.empire_crm_login_credentials",
                      "os.system(", "shell=True", "curl -X POST"):
        assert forbidden not in src
