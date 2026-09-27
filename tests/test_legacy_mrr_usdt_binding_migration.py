from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260926192421_recover_legacy_mrr_bind_usdt_bsc.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_recovery_binds_legacy_mrr_to_usdt_bsc():
    sql = migration_sql()

    assert "legacy_mrr_usdt_bsc_v1" in sql
    assert "'settlement','USDT_BSC'" in sql
    assert "'settlement_asset','USDT'" in sql
    assert "'settlement_network','BSC'" in sql
    assert "'settlement_chain_id',56" in sql


def test_recovery_preserves_legacy_evidence_instead_of_rewriting_usdc():
    sql = migration_sql()

    assert "Historical USDC/Solana evidence is preserved" in sql
    assert "COMMENT ON COLUMN public.crypto_payment_requests.amount_usdc" in sql
    assert "COMMENT ON COLUMN public.empire_revenue_ledger.usdc_amount" in sql
    assert "public.bsc_payment_requests.amount_usdt" in sql


def test_recovered_products_remain_fail_closed_for_economics():
    sql = migration_sql()

    assert "'commercial_activation','PENDING_ECONOMICS_REVIEW'" in sql
    assert "'economics_founder_approved',false" in sql
    assert "'acquisition_cost_not_recovered_from_legacy_sources'" in sql
    assert "'fulfilment_cost_not_recovered_from_legacy_sources'" in sql
    assert "'margin_policy_not_recovered_from_legacy_sources'" in sql
    assert "auto_verify_commercial_product_version" not in sql


def test_price_conflicts_are_not_silently_resolved():
    sql = migration_sql()

    assert "'PRICE_CONFLICT'" in sql
    assert "'state','CONFLICT'" in sql
    assert "'pricing_candidate_cents'" in sql
    assert "'metadata_candidate_cents'" in sql
    assert "'REQUIRES_FOUNDER_PRICE_RESOLUTION'" in sql


def test_demo_and_e2e_subscriptions_are_removed_from_active_mrr():
    sql = migration_sql()

    assert "subscription_status='CANCELED'" in sql
    assert "customer_account_id LIKE 'demo_%'" in sql
    assert "customer_account_id LIKE 'e2e_%'" in sql
    assert "DEMO_ONLY_NON_REVENUE" in sql
    assert "E2E_TEST_ONLY_NON_REVENUE" in sql
