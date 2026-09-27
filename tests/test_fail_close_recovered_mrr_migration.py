from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260926202007_fail_close_recovered_mrr_until_verified.sql"
)


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_recovered_skus_are_inactive_until_verified():
    text = sql()

    assert "SET active=false" in text
    assert "'RECOVERED_INACTIVE_PENDING_VERIFICATION'" in text
    assert "'sellable_now',false" in text
    assert "'activation_authority','founder_or_verified_catalog_process'" in text


def test_recovery_evidence_is_preserved():
    text = sql()

    assert "no product/version evidence is deleted" in text
    assert "recovery_batch" in text
    assert "'payment_mutated',false" in text
    assert "'revenue_recognized',false" in text


def test_verified_catalog_versions_are_not_blindly_deactivated():
    text = sql()

    assert "catalog_state <> 'VERIFIED'" in text
    assert "v.version_state='VERIFIED'" in text
