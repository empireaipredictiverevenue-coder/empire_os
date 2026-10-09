"""Fail-closed live CRM catalog probe tests, no production connection."""
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / "scripts/verify_revenue_crm_live_contract.py"
    spec = importlib.util.spec_from_file_location("crm_live_contract_test", path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Catalog:
    def __init__(
        self, *,
        role=(False,False,False),
        tenant_function=(True,),
        view_missing=False,
        missing_column=False,
        invoker=True,
        grants=(True,False,False,False),
        base_rls=True,
        policy=("r", "tenant_id = public.empire_current_tenant_id()", True, True),
        helper=(True, "s", "empiredb_migrator"),
    ):
        self.role = role
        self.tenant_function = tenant_function
        self.view_missing = view_missing
        self.missing_column = missing_column
        self.invoker = invoker
        self.grants = grants
        self.base_rls = base_rls
        self.policy = policy
        self.helper = helper
        self.calls = []
        self.last = ""
        self.params = ()
    def execute(self, sql, params=None):
        self.last = sql
        self.params = tuple(params or ())
        self.calls.append((sql,params))
    def fetchone(self):
        q = self.last
        if "pg_catalog.pg_proc" in q:
            return self.helper if "empire_crm_prospect_authorized" in q else self.tenant_function
        if "pg_catalog.pg_roles" in q:
            return self.role
        if "pg_catalog.pg_class c" in q:
            if self.view_missing:
                return None
            return (5, "v", ["security_invoker=true"] if self.invoker else [])
        if "pg_catalog.has_table_privilege" in q:
            return self.grants
        raise AssertionError(q)
    def fetchall(self):
        q = self.last
        if "pg_catalog.pg_attribute" in q:
            from empire_os.revenue_crm_transport import PROSPECT_COLUMNS, BUYER_COLUMNS
            # Both synthetic view OIDs are stubbed as 5 in this fake.
            values = sorted(set(PROSPECT_COLUMNS.split(",") + BUYER_COLUMNS.split(",")))
            return [(c,) for c in values if c != "tenant_id" or not self.missing_column]
        if "pg_catalog.pg_rewrite" in q:
            return [(10, "r", self.base_rls, [])]
        if "pg_catalog.pg_policy" in q:
            if self.policy is None:
                return []
            return (
                self.policy if isinstance(self.policy, list)
                else [self.policy]
            )
        raise AssertionError(q)


def test_catalog_healthy_fixture_is_only_precondition_not_activation():
    result = module().inspect_crm_catalog(Catalog())
    assert result["status"] == "CATALOG_PRECONDITIONS_VERIFIED"
    assert result["blockers"] == []
    assert result["no_data_rows_read"] is True
    assert result["source_schema"]["status"] == "BLOCKED"
    assert result["source_schema"]["tenant_binding_rows_verified"] is False
    assert result["source_schema"]["customer_rows_read"] == 0
    assert result["actual_cross_tenant_read_verified"] is False
    assert result["application_login_tenant_authority_verified"] is False
    assert result["public_api_activation_authorized"] is False
    assert result["buyer_authenticated"] is False


@pytest.mark.parametrize("key,wrong,reason",[
    ("role", None, "CRM_READER_ROLE_MISSING_OR_UNSAFE"),
    ("role", (False,True,False), "CRM_READER_ROLE_MISSING_OR_UNSAFE"),
    ("role", (False,False,True), "CRM_READER_ROLE_MISSING_OR_UNSAFE"),
    ("tenant_function", None, "TRUSTED_TENANT_FUNCTION_NOT_VERIFIED"),
    ("view_missing", True, "PROSPECTS_VIEW_MISSING_OR_NOT_VIEW"),
    ("missing_column", True, "PROSPECTS_VIEW_COLUMNS_MISSING"),
    ("invoker", False, "BUYERS_VIEW_NOT_SECURITY_INVOKER"),
    ("grants", (True,True,False,False), "BUYERS_ROLE_READ_GRANTS_NOT_SAFE"),
    ("base_rls", False, "PROSPECTS_BASE_RLS_NOT_VERIFIED"),
    ("policy", None, "BUYERS_BASE_RLS_NOT_VERIFIED"),
    ("policy", ("r", "true", True, True), "PROSPECTS_BASE_RLS_NOT_VERIFIED"),
    ("policy", ("r", "tenant_id = public.empire_current_tenant_id() OR true", True, True),
     "BUYERS_BASE_RLS_NOT_VERIFIED"),
    ("policy", ("r", "NOT tenant_id = public.empire_current_tenant_id()", True, True),
     "PROSPECTS_BASE_RLS_NOT_VERIFIED"),
    ("helper", None, "GUARDED_PROSPECT_SCOPE_FUNCTION_NOT_VERIFIED"),
    ("helper", (True, "v", "empiredb_migrator"), "GUARDED_PROSPECT_SCOPE_FUNCTION_NOT_VERIFIED"),
])
def test_unproven_catalog_item_is_explicit_blocker(key, wrong, reason):
    scenario = {key:wrong}
    if key=="helper":
        scenario["policy"]=(
            "r","empire_crm_prospect_authorized(id)",True,True,
        )
    value = module().inspect_crm_catalog(Catalog(**scenario))
    assert value["status"] == "BLOCKED"
    assert reason in value["blockers"]
    assert value["public_api_activation_authorized"] is False


def test_missing_connection_cannot_report_absent_views(monkeypatch, capsys):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)
    assert module().run() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "CONNECTION_NOT_CONFIGURED"
    assert report["blockers"] == ["APPROVED_DATABASE_CONNECTION_UNAVAILABLE"]
    assert "views" not in report
    assert report["no_data_rows_read"] is True


def test_auth_failure_hides_dsn_and_driver_exception(monkeypatch, capsys):
    secret="postgresql://sysadmin:very-private-password@not-running/empire"
    monkeypatch.setenv("EMPIREDB_DSN",secret)
    assert module().run() == 2
    result = capsys.readouterr().out
    assert secret not in result
    assert "very-private-password" not in result
    assert json.loads(result)["status"] == "CONNECTION_OR_CATALOG_ACCESS_FAILED"


def test_catalog_probe_only_uses_static_catalog_queries():
    cursor = Catalog()
    module().inspect_crm_catalog(cursor)
    assert len(cursor.calls) > 0
    for sql, _ in cursor.calls:
        assert "INSERT " not in sql
        assert "DELETE " not in sql
        assert "UPDATE " not in sql
        assert "SELECT *" not in sql
        assert "FROM public.revenue_crm_prospects" not in sql
        assert "FROM public.revenue_crm_buyers" not in sql


def test_extra_public_permissive_policy_cannot_override_tenant_gate():
    allowed = ("r", "tenant_id = public.empire_current_tenant_id()", True, True)
    public_bypass = ("r", "true", True, True)
    result = module().inspect_crm_catalog(
        Catalog(policy=[allowed,public_bypass])
    )
    assert result["status"] == "BLOCKED"
    assert "BUYERS_BASE_RLS_NOT_VERIFIED" in result["blockers"]
    assert result["public_api_activation_authorized"] is False


def test_policy_for_unrelated_non_member_role_is_not_tenant_bypass():
    allowed = ("r", "tenant_id = public.empire_current_tenant_id()", True, True)
    not_applicable = ("r", "true", True, False)
    result = module().inspect_crm_catalog(
        Catalog(policy=[allowed,not_applicable])
    )
    assert result["status"] == "CATALOG_PRECONDITIONS_VERIFIED"
    assert result["actual_cross_tenant_read_verified"] is False
