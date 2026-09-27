from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/"
    "20260926171003_require_verified_personhood_for_buyer_outbound.sql"
)


def _migration_text() -> str:
    return MIGRATION.read_text()


def test_review_listing_requires_verified_named_personhood():
    text = _migration_text().lower()

    assert "list_buyer_reviews_for_outbound" in text
    assert "contact_personhood_valid" in text
    assert "has_named_contact" in text
    assert "outbound_suppressions" in text


def test_reviewed_intent_proposal_fails_closed_on_personhood():
    text = _migration_text().lower()

    assert "propose_reviewed_outbound_intent" in text
    assert "verified contact personhood required" in text
    assert "fresh buyer candidate approval required" in text
    assert "outreach-ready evidence required" in text


def test_auto_review_requires_personhood_before_existing_approval_return():
    text = _migration_text().lower()

    marker = "if r.status='approved' then"
    personhood = (
        "coalesce(lower(r.evidence->>'contact_personhood_valid'),'false') <> 'true'"
    )
    assert personhood in text
    assert text.index(personhood) < text.index(marker)
    assert "has_named_contact" in text
    assert "verified decision-maker contact evidence required" in text


def test_migration_does_not_grant_send_payment_or_revenue_authority():
    text = _migration_text().lower()

    assert "record_outbound_delivery" not in text
    assert "claim_outbound_send" not in text
    assert "insert into public.commercial_terms" not in text
    assert "insert into public.bsc_payment_requests" not in text
    assert "'actual_revenue',false" in text
