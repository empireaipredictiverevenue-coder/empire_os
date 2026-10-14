"""Extra founder-review prospect reuses existing rapport and no-send policy."""
from pathlib import Path
import json

from scripts.review_search_first_sale_rapport import review_candidate

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/commercial/SEARCH_FIRST_SALE_NAMED_OWNER_BACKUP_20261014.json"


def candidate():
    report = json.loads(PATH.read_text(encoding="utf-8"))
    return report, report["candidate"]


def test_named_industry_email_and_official_leadership_have_grounded_sources():
    report, row = candidate()
    assert report["status"] == "FOUNDER_OUTREACH_OWNER_REVIEW_ONLY"
    assert row["company_name"] == "Empire State Fire Sprinkler Corp."
    assert row["email"] == "helen@empirefire.net"
    assert row["person"] == "Helen DiLorenzo"
    assert row["contact_route"] == "person_bound"
    assert row["recipient_identity_currently_verified"] is False
    assert "member.nfsa.org" in report["identity_sources"]["industry_member_named_email"]
    assert "empirefire.net" in report["identity_sources"]["company_official_about"]
    assert "j20260717" in row["source_url"]
    assert "not independently established" in row["observation"]
    assert report["product_if_requested_after_real_reply"]["list_price_usd"] == 199
    assert report["product_if_requested_after_real_reply"]["order_revenue_verified"] is False


def test_existing_rapport_policy_passes_only_copy_and_refuses_send():
    report, row = candidate()
    decision = review_candidate(row)
    assert decision["next_action"] == "DRAFT_RAPPORT_TOUCH"
    assert decision["copy_review"]["eligible"] is True
    assert decision["copy_review"]["blockers"] == []
    assert decision["current_recipient_identity_cleared"] is False
    assert decision["canonical_suppression_cleared"] is False
    assert decision["professional_mailbox_send_authorized"] is False
    assert decision["founder_send_approved"] is False
    assert decision["send_authorized"] is False
    assert decision["outbound_sent"] is False
    assert decision["execution_authority"] == "none"
    assert decision["strict_verified_reply_required"] is True
    assert decision["automatic_followup"] is False
    assert decision["product_pitch_in_first_touch"] is False


def test_no_imagined_results_revenue_or_traffic_activation():
    report, row = candidate()
    body = row["body"].casefold()
    assert "$199" not in body
    assert "competitor search gap" not in body
    assert "https://empire-ai.co.uk/buy" not in body
    assert "ranked" not in body and "lost leads" not in body
    assert "book a call" not in body and "15 minutes" not in body
    assert all(v is False for v in report["governance"].values())
    assert all(
        v is False
        for k, v in report["product_if_requested_after_real_reply"].items()
        if k.endswith("_verified")
    )


def test_evidence_supplement_does_not_override_existing_primary_shortlist():
    report, _ = candidate()
    assert "THREE_PROSPECTS_REVIEW" in report["context"]
    primary = ROOT / "docs/commercial/SEARCH_FIRST_SALE_THREE_PROSPECTS_REVIEW_20261014.md"
    assert primary.is_file()
    content = (ROOT / "docs/commercial/SEARCH_FIRST_SALE_NAMED_OWNER_BACKUP_20261014.md").read_text()
    assert "Green Coast primary" in content
    assert "no ranking" in content or "not which" in content
    assert "No email" in content
