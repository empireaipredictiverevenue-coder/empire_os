from pathlib import Path


PATH = Path("migrations/empiredb/035_outbound_deliverability_control_plane.sql")


def test_empiredb_deliverability_migration_is_staged_append_only():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_deliverability_observations" in lowered
    assert "outbound_ringleader_decisions" in lowered
    assert "outbound_sender_pool_observations" in lowered
    assert "outbound_provider_policy_snapshots" in lowered
    assert "outbound_reputation_economic_events" in lowered
    assert "outbound_contact_pressure_events" in lowered

    assert "grant " not in lowered
    assert " update " not in lowered
    assert " delete " not in lowered
    assert "mutation_authorized boolean not null default false" in lowered
    assert "check (mutation_authorized = false)" in lowered
