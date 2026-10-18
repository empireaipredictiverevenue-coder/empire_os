"""REV052 after-commit reconciliation: no writes, no credentials or source events."""
import json
from types import SimpleNamespace

from scripts import review_rev052_committed_login_readonly_20261018 as audit


def _catalog(**overrides):
    base={key:True for key in (
        "correct_db","login_exists","login_no_admin_noinherit",
        "credential_is_scram","capability_is_nologin",
        "exact_set_only_grant","no_other_granted_memberships",
        "tenant_binding_exactly_one","tenant_binding_no_extra_rows",
        "function_exists","capability_function_execute",
        "login_no_commercial_select","login_no_orders_select",
        "login_no_buyers_select","hba_specific_scram_rule_configured",
        "hba_no_parse_errors",
    )}
    base.update(overrides)
    return json.dumps(base)


def test_catalog_is_single_readonly_transaction_with_no_ledger_records():
    sql=audit.CATALOG_SQL
    assert sql.startswith("BEGIN READ ONLY;")
    assert sql.rstrip().endswith("ROLLBACK;")
    assert "pg_catalog.pg_authid" in sql
    assert "public.empire_tenant_role_bindings" in sql
    assert "pg_catalog.pg_hba_file_rules" in sql
    assert "pg_catalog.pg_auth_members" in sql
    assert "public.read_predictive_revenue_event_v1(uuid,text)" in sql
    assert "UPDATE public." not in sql
    assert "INSERT INTO public." not in sql
    assert "DELETE FROM public." not in sql
    assert "SELECT * FROM public.commercial_events" not in sql
    assert "SELECT * FROM public.fulfilment_orders" not in sql


def test_admin_catalog_fail_closed_before_private_password():
    report=audit.review(
        admin_query=lambda _sql:_catalog(credential_is_scram=False),
        password_reader=lambda:(_ for _ in ()).throw(
            AssertionError("must not open credential")),
    )
    assert report["status"]=="HOLD_REV052_POST_COMMIT_NOT_VERIFIED"
    assert report["failure_stage"]=="CATALOG_PREREQUISITES"
    assert report["catalog_checks"]["credential_is_scram"] is False
    assert "password" not in json.dumps(report).lower().replace("password_printed","")


def test_admin_catalog_exception_is_redacted():
    secret="never-repeat-secret"
    def fail(_sql):
        raise RuntimeError(secret)
    report=audit.review(admin_query=fail)
    assert report["failure_stage"]=="ADMIN_CATALOG_READONLY"
    assert secret not in json.dumps(report)
    assert report["production_writes"] is False


def test_private_vault_error_is_redacted_without_authentication():
    report=audit.review(
        admin_query=lambda _sql:_catalog(),
        password_reader=lambda:(_ for _ in ()).throw(
            RuntimeError("very-private-password")),
    )
    assert report["failure_stage"]=="PRIVATE_CREDENTIAL_CUSTODY"
    assert "very-private-password" not in json.dumps(report)


def test_authenticated_probe_sqlstate_only_no_raw_exception():
    class SecretAuthError(RuntimeError):
        sqlstate="28P01"
    def fail_connect(**kw):
        raise SecretAuthError("super secret string")
    report=audit.review(
        admin_query=lambda _sql:_catalog(),
        password_reader=lambda:"dummy-unexposed-password",
        connector=fail_connect,
    )
    assert report["failure_stage"]=="AUTHENTICATION"
    assert report["sqlstate"]=="28P01"
    assert report["auth_checks"]["auth_connection_verified"] is False
    assert "super secret" not in json.dumps(report)
    assert "dummy-unexposed" not in json.dumps(report)


def test_incomplete_auth_checks_never_become_verified():
    class SecretAuthError(RuntimeError):
        pass
    report=audit.review(
        admin_query=lambda _sql:_catalog(),
        password_reader=lambda:"hidden",
        connector=lambda **kw:(_ for _ in ()).throw(SecretAuthError()),
    )
    assert report["status"].startswith("HOLD_")
    assert report["failure_stage"]=="AUTHENTICATION"


def test_custody_requires_root_only_private_directory_and_file(tmp_path,monkeypatch):
    from scripts import provision_revenue_event_evidence_login_20261018 as release
    vault=tmp_path/"private"
    vault.mkdir(mode=0o700)
    passfile=vault/"reader.pgpass"
    passfile.write_text(
        f"/var/run/postgresql:5432:empiredb:{release.LOGIN}:"
        +"synthetic-test-only-token-not-sensitive"+"\n"
    )
    passfile.chmod(0o600)
    monkeypatch.setattr(audit,"VAULT",vault)
    monkeypatch.setattr(audit,"PASSFILE",passfile)
    # Nonroot unit fixture must fail closed; no workaround around ownership.
    if vault.stat().st_uid!=0:
        try:
            audit.private_password()
        except RuntimeError as e:
            assert "CREDENTIAL_CUSTODY_UNSAFE" in str(e)
        else:
            raise AssertionError("non-root credential directory accepted")
    passfile.chmod(0o644)
    try:
        audit.private_password()
    except RuntimeError as e:
        assert "CREDENTIAL_CUSTODY_UNSAFE" in str(e)
    else:
        raise AssertionError("world-readable secret file accepted")


def test_real_sentinel_uuid_is_not_financial_evidence():
    assert audit.EXPECTED_ABSENT_UUID=="00000000-0000-4000-8000-000000000000"
    src=audit.CATALOG_SQL
    assert "commercial_events','SELECT')" in src
    assert "tenant_binding_exactly_one" in src
    assert "hba_specific_scram_rule_configured" in src


def test_exact_readonly_cli_flag_required_without_opening_credentials(monkeypatch,capsys):
    assert audit.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out
    monkeypatch.setattr(audit.os,"geteuid",lambda:1000)
    assert audit.main(["--read-only"])==2
    assert "HOLD_ROOT_READONLY_REQUIRED" in capsys.readouterr().out


def test_authenticated_probe_does_not_resolve_forbidden_source_table_names():
    import inspect
    implementation=inspect.getsource(audit.bounded_auth_probe)
    assert "SELECT session_user::text,current_user::text" in implementation
    assert "has_table_privilege" not in implementation
    assert "SET LOCAL ROLE "+'"'+"+ROLE" in implementation
    assert "sentinel_zero_result_verified" in implementation
    admin=audit.CATALOG_SQL
    assert "login_no_commercial_select" in admin
    assert "login_no_orders_select" in admin
    assert "login_no_buyers_select" in admin
    full=inspect.getsource(audit.review)
    assert "ADMIN_READ_ONLY_CATALOG" in full
    assert "if not all(out[\"catalog_checks\"].values())" in full
