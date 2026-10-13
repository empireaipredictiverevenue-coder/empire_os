"""Private reader 049: canonical production preflight must be read only."""
import inspect
import pytest
from scripts import inspect_direct_bsc_private_reader_049 as gate


def safe():
    return {
        "identity": ("empiredb", "postgres", False),
        "capability": (True, True, "empiredb_migrator", 0, 0),
        "reader_role_absent": True,
        "reader_function_absent": True,
        "migrator_incoming_memberships": 0,
        "tables": (True, True, True),
        "selects": (True, True, True),
    }


def test_exact_sealed_state_ready_for_separate_approval_not_activated():
    output=gate.classify(safe())
    assert output["status"] == "READY_FOR_SEPARATELY_APPROVED_PRIVATE_READER_049"
    assert output["migration_049_applied"] is False
    assert output["reader_login_assigned"] is False
    assert output["buyer_status_endpoint_activated"] is False
    assert output["payment_execution"] is False
    assert output["release_gate"] == "FOUNDER_APPROVAL_049_REQUIRED"


@pytest.mark.parametrize("field,mutated", (
    ("identity", ("other", "postgres", False)),
    ("identity", ("empiredb", "empiredb_app", False)),
    ("identity", ("empiredb", "postgres", True)),
    ("capability", (False, True, "empiredb_migrator", 0, 0)),
    ("capability", (True, False, "empiredb_migrator", 0, 0)),
    ("capability", (True, True, "postgres", 0, 0)),
    ("capability", (True, True, "empiredb_migrator", 1, 0)),
    ("capability", (True, True, "empiredb_migrator", 0, 1)),
    ("capability", None),
    ("reader_role_absent", False),
    ("reader_function_absent", False),
    ("migrator_incoming_memberships", 1),
    ("tables", (True, True, False)),
    ("selects", (True, False, True)),
    ("selects", (True, True, False)),
))
def test_role_source_or_acl_drift_holds(field, mutated):
    assert gate.classify({**safe(),field:mutated})["status"] == (
        "HELD_PRIVATE_READER_049_GATES"
    )


def test_requires_exact_readonly_approval_and_refuses_mutation(capsys):
    assert gate.main([]) == 3
    assert gate.main(["--apply"]) == 3
    assert "HELD_EXACT_READONLY_PREFLIGHT_FLAG_REQUIRED" in capsys.readouterr().out
    src=inspect.getsource(gate)
    assert "SET TRANSACTION READ ONLY" in src
    for forbidden in (
        "CREATE ROLE ", "GRANT EXECUTE", "CREATE POLICY ",
        "COMMIT;", "UPDATE public.", "INSERT INTO public.",
        "DELETE FROM public.", "CREATE FUNCTION public."
    ):
        assert forbidden not in src
