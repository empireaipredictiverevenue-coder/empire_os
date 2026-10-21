"""Guarded original registry check cannot silently use privileged SQL writers."""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / (
    "scripts/run_guarded_predictive_registry_readonly_20261021.sh"
)


@pytest.mark.parametrize("args", [
    (), ("--check",), ("--run-read-only", "abc"),
    ("--write", "f" * 40), ("--run-read-only", "f" * 40),
])
def test_no_implicit_privileged_execution(args):
    completed = subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True,
        text=True, check=False, timeout=10,
    )
    assert completed.returncode != 0
    assert "REGISTRY_READ_FINISHED" not in completed.stdout


def test_exact_source_package_and_no_database_or_role_mutation():
    code = SCRIPT.read_text()
    for required in (
        '[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]',
        'cat-file -t "$COMMIT"',
        'archive "$COMMIT" --',
        '[[ "$(stat -c \'%u\' "$TARGET")" == 0 ]]',
        'find "$TARGET" -type l -print -quit',
        'find "$TARGET" ! -user root -print -quit',
        'find "$TARGET" -perm /022 -print -quit',
        "source_hash", "sha256sum",
        "chown -R root:root", 'chmod 0555', 'chmod 0444',
        "PGPASSFILE=", 'PYTHONPATH="$TARGET"',
        '"$PY" -P -B -m scripts.review_predictive_registry_source_admission_20261021 --read-only',
        "LIVE_DATABASE_NOT_QUERIED=true",
        "REGISTRY_READ_FINISHED_NO_PERMISSION_OR_DATA_WRITES=true",
    ):
        assert required in code
    for forbidden in (
        "ALTER ROLE", "GRANT SELECT", "CREATE USER", "CREATE ROLE",
        "DROP TABLE", "psql -", "curl ", "chmod 777",
    ):
        assert forbidden not in code


def test_original_reader_only_and_no_forecast_promotion():
    src = (SCRIPT.parents[1] /
        "empire_os/predictive_existing_tenant_registry_receipts.py").read_text()
    assert "SET TRANSACTION READ ONLY" in src
    assert "SET LOCAL ROLE " in src
    assert "REGISTRY_META_SQL" in src
    assert "REGISTRY_POLICY_SQL" in src
    assert "ROWS_SQL" in src
    assert '"original_forecast_immutable_registration_verified": False' in src
    assert '"forecast_registered_before_outcome_verified": False' in src
    assert '"independent_revenue_settlement_verified": False' in src
    assert '"customer_training_labels_admitted": False' in src
