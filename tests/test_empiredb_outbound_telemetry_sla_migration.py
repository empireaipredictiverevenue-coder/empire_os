from pathlib import Path
import re


PATH = Path("migrations/empiredb/043_outbound_telemetry_sla.sql")


def test_telemetry_sla_migration_is_append_only_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_telemetry_heartbeats" in lowered
    assert "outbound_telemetry_sla_snapshots" in lowered
    assert "critical_blind" in lowered
    assert "critical_stale" in lowered
    assert "critical_partial" in lowered
    assert "posture in ('current','partial','stale','blind')" in lowered
    assert "mutation_authorized boolean not null default false" in lowered
    assert "send_authorized boolean not null default false" in lowered
    assert "check (mutation_authorized = false)" in lowered
    assert "check (send_authorized = false)" in lowered

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
