"""Retire a former noncanonical offline restore path before it can stop EmpireDB."""
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "empiredb_backup_restore_proof.sh"
DENIAL = "EMPIREDB_OFFLINE_RESTORE_PROOF_RETIRED_CANONICAL_INSTANCE"


def test_previous_offline_restore_is_non_disruptive():
    result = subprocess.run(
        ["bash", str(SCRIPT)], text=True, capture_output=True, timeout=3,
        check=False,
    )
    assert result.returncode == 78
    assert result.stdout.strip() == DENIAL
    assert result.stderr == ""


def test_denial_precedes_every_historic_service_stopping_operation():
    source = SCRIPT.read_text()
    marker = source.index("exit 78")
    assert marker < source.index("systemctl stop pgbouncer")
    assert marker < source.index("pg_ctlcluster 18 main stop")
    assert marker < source.index("rm -rf --one-file-system")
    assert "RETIRED" in source[:marker]
    assert "canonical production database" in source[:marker]
