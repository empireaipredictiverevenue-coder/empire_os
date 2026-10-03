from pathlib import Path
import re


PATH = Path("migrations/empiredb/035_outbound_sender_estate_inventory.sql")


def test_sender_estate_migration_is_staged_and_non_authorizing():
    sql = PATH.read_text(encoding="utf-8")
    lowered = sql.lower()

    for table in (
        "outbound_transports",
        "outbound_domains",
        "outbound_mailboxes",
        "outbound_sender_pools",
        "outbound_pool_members",
        "outbound_capacity_ledger",
        "outbound_seed_mailboxes",
    ):
        assert table in lowered

    assert "grant " not in lowered
    # Foreign-key clauses such as ON DELETE RESTRICT are safety controls, not
    # destructive DML. Block executable DELETE statements instead.
    assert re.search(r"(?m)^\\s*delete\\s+from\\s+", lowered) is None
    assert re.search(r"(?m)^\\s*update\\s+", lowered) is None
    assert re.search(r"(?m)^\\s*insert\\s+into\\s+", lowered) is None
    assert "provider credentials remain outside empiredb" in lowered
    assert "set_limit" in lowered
    assert "reserve" in lowered
    assert "consume" in lowered
    assert "release" in lowered
    assert "replayable and non-authorizing" in lowered
