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
