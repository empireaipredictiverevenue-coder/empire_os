"""Owner release contract: existing V4.10/066 HELD source binding, no authority expansion."""
from __future__ import annotations
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/(
    "scripts/bind_official_ich_to_original_crm_tenant_held_20261108.py")
S=importlib.util.spec_from_file_location("original_066_held_tenant_bind",SCRIPT)
m=importlib.util.module_from_spec(S)
S.loader.exec_module(m)


def fake_inputs():
    return ({"source_digest":"a"*64,
             "observed_at":datetime.now(timezone.utc).isoformat()},
            {"rights_document_digest":"b"*64})


def test_real_source_research_packet_pinned_and_non_personal():
    s=m.source_packet()
    assert s["source_digest"]=="31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d"
    assert s["company_number"]=="02745893"
    assert m.sha(m.PACKET.read_bytes())==m.PACKET_SHA
    assert m.PURPOSE=="PRIVATE_PREDICTIVE_RESEARCH_ONLY"


def test_owner_derived_genuine_tenant_not_supplied_by_caller():
    source,policy=fake_inputs()
    sql=m.transaction(source,policy,"c"*64)
    for term in (
        "public.empire_crm_tenant_memberships",
        "public.empire_crm_login_credentials",
        "c.invitation_tenant_id=m.tenant_id",
        "m.role='owner'", "m.status='active'",
        "c.status='active'", "c.password_change_required=false",
        "m.revoked_at IS NULL", "count(DISTINCT m.tenant_id)",
        "PENDING", "PRIVATE_PREDICTIVE_RESEARCH_ONLY",
    ):
        assert term in sql
    assert "role='owner'" in m.OWNER_WHERE
    assert "tenant_id" not in source and "tenant_id" not in policy
    assert re.search(r"SELECT m\.tenant_id,'a{64}'",sql)
    assert sql.rstrip().endswith("COMMIT;")


def test_cannot_publish_forecast_or_add_other_source_admission_authority():
    source,policy=fake_inputs()
    sql=m.transaction(source,policy,"c"*64)
    assert sql.count("\nBEGIN;")==0  # SQL starts exactly at BEGIN
    assert sql.startswith("BEGIN;")
    assert sql.count("CREATE ROLE empire_predictive_rights_login")==1
    assert sql.count("INSERT INTO public.empire_predictive_source_rights_candidate_held")==1
    for x in ("redis_publish", "customer_forecast", "customer_delivery",
              "settlement", "ALTER TABLE", "DROP TABLE", "ALTER SYSTEM",
              "CREATE TABLE", "CREATE FUNCTION", "GRANT INSERT"):
        assert x not in sql
    assert "'PENDING','none'" in sql
    assert "CONNECTION LIMIT 2" in sql
    assert "VALID UNTIL" in sql
    assert "SET FALSE" in sql
    assert "NOBYPASSRLS" in sql


@pytest.mark.parametrize("password",["a' or 1=1", "", "not-hex", "x"*65, "a"*32])
def test_no_untrusted_password_in_ddl(password):
    source,policy=fake_inputs()
    with pytest.raises(RuntimeError,match="generated_credentials_invalid"):
        m.transaction(source,policy,password)


def test_preflight_is_read_only_and_single_tenant_tied_to_login():
    s=m.PREFLIGHT
    assert "count(DISTINCT m.tenant_id)=1 AND count(*)=1" in s
    assert "count(*)=0 FROM public.empire_predictive_source_rights_candidate_held" in s
    assert "count(*)=0 FROM public.empire_predictive_source_revocations_held" in s
    assert "count(*)=0 FROM pg_catalog.pg_roles" in s
    for cmd in ("INSERT ","UPDATE ","DELETE ","CREATE ROLE","ALTER ROLE"):
        assert cmd not in s


def test_official_rights_policy_uses_only_allowlisted_gov_domain():
    assert m.POLICY.startswith("https://www.gov.uk/government/publications/")
    assert "companies-house" in m.POLICY
    s=SCRIPT.read_text()
    assert "independent_signed_license_attestation" in s
    assert "False" in s
    assert '"OFFICIAL_PUBLIC_REGISTER_POLICY_REVIEW_ONLY"' in s
    assert '"PENDING_HELD"' in s


def test_transaction_rejects_untrusted_timestamp_or_digest():
    source,policy=fake_inputs()
    source["observed_at"]="2026-11-08'; DROP TABLE foo; --"
    with pytest.raises(RuntimeError,match="source_time_untrusted"):
        m.transaction(source,policy,"c"*64)
    source,policy=fake_inputs()
    source["source_digest"]="invalid"
    with pytest.raises(RuntimeError,match="source_or_policy_digest_invalid"):
        m.transaction(source,policy,"c"*64)


def test_private_backup_includes_postgres_global_roles_and_original_reader():
    code=SCRIPT.read_text()
    for term in (
        'pg_dumpall","--globals-only',
        '"pg_restore","--list"',
        "os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600",
        "EmpireDbHeldSourceRightsReader(dsn)",
        'reader(tenant,"f"*64)',
        "pending_rights_reader_dsn",
        "cross_tenant_rejected",
        "rights_owner_attested",
        "source_review_state",
    ):
        assert term in code


def test_source_packet_pin_cannot_be_replaced(monkeypatch,tmp_path):
    fake=tmp_path/"spoof.json"
    fake.write_text("{}")
    monkeypatch.setattr(m,"PACKET",fake)
    with pytest.raises(RuntimeError,match="original_official_research_packet_changed"):
        m.source_packet()
