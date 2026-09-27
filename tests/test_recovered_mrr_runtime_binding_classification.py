from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260926201550_classify_recovered_mrr_runtime_bindings.sql"
)


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_recovered_mrr_is_mapped_to_modern_runtime_targets():
    text = sql()

    assert "'ai_closer','MERGE_MODERNIZE','buyer_conversation_engine','HIGH'" in text
    assert "'contractor_exchange','MERGE','commercial_exchange','HIGH'" in text
    assert "'forecast','MERGE','predictive_intelligence','HIGH'" in text
    assert "'lead_score','MERGE','lead_scoring_v2_and_omega','HIGH'" in text
    assert "'seo_optimizer','MERGE','search_growth_command','HIGH'" in text


def test_noncore_or_obsolete_products_do_not_auto_activate():
    text = sql()

    assert "'meetily','ARCHIVE_NONCORE'" in text
    assert "'sovereign_agi_matrix','ARCHIVE_MERGE_INTERNAL'" in text
    assert "'all_products','HOLD_REDESIGN'" in text
    assert "'hexstrike','HOLD_NONCORE'" in text


def test_classification_does_not_approve_prices_or_revenue():
    text = sql()

    assert "'price_carry_forward_authorized',false" in text
    assert "'commercial_activation','PENDING_ECONOMICS_REVIEW'" in text
    assert "'actual_revenue',false" in text
    assert "'price_mutated',false" in text
    assert "'payment_mutated',false" in text


def test_conflicted_scraper_family_requires_repricing():
    text = sql()

    assert "'elite_scraper','MERGE_REPRICE'" in text
    assert "Legacy prices conflict" in text
