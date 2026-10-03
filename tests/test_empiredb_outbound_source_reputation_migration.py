from pathlib import Path
import re


PATH = Path("migrations/empiredb/039_outbound_source_reputation_memory.sql")


def test_source_reputation_migration_is_append_only_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_source_reputation_events" in lowered
    assert "outbound_source_reputation_snapshots" in lowered
    assert "event_kind" in lowered
    assert "hard_bounce" in lowered
    assert "complaint" in lowered
    assert "positive_reply" in lowered
    assert "revenue" in lowered
    assert "mutation_authorized boolean not null default false" in lowered
    assert "check (mutation_authorized = false)" in lowered

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
