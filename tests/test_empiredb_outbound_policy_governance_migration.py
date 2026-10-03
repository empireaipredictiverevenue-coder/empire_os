from pathlib import Path


PATH = Path("migrations/empiredb/036_outbound_policy_governance.sql")


def test_policy_governance_migration_is_append_only_and_non_activating():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    assert "outbound_policy_manifests" in lowered
    assert "outbound_policy_shadow_runs" in lowered
    assert "activation_authorized boolean not null default false" in lowered
    assert lowered.count("check (activation_authorized = false)") >= 2

    assert "grant " not in lowered
    assert " update " not in lowered
    assert " delete " not in lowered
