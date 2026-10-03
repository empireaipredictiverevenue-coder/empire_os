from pathlib import Path
import re


PATH = Path("migrations/empiredb/038_outbound_capacity_reservation_leases.sql")


def test_capacity_reservation_migration_is_staged_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "reservation_key" in lowered
    assert "idempotency_key" in lowered
    assert "lease_expires_at" in lowered
    assert "idx_outbound_capacity_idempotency" in lowered
    assert "where idempotency_key is not null" in lowered
    assert "outbound_capacity_reservation_identity_required" in lowered
    assert "outbound_capacity_reserve_lease_required" in lowered

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
    assert "send_authorized" not in lowered
