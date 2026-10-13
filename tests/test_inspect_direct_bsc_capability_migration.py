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
