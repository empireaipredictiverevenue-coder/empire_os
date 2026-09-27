from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/"
    "20260921123000_high_risk_api_security_lockdown.sql"
)

VIEWS = (
    "affiliate_performance",
    "affiliate_stats",
    "predictive_revenue_view",
    "contractor_referral_view",
    "referral_click_funnel",
    "bounty_payout_summary",
    "referral_funnel_view",
)


def text():
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_is_explicitly_staged_and_scoped():
    sql = text()
    assert "STAGED, NOT APPLIED" in sql
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
    assert "DROP TABLE" not in sql
    assert "DELETE FROM" not in sql
    assert "TRUNCATE TABLE" not in sql
    assert "ALTER TABLE" not in sql


def test_sensitive_views_become_security_invoker_and_private():
    sql = text()
    for view in VIEWS:
        assert f"ALTER VIEW public.{view}" in sql
        assert "security_invoker = true" in sql
        assert f"REVOKE ALL ON TABLE public.{view}" in sql
        assert f"GRANT SELECT ON TABLE public.{view} TO service_role;" in sql


def test_pulse_rollup_is_removed_from_client_roles():
    sql = text()
    assert "REVOKE ALL ON TABLE public.pulse_rollup_hourly" in sql
    assert "GRANT SELECT ON TABLE public.pulse_rollup_hourly TO service_role;" in sql


def test_token_rpcs_are_service_role_only():
    sql = text()
    for signature in (
        "public.get_astra_operational_evidence_token(text)",
        "public.get_commercial_outcome_feedback_token(text, integer)",
    ):
        assert f"REVOKE EXECUTE ON FUNCTION\n  {signature}" in sql
        assert f"GRANT EXECUTE ON FUNCTION\n  {signature}" in sql
        assert "FROM PUBLIC, anon, authenticated;" in sql
        assert "TO service_role;" in sql
