from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/"
    "20260924235408_enterprise_buyer_candidate_review_authority.sql"
)


def _migration_text() -> str:
    return MIGRATION.read_text()


def test_enterprise_review_authority_is_service_role_only_invoker():
    text = _migration_text()
    lowered = text.lower()

    assert "auto_review_enterprise_buyer_candidate" in text
    assert "security definer" not in lowered
    assert "set search_path to ''" in lowered
    assert "revoke execute" in lowered
    assert "from public, anon, authenticated" in lowered
    assert "grant execute" in lowered
    assert "to service_role" in lowered


def test_enterprise_review_authority_preserves_evidence_gates():
    text = _migration_text()

    assert "coalesce(r.company_score,0) < 50" in text
    assert "coalesce(r.decision_score,0) < 0.80" in text
    assert "predictive_revenue_enterprise" in text
    assert "enterprise_fit_revalidated" in text
    assert "contact_personhood_valid" in text
    assert "bound_to_decision_maker" in text
    assert "recipient is suppressed" in text
    assert "existing outbound history requires explicit review" in text


def test_enterprise_review_authority_does_not_grant_consequential_authority():
    text = _migration_text().lower()

    assert "'live_outbound_send',false" in text
    assert "'binding_terms',false" in text
    assert "'payment_action',false" in text
    assert "'actual_revenue',false" in text
    assert "update public.outbound_intents" not in text
    assert "insert into public.commercial_terms" not in text
    assert "insert into public.bsc_payment_requests" not in text
    assert "insert into public.empire_revenue_ledger" not in text
