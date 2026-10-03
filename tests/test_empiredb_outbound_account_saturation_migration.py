from pathlib import Path
import re


PATH = Path("migrations/empiredb/040_outbound_account_saturation_dimensions.sql")


def test_account_saturation_migration_is_staged_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "parent_company_key" in lowered
    assert "corridor_key" in lowered
    assert "event_kind" in lowered
    assert "idx_outbound_contact_pressure_parent" in lowered
    assert "idx_outbound_contact_pressure_corridor" in lowered
    assert "idx_outbound_contact_pressure_company_kind" in lowered

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
