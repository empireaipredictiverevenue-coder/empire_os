from pathlib import Path


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
    assert " delete " not in lowered
    assert "insert into" not in lowered
    assert "provider credentials remain outside empiredb" in lowered
    assert "does not itself authorize sends" in lowered
