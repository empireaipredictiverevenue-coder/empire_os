from pathlib import Path
import re


PATH = Path("migrations/empiredb/040_outbound_content_claim_memory.sql")


def test_content_claim_memory_migration_is_append_only_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_content_family_events" in lowered
    assert "outbound_content_family_snapshots" in lowered
    assert "outbound_claim_verification_events" in lowered
    assert "claim_hash" in lowered
    assert "verification_key" in lowered
    assert "mutation_authorized boolean not null default false" in lowered
    assert lowered.count("check (mutation_authorized = false)") >= 2

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
