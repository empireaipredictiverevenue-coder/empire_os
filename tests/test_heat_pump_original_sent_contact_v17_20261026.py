"""V17: authenticated Workspace SENT receipts override stale draft-only status."""
from datetime import datetime, timezone
from pathlib import Path

from empire_os.heat_pump_commercial_review import review
import empire_os.heat_pump_commercial_review as commercial

ROOT=Path("/srv/empire_os")
TARGETS=("goodenergy.co.uk","altoenergy.co.uk","appianheatpumps.com")


def test_original_authenticated_send_evidence_is_joined_without_buyer_claim():
    result=review(ROOT,now=datetime.now(timezone.utc))
    rows={row["domain"]:row for row in result["research_inventory"]}
    for domain in TARGETS:
        actual=rows[domain]
        assert actual["original_contact_history_state"]=="WORKSPACE_SENT_ALREADY_CONTACTED"
        assert actual["workspace_sent_metadata_observed"] is True
        assert actual["current_email_status"]=="WORKSPACE_SENT_OBSERVED_NOT_DELIVERY_OR_ACCEPTANCE"
        assert actual["founder_next_action"]=="WAIT_FOR_WORKSPACE_REPLY_NO_DUPLICATE_FIRST_TOUCH"
        assert actual["workspace_draft_preparation"] is not None
        assert actual["direct_purchase_statement_verified"] is False
        assert actual["paid_pilot_verified"] is False
        assert actual["outbound_authorized"] is False
    assert result["workspace_sent_company_count"] >= 3
    assert result["workspace_sent_is_not_delivery_or_buyer_acceptance"] is True
    assert result["verified_payable_buyers"] == 0
    assert result["outbound_sent"] is False


def test_missing_contact_history_fails_closed_not_inferred_from_old_draft(monkeypatch):
    def missing_contact(*args,**kwargs):
        return {"available": False}
    monkeypatch.setattr(commercial,"load_original_contact_context",missing_contact)
    result=commercial.review(ROOT,now=datetime.now(timezone.utc))
    rows={row["domain"]:row for row in result["research_inventory"]}
    for domain in TARGETS:
        assert rows[domain]["original_contact_history_state"]=="SOURCE_UNAVAILABLE"
        assert rows[domain]["workspace_sent_metadata_observed"] is False
        assert rows[domain]["current_email_status"]=="PRIOR_DRAFT_CREATION_ONLY_REVERIFY_BEFORE_ANY_SEND"
        assert rows[domain]["outbound_authorized"] is False
    assert result["workspace_sent_company_count"] == 0
