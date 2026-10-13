"""Read-only direct USDT capability migration preflight invariants.

Exact production role membership is required; NEVER broaden migrator permissions.
"""
import inspect
import pytest
from scripts import inspect_direct_bsc_capability_migration as preflight


def safe():
    return dict(
        database="empiredb", user="postgres", standby=False,
        migrator=(False, True, False, False, False, False, False),
        tenant_reader=(False, False, False, False, False, False, False),
        migrator_memberships=(("empiredb_tenant_reader", True, True, False, True),),
        tenant_reader_memberships=(),
        parent_tables=(True, True),
        privileges=(True, True, True, True, True),
        targets_absent=(True, True),
    )


def test_exact_existing_role_and_schema_ready_but_migration_still_requires_approval():
    result = preflight.classify(safe())
    assert result["status"] == "READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION"
    assert result["restricted_migrator"] is True
    assert result["tenant_reader_role_restricted"] is True
    assert result["exact_existing_tenant_reader_membership"] is True
    assert result["no_transitive_reader_memberships"] is True
    assert result["migrator_mismatched_flags"] == []
    assert result["migrator_attributes"]["inherits_membership"] is True
    assert result["migration_applied"] is False
    assert result["checkout_activated"] is False
    assert result["payment_or_customer_mutation"] is False
    assert result["release_gates"] == "MIGRATION_APPROVAL_REQUIRED"


@pytest.mark.parametrize("field,value", (
    ("database", "postgres"),
    ("user", "empiredb_app"),
    ("standby", True),
    ("migrator", None),
    ("migrator", (False, False, False, False, False, False, False)),
    ("migrator", (True, True, False, False, False, False, False)),
    ("migrator", (False, True, True, False, False, False, False)),
    ("migrator", (False, True, False, True, False, False, False)),
    ("migrator", (False, True, False, False, True, False, False)),
    ("migrator", (False, True, False, False, False, True, False)),
    ("migrator", (False, True, False, False, False, False, True)),
    ("tenant_reader", None),
    ("tenant_reader", (True, False, False, False, False, False, False)),
    ("tenant_reader", (False, True, False, False, False, False, False)),
    ("tenant_reader", (False, False, True, False, False, False, False)),
    ("migrator_memberships", ()),
    ("migrator_memberships", None),
    ("migrator_memberships", (("empire_payment_approver", True, True, False, True),)),
    ("migrator_memberships", (
        ("empiredb_tenant_reader", True, True, False, True),
        ("empire_payment_approver", True, True, False, True))),
    ("migrator_memberships", (("empiredb_tenant_reader", True, True, True, True),)),
    ("migrator_memberships", (("empiredb_tenant_reader", False, True, False, False),)),
    ("migrator_memberships", (("empiredb_tenant_reader", True, False, False, True),)),
    ("migrator_memberships", (("empiredb_tenant_reader", True, True, False, False),)),
    ("tenant_reader_memberships", None),
    ("tenant_reader_memberships", ("empire_bsc_verifier",)),
    ("parent_tables", (True, False)),
    ("privileges", (True, True, True, False, True)),
    ("privileges", (False, True, True, True, True)),
    ("targets_absent", (False, True)),
    ("targets_absent", (True, False)),
))
def test_any_unexpected_authority_schema_or_membership_fails_closed(field, value):
    assert preflight.classify({**safe(), field: value})["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"


@pytest.mark.parametrize("unsafe", (None, (), (False,), (0,)*7))
def test_missing_or_malformed_migrator_role_diagnostic_fail_closed(unsafe):
    result = preflight.classify({**safe(), "migrator": unsafe})
    assert result["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"
    assert result["migrator_attributes"] is None
    assert result["migrator_mismatched_flags"] == ["missing_or_unreadable_migrator"]


def test_inherit_switch_off_now_fails_exact_authority_contract():
    result = preflight.classify({
        **safe(),
        "migrator": (False, False, False, False, False, False, False),
    })
    assert result["migrator_mismatched_flags"] == ["inherits_membership"]
    assert result["migrator_attributes"]["inherits_membership"] is False
    assert result["migration_applied"] is False


def test_unapproved_flags_denied_even_without_privilege(capsys):
    assert preflight.main([]) == 3
    assert preflight.main(["--apply"]) == 3
    assert "HELD_EXACT_READONLY_FLAG_REQUIRED" in capsys.readouterr().out


def test_read_only_inspector_cannot_mutate_database():
    src = inspect.getsource(preflight)
    for forbidden in ("CREATE TABLE public.", "INSERT INTO public.",
                      "GRANT CONNECT ON DATABASE", "ALTER TABLE public.",
                      "COMMIT;"):
        assert forbidden not in src
    assert 'SET TRANSACTION READ ONLY' in src


def test_exact_migration_rechecks_inherited_authority_inside_transaction():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] /
           "migrations/empiredb/047_direct_bsc_buyer_status_capability.sql").read_text()
    assert "DIRECT047_UNREVIEWED_MIGRATOR_INHERITED_AUTHORITY" in sql
    assert "empiredb_tenant_reader" in sql
    assert "m.inherit_option AND m.set_option AND NOT m.admin_option" in sql
    assert "AND r.rolinherit AND NOT r.rolsuper" in sql
    assert "member.rolname='empiredb_tenant_reader'" in sql
    assert "ALTER TABLE public.direct_bsc_buyer_capabilities FORCE ROW LEVEL SECURITY" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "BEGIN;" in sql and "COMMIT;" in sql


def test_readonly_inspector_v2_contract_version():
    assert preflight.classify(safe())["schema_version"] == (
        "empire.direct-bsc-buyer-capability-migration-preflight.v2"
    )
