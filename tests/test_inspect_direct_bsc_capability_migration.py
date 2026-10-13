"""Read-only direct USDT capability migration preflight invariants."""
import pytest
from scripts import inspect_direct_bsc_capability_migration as preflight


def safe():
    return dict(
        database="empiredb", user="postgres", standby=False,
        migrator=(False, False, False, False, False, False, False),
        parent_tables=(True, True),
        privileges=(True, True, True, True, True),
        targets_absent=(True, True),
    )


def test_readonly_migration_preflight_requires_exact_canonical_state():
    result = preflight.classify(safe())
    assert result["status"] == "READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION"
    assert result["mode"] == "READ_ONLY"
    assert result["migration_applied"] is False
    assert result["checkout_activated"] is False
    assert result["payment_or_customer_mutation"] is False


@pytest.mark.parametrize("field,value", (
    ("database", "postgres"),
    ("user", "empiredb_app"),
    ("standby", True),
    ("migrator", None),
    ("migrator", (True, False, False, False, False, False, False)),
    ("migrator", (False, False, True, False, False, False, False)),
    ("parent_tables", (True, False)),
    ("privileges", (True, True, True, False, True)),
    ("privileges", (False, True, True, True, True)),
    ("targets_absent", (False, True)),
    ("targets_absent", (True, False)),
))
def test_partial_or_unsafe_catalog_fails_closed(field, value):
    report = {**safe(), field: value}
    assert preflight.classify(report)["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"


def test_unapproved_flags_denied_even_without_root(capsys):
    assert preflight.main([]) == 3
    assert preflight.main(["--apply"]) == 3
    assert "HELD_EXACT_READONLY_FLAG_REQUIRED" in capsys.readouterr().out


def test_no_schema_migration_or_write_methods_in_catalog_inspector():
    import inspect
    src = inspect.getsource(preflight)
    for forbidden in ("CREATE TABLE public.", "INSERT INTO public.",
                      "GRANT CONNECT ON DATABASE", "ALTER TABLE public.",
                      "COMMIT;"):
        assert forbidden not in src


def test_diagnostic_exposes_only_safe_role_attribute_booleans():
    facts = safe()
    facts["migrator"] = (False, True, False, False, False, False, False)
    result = preflight.classify(facts)
    assert result["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"
    assert result["migrator_mismatched_flags"] == ["inherits_membership"]
    assert result["migrator_attributes"]["inherits_membership"] is True
    assert result["migrator_attributes"]["superuser"] is False
    assert result["migration_applied"] is False


def test_unsafe_superuser_remains_held_even_with_other_preflight_checks_green():
    facts = safe()
    facts["migrator"] = (False, False, True, False, False, False, False)
    result = preflight.classify(facts)
    assert result["restricted_migrator"] is False
    assert result["migrator_mismatched_flags"] == ["superuser"]
    assert result["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"


@pytest.mark.parametrize("unsafe", (None, (), (False,), (0,)*7))
def test_missing_or_malformed_migrator_role_diagnostic_fail_closed(unsafe):
    facts = safe()
    facts["migrator"] = unsafe
    result = preflight.classify(facts)
    assert result["status"] == "HELD_SCHEMA_OR_AUTHORITY_DRIFT"
    assert result["migrator_attributes"] is None
    assert result["migrator_mismatched_flags"] == ["missing_or_unreadable_migrator"]


def test_exact_expected_migrator_only_profile_remains_unchanged():
    result = preflight.classify(safe())
    assert result["restricted_migrator"] is True
    assert result["migrator_mismatched_flags"] == []
    assert result["status"] == "READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION"
