from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260923082430_phase4_buyer_scout_candidates.sql"
)


def test_buyer_scout_candidate_schema_is_service_role_only():
    text = MIGRATION.read_text()

    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FROM PUBLIC, anon, authenticated" in text
    assert "TO service_role" in text
    assert "SECURITY INVOKER" in text
    assert "SECURITY DEFINER" not in text


def test_buyer_scout_candidate_schema_does_not_fake_buy_signal():
    text = MIGRATION.read_text()

    assert "direct_buyer_score" in text
    assert "buy_signal_score" not in text
    assert "target_buyer_pools" in text
    assert "target_product_codes" in text
    assert "target_corridor_keys" in text
    assert "query_evidence" in text
    assert "site_evidence" in text


def test_buyer_scout_candidate_rpc_grants_no_commercial_authority():
    text = MIGRATION.read_text()

    assert "'outreach_authorized',false" in text
    assert "'commercial_terms_verified',false" in text
    assert "'actual_revenue',false" in text
    assert "canonical_buyer_id" in text
    assert "canonical_prospect_id" in text
