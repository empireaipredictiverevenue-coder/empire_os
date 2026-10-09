"""Acceptance coverage for the privileged, *read-only* CRM login probe."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "probe_crm_application_login_contract.py"
spec = spec_from_file_location("crm_login_probe", PROBE)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def catalog(**overrides):
    d = {
        "database": "empiredb",
        "postmaster_epoch": 1234,
        "app_login_present": True,
        "app_login_elevated": False,
        "app_login_bound": False,
        "app_login_evidenced": False,
        "app_login_crm_member": False,
        "app_login_crm_select": False,
        "app_login_binding_update": False,
        "other_bound_logins": 1,
        "other_evidenced_logins": 1,
    }
    d.update(overrides)
    return d


def test_preflight_proves_app_login_is_not_automatically_tenant_login():
    report = module.classify("empiredb", 1234, catalog())
    assert report["canonical_database_instance_verified"]
    assert report["app_login_low_privilege"]
    assert report["app_login_has_active_tenant_binding"] is False
    assert report["independent_evidenced_bound_logins"] == 1
    assert report["app_login_crm_role_member"] is False
    assert report["app_activation_authorized"] is False
    assert report["http_tenant_authentication_verified"] is False
    assert report["live_cross_tenant_proof"] is False


def test_no_tenant_claim_from_role_membership_or_binding_reference_only():
    report = module.classify(
        "empiredb", 1234, catalog(
            app_login_bound=True, app_login_evidenced=True,
            app_login_crm_member=True, app_login_crm_select=True,
        ),
    )
    assert report["app_login_has_active_tenant_binding"]
    assert report["app_login_crm_view_select"]
    assert report["app_activation_authorized"] is False
    assert report["http_tenant_authentication_verified"] is False


def test_privileged_or_binding_writable_login_not_low_privilege():
    for attr in ("app_login_elevated", "app_login_binding_update"):
        report = module.classify("empiredb", 1234, catalog(**{attr: True}))
        assert report["app_login_low_privilege"] is False
        assert not report["app_activation_authorized"]


def test_wrong_instance_never_verifies_canonical_database():
    for db, epoch in (("otherdb", 1234), ("empiredb", 1000)):
        report = module.classify(db, epoch, catalog())
        assert report["canonical_database_instance_verified"] is False
        assert report["app_activation_authorized"] is False


def test_probe_does_not_print_names_or_operate_on_customer_rows():
    source = PROBE.read_text()
    assert "BEGIN TRANSACTION READ ONLY" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert 'os.geteuid() != 0' in source
    assert 'role_changes_performed' in source
    assert 'customer_rows_read' in source
    assert 'runuser", "-u", "postgres"' in source
    assert 'password' not in source.lower().replace("passwords/dsns", "")
    for forbidden in (
        "CREATE ROLE ", "GRANT empire_revenue_crm_reader",
        "ALTER ROLE ", "DELETE FROM ", "INSERT INTO ", "UPDATE public.",
        "SELECT * FROM public.buyers", "SELECT * FROM public.prospects",
    ):
        assert forbidden not in source


def test_unbound_app_view_grant_is_visible_but_never_authorizes_activation():
    report = module.classify(
        "empiredb", 1234, catalog(
            app_login_crm_select=True,
            app_login_crm_buyer_select=True,
            crm_two_views_present=True,
            crm_views_security_invoker=True,
            crm_views_security_barrier=True,
            crm_source_tables_rls_enabled=True,
            crm_grant_public=True,
        )
    )
    assert report["crm_view_effective_permission_without_reader_membership"] is True
    assert report["crm_view_select_grant_public"] is True
    assert report["app_login_has_active_tenant_binding"] is False
    assert report["app_activation_authorized"] is False
    assert report["live_cross_tenant_proof"] is False
    assert report["customer_rows_read"] is False


def test_catalog_query_includes_both_views_and_fails_open_nothing():
    sql = module.build_catalog_statement("'crm_app_fixture'")
    assert "BEGIN TRANSACTION READ ONLY" in sql
    assert "pg_catalog.aclexplode" in sql
    assert "pg_catalog.has_any_column_privilege" in sql
    assert "crm_grant_direct_app" in sql
    assert "crm_grant_inherited" in sql
    assert "crm_grant_public" in sql
    assert "crm_source_tables_rls_enabled" in sql
    assert "revenue_crm_buyers" in sql
    assert "SELECT row_to_json(result)" in sql
    assert "COMMIT;" in sql
