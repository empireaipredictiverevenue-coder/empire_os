from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/"
    "20260922223600_predictive_outcome_timing.sql"
)


def sql():
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_is_staged_read_contract_only():
    text = sql()
    assert "STAGED, NOT APPLIED" in text
    assert "BEGIN;" in text
    assert "COMMIT;" in text
    assert "CREATE OR REPLACE FUNCTION public.get_commercial_outcome_feedback" in text
    assert "INSERT INTO" not in text
    assert "UPDATE public.fulfilment_orders" not in text
    assert "DELETE FROM" not in text
    assert "TRUNCATE" not in text


def test_feedback_contract_exposes_verified_timing_anchor():
    text = sql().replace(" ", "")
    assert "'fulfilment_created_at',o.created_at" in text
    assert "'revenue_recognized_at',ce.occurred_at" in text
    assert "'conversion_outcome',co.conversion_outcome" in text
    assert "'product_id',o.product_id" in text


def test_feedback_reader_permissions_do_not_expand():
    text = sql()
    assert (
        "REVOKE ALL ON FUNCTION public.get_commercial_outcome_feedback(integer)"
        in text
    )
    assert (
        "FROM PUBLIC,anon,authenticated,empire_outcome_recorder,"
        "empire_revenue_recognizer;" in text
    )
    assert (
        "GRANT EXECUTE ON FUNCTION public.get_commercial_outcome_feedback(integer)"
        in text
    )
    assert "TO service_role;" in text
