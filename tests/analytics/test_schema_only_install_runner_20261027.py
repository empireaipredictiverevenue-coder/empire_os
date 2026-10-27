"""Schema-only release script checks; never invokes privileged migration.

The production script needs deliberate founder operator execution, not pytest.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import os
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/deploy_empiredb_analytics054055_schema_only_20261027.sh"
A = ROOT / "migrations/empiredb/054_first_party_analytics_ledger_held.sql"
B = ROOT / "migrations/empiredb/055_first_party_analytics_erasure_held.sql"


def test_only_original_pinned_migrations_allowed():
    s = RUNNER.read_text()
    assert sha256(A.read_bytes()).hexdigest() == (
        "3a7ae044eba0e30fdaa532bcda1208668712293dfa2a61e3a483505c0de64113"
    )
    assert sha256(B.read_bytes()).hexdigest() == (
        "a49f84cb2b4875df23f4b499de721d750e99066c5d0f10f2b112a0e34be9dd76"
    )
    assert "review_analytics_ledger_schema_20261019" in s
    assert "review_analytics_erasure_preflight_20261019" in s
    assert "review_analytics_live_catalog_20261019" in s
    assert "review_rev051_pgbackrest_backup_readonly" in s
    assert "BACKUP_STATE" in s
    assert "SCHEMA_ONLY_INSTALLATION_VERIFIED" in s
    assert "075_first_party" not in s
    for forbidden in (
        "pg_ctlcluster", "systemctl restart", "CREATE ROLE",
        "GRANT ALL", "DROP TABLE", "curl ", "chmod 777",
        "checkout", "commerce", "lead_smart",
    ):
        assert forbidden not in s


def test_bash_parsing_clean_and_flags_are_required():
    p = subprocess.run(["bash", "-n", str(RUNNER)],
                       capture_output=True, text=True, timeout=3)
    assert p.returncode == 0, p.stderr
    for args in (
        (), ("--apply",), ("--apply", "--other-approved"),
        ("--preflight", "--apply"),
    ):
        p = subprocess.run(["bash", str(RUNNER), *args],
                           capture_output=True, text=True, timeout=3)
        assert p.returncode == 3
        assert "HELD_EXACT_SCOPE_FLAGS_REQUIRED" in p.stderr


def test_no_unprivileged_preflight_can_connect_or_write():
    if os.geteuid() == 0:
        pytest.skip("must verify nonroot denial under real nonroot user")
    p = subprocess.run(["bash", str(RUNNER), "--preflight"],
                       capture_output=True, text=True, timeout=3)
    assert p.returncode == 3
    assert "HELD_ROOT_OPERATOR_REQUIRED" in p.stderr


def test_source_sql_contains_no_runtime_user_creation_or_collection_endpoint():
    for script in (A.read_text(), B.read_text()):
        assert "SET LOCAL ROLE empiredb_migrator;" in script
        assert "FORCE ROW LEVEL SECURITY" in script
        assert "COMMIT;" in script
        assert "CREATE ROLE" not in script
        assert "CREATE LOGIN" not in script
        assert "CREATE SERVER" not in script
