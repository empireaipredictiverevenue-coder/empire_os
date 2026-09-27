from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/"
    "20260926170755_allow_expired_unsent_outbound_reproposal.sql"
)


def _migration_text() -> str:
    return MIGRATION.read_text()


def test_expired_unsent_intents_do_not_permanently_block_reproposal():
    text = _migration_text().lower()

    assert "buyer_candidate_review_events" not in text
    assert "outbound_proposed" not in text
    assert "i.status in ('pending_approval','approved')" in text
    assert "i.expires_at > clock_timestamp()" in text


def test_real_outbound_history_still_blocks_duplicate_reproposal():
    text = _migration_text().lower()

    for status in (
        "'sending'",
        "'sent'",
        "'delivered'",
        "'replied'",
        "'bounced'",
        "'failed'",
        "'suppressed'",
    ):
        assert status in text

    assert "outbound_suppressions" in text
    assert "normalized_contact=lower(trim(r.contact_email))" in text


def test_review_freshness_and_outreach_readiness_stay_required():
    text = _migration_text().lower()

    assert "r.status='approved'" in text
    assert "interval '7 days'" in text
    assert "r.evidence->>'outreach_ready'" in text
    assert "security definer" in text
    assert "set search_path=''" in text
