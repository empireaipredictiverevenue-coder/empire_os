"""Current real email wording regression; test-only mocks do not create business data."""
from __future__ import annotations
import json
from pathlib import Path

from empire_os.buyer_mail_semantics import classify_visible_claims
from empire_os.buyer_thread_discovery import discover
from empire_os.publisher_commercial_triage import publisher_next_evidence
from scripts.reconcile_buyer_email_relationships import annotate_new_engaged_commercial_roles
from tests.test_buyer_thread_discovery import FakeService, thread, attach, NOW
from tests.test_connected_gmail_buyer_metadata import inputs

# Exact top-level statements from the 20 October SolarBriton reply,
# not guessed performance figures or an asserted contract.
REPLY = (
    "The single-installer, accepted-outcome approach works for us, and "
    "we agree nothing goes live and no data is shared until terms are signed "
    "and coverage is verified. 30 days will work for us too. "
    "Fee: as a negotiating target only, 70% of the amount the installer "
    "actually pays for each accepted event, with a minimum of £35 per event."
)
PILOT = "PUBLISHER_ACCEPTED_OUTCOME_PILOT_REPORTED"
RATE = "PUBLISHER_REVENUE_SHARE_TARGET_REPORTED"
TERMS = "PUBLISHER_SIGNED_TERMS_AND_COVERAGE_REQUIRED_REPORTED"


def test_real_publisher_reply_is_report_only_and_quoted_old_reply_ignored():
    codes = classify_visible_claims(REPLY)
    assert set((PILOT, RATE, TERMS)).issubset(codes)
    assert classify_visible_claims(
        "Thanks for the update.\n\nOn 20 October, Abhishek wrote:\n" + REPLY
    ) == []
    assert classify_visible_claims(REPLY, outbound=True) == []


def test_existing_gmail_discovery_to_original_founder_supplier_queue(tmp_path: Path):
    import base64
    from tests.test_buyer_thread_discovery import UNKNOWN
    old, index = inputs()
    source = thread(UNKNOWN, "solarbriton.co.uk",
                    sender="marketing@solarbriton.co.uk")
    source["messages"][1]["payload"]["body"]["data"] = (
        base64.urlsafe_b64encode(REPLY.encode()).decode().rstrip("=")
    )
    evidence = discover(FakeService({UNKNOWN: source}), old, now=NOW)
    assert evidence["unlinked_review_count"] == 1
    updated = attach(old, index, evidence)
    item = updated["buyer_new_thread_review"][0]
    assert set(item["last_reply_signals"]) == {PILOT, RATE, TERMS}
    assert item["status"] == "REVIEW_IDENTITY_NO_SEND"
    decision = publisher_next_evidence(item)
    assert decision["next_action"] == "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
    assert decision["reported_proposed_share"] is True
    assert decision["buyer_capacity_verified"] is False
    assert decision["quote_authorized"] is False

    doc = tmp_path / "docs/commercial"
    doc.mkdir(parents=True)
    (doc / "PUBLISHER_SUPPLY_RECRUITMENT_EVIDENCE_20261010.json").write_text(
        json.dumps({"schema_version": "empire.publisher_supply_recruitment_evidence.v1",
                    "items": [{"domain": "solarbriton.co.uk",
                               "company": "Solar Briton",
                               "role": "TRAFFIC_SUPPLY_HYPOTHESIS"}]})
    )
    report = {"new_engaged_buyer_identity_review_queue": [item]}
    annotate_new_engaged_commercial_roles(report, root=tmp_path)
    assert report["new_engaged_publisher_supply_review_count"] == 1
    found = report["new_engaged_publisher_supply_review_queue"][0]
    assert found["next_action"] == "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
    assert found["publisher_next_evidence"]["traffic_authorized"] is False
    assert found["buyer_demand_verified"] is False
    assert found["outbound_authorized"] is False


def test_buyer_evidence_brain_never_upgrades_missing_contract():
    from datetime import datetime, timezone
    from empire_os.buyer_evidence_brain import plan_evidence_work
    from empire_os.publisher_commercial_triage import publisher_next_evidence
    stamp = datetime(2026, 10, 25, 22, 0, tzinfo=timezone.utc)
    source = {
        "domain": "solarbriton.co.uk",
        "last_reply_id": "1a159bed9fcc61ac",
        "source": "EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED",
        "last_buyer_reply_id": "1a159bed9fcc61ac",
        "last_reply_signals": [PILOT, RATE, TERMS],
        "outbound_authorized": False,
    }
    decision = publisher_next_evidence(source)
    row = {
        "domain": "solarbriton.co.uk",
        "last_reply_id": "1a159bed9fcc61ac",
        "next_action": decision["next_action"],
        "publisher_next_evidence": decision,
        "buyer_demand_verified": False,
        "outbound_authorized": False,
    }
    result = plan_evidence_work([row], buyer_snapshot=None, now=stamp)
    assert result["commercial_proof_task_count"] == 1
    assert result["buyer_capacity_evidence"]["status"] == "SOURCE_MISSING"
    assert result["commercial_proof_tasks"][0]["gmail_source_ref"] == (
        "gmail:1a159bed9fcc61ac"
    )
    assert result["commercial_proof_tasks"][0]["task"] == (
        "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
    )
    assert result["any_contract_approved"] is False
    assert result["lead_delivery_authorized"] is False
    assert result["new_emails_sent"] is False
    assert result["recognized_revenue"] is None


def test_buyer_evidence_brain_rejects_claimed_send_authority():
    import pytest
    from datetime import datetime, timezone
    from empire_os.buyer_evidence_brain import plan_evidence_work
    with pytest.raises(ValueError, match="UNTRUSTED_PUBLISHER_EVIDENCE"):
        plan_evidence_work(
            [{"outbound_authorized": True, "buyer_demand_verified": False}],
            buyer_snapshot=None,
            now=datetime(2026, 10, 25, tzinfo=timezone.utc),
        )
