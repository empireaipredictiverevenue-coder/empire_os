from pathlib import Path


def test_personhood_authority_is_column_scoped():
    text = Path(
        "migrations/empiredb/"
        "020_outbound_approver_personhood_read.sql"
    ).read_text()

    assert "GRANT SELECT (id, business_name)" in text
    assert "TO empire_outbound_approver" in text
    assert "GRANT SELECT ON public.prospects" not in text


def test_postgres_policy_blocks_remain_visible():
    text = Path(
        "empire_os/outbound_role_transport.py"
    ).read_text()

    assert 'sqlstate == "P0001"' in text
    assert "standing authority blocked:" in text


def test_policy_block_does_not_poison_worker_health():
    text = Path(
        "scripts/outbound_governor_worker.py"
    ).read_text()

    assert '"standing authority blocked:" in message' in text
    assert '"nonfatal": True' in text
