from pathlib import Path
import re


PATH = Path("migrations/empiredb/039_outbound_fleet_readiness_certificates.sql")


def test_fleet_readiness_certificate_migration_is_append_only_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_fleet_readiness_certificates" in lowered
    assert "approved_daily_volume" in lowered
    assert "capacity_gap" in lowered
    assert "transport_n_minus_one_survival" in lowered
    assert "domain_n_minus_one_survival" in lowered
    assert "ip_pool_n_minus_one_survival" in lowered
    assert "certificate_fingerprint" in lowered
    assert "mutation_authorized boolean not null default false" in lowered
    assert "provisioning_authorized boolean not null default false" in lowered
    assert "send_authorized boolean not null default false" in lowered
    assert "check (mutation_authorized = false)" in lowered
    assert "check (provisioning_authorized = false)" in lowered
    assert "check (send_authorized = false)" in lowered

    assert "grant " not in lowered
    assert re.search(r"(?m)^\s*delete\s+from\s+", lowered) is None
    assert re.search(r"(?m)^\s*update\s+", lowered) is None
    assert re.search(r"(?m)^\s*insert\s+into\s+", lowered) is None
