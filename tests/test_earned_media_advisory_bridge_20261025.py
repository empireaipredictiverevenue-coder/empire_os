"""Strict regression on the no-send/no-CRM bridge and source authenticity."""
import json
from pathlib import Path

from empire_os.earned_media_advisory_bridge import (
    GROWTH_ARTICLE, GROWTH_PITCH, PR_CONTACT, PR_PRICES, PR_SEND, PROPOSAL,
    TENDER, review,
)


def save(root: Path, relative: str, data) -> None:
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data) if isinstance(data, dict) else data)


def prepared(tmp_path):
    main = tmp_path / "main"
    pr = tmp_path / "pr"
    main.mkdir()
    pr.mkdir()
    save(pr, PR_SEND, {
        "schema_version": "empire.pr_editorial_gmail_submission_evidence.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "future_outreach_authorized": False,
        "canonical_governed_outbound_activation": False,
        "submission_count": 2,
        "records": [
            {"outlet": "BusinessCloud", "thread_id": "abc123",
             "message_id": "msg1", "provider_label": "SENT",
             "receipt_verified": True},
            {"outlet": "Prolific North", "thread_id": "def123",
             "message_id": "msg2", "provider_label": "SENT",
             "receipt_verified": True},
        ],
    })
    save(pr, PR_CONTACT, {"mode": "OBSERVE", "outlets": [
        {"outlet": "BusinessCloud", "pitch_sent": False},
        {"outlet": "Prolific North", "pitch_sent": False},
        {"outlet": "UKTN", "pitch_sent": False},
    ]})
    save(pr, PR_PRICES, {
        "approval": {"decision": "FOUNDER_APPROVES_PROPOSED_PRICING_ONLY",
                     "excludes": ["contracts", "payments", "crm_write",
                                  "production_activation"]},
        "services": [
            {"code": "consultancy_ai_revenue_opportunity_assessment",
             "name": "Assessment", "amount_minor": 250000,
             "currency": "GBP", "billing_model": "one_off",
             "existing_catalog_product_code": None},
            {"code": "consultancy_predictive_revenue_strategy_blueprint",
             "name": "Blueprint", "amount_minor": 750000,
             "currency": "GBP", "billing_model": "one_off",
             "existing_catalog_product_code": None},
            {"code": "consultancy_strategic_ai_revenue_advisory",
             "name": "Advisory", "amount_minor": 300000,
             "currency": "GBP", "billing_model": "monthly",
             "existing_catalog_product_code": None},
        ],
    })
    save(main, GROWTH_PITCH, "# GROWTH-001 — prepared, NOT sent\nCompare the Cloud; SME Today")
    save(main, GROWTH_ARTICLE, "Original study and commercial enquiry draft")
    save(main, PROPOSAL, "Review-only native buyer proposal packet")
    save(main, TENDER, "Original tender consultancy held")
    save(main, "runtime/revenue_distribution/latest.json", {
        "mode": "OBSERVE", "execution_authority": "none",
        "publisher_supply_recruitment": {
            "execution_authority": "none", "candidate_count": 12,
            "email_submitted_count": 4, "evidence_observed_date": "2026-10-10"
        },
    })
    return main, pr


def test_integrated_review_deduplicates_prior_sends_and_has_no_authority(tmp_path):
    main, pr = prepared(tmp_path)
    result = review(main, pr_root=pr)
    assert result["status"] == "REVIEW_CONNECTED_NOT_PRODUCTION_ACTIVATION"
    assert result["lane_counts"] == {"pr": 3, "editorial": 3, "consultancy": 4,
                                     "proposal": 1}
    assert len([x for x in result["items"] if x["source_provider_thread"]]) == 2
    assert len([x for x in result["items"] if x["label"] == "BusinessCloud"]) == 1
    assert result["publisher_supply"]["historical_snapshot"]
    assert result["revenue_verification_state"] == "NOT_QUERIED"
    assert review(main, pr_root=pr) == result
    for item in result["items"]:
        assert item["execution_authority"] == "none"
        assert not item["approved_to_contact"]
        assert not item["approved_to_quote"]
        assert not item["approved_to_publish"]
        assert item["crm_linkage"]["canonical_opportunity_id"] is None
    assert result["smart_crm_writes"] is False
    assert result["empiredb_writes"] is False


def test_invalid_send_receipt_never_creates_sent_claim(tmp_path):
    main, pr = prepared(tmp_path)
    p = pr / PR_SEND
    data = json.loads(p.read_text())
    data["records"][0]["receipt_verified"] = False
    save(pr, PR_SEND, data)
    packet = review(main, pr_root=pr)
    assert packet["sources"]["pr_sent_receipts"]["state"] == "HELD_CONTRADICTORY_SEND_EVIDENCE"
    assert not any(x["state"] == "SENT_PROVIDER_RECEIPT_REPLY_UNVERIFIED"
                   for x in packet["items"])
    assert all(x["state"] == "HOLD_PRIOR_SEND_HISTORY_UNVERIFIED"
               for x in packet["items"] if x["lane"] == "pr")


def test_price_tamper_fails_closed(tmp_path):
    main, pr = prepared(tmp_path)
    p = pr / PR_PRICES
    data = json.loads(p.read_text())
    data["services"][0]["amount_minor"] = 100
    save(pr, PR_PRICES, data)
    packet = review(main, pr_root=pr)
    assert packet["sources"]["consultancy_pricing"]["state"] == "HELD_UNVERIFIED_PRICE_OR_AUTHORITY"
    assert not any(i["amount_minor"] is not None for i in packet["items"])


def test_symlink_source_rejected_and_no_escape(tmp_path):
    main, pr = prepared(tmp_path)
    p = pr / PR_SEND
    p.unlink()
    p.symlink_to(tmp_path / "missing.json")
    packet = review(main, pr_root=pr)
    assert packet["sources"]["pr_sent_receipts"]["state"] == "HELD_SOURCE_UNAVAILABLE_OR_INVALID"
    assert not any(i["source_provider_thread"] for i in packet["items"])


def test_missing_independent_pr_worktree_is_visible(tmp_path):
    main, pr = prepared(tmp_path)
    packet = review(main)
    assert packet["status"] == "REVIEW_CONNECTED_WITH_SOURCE_GAPS"
    assert packet["lane_counts"]["pr"] == 0
    assert packet["lane_counts"]["editorial"] == 3
    assert packet["new_outbound_authorized"] is False


def test_invalid_approval_exclusions_cannot_force_quote(tmp_path):
    main, pr = prepared(tmp_path)
    path = pr / PR_PRICES
    data = json.loads(path.read_text())
    data["approval"]["excludes"] = None
    save(pr, PR_PRICES, data)
    packet = review(main, pr_root=pr)
    assert packet["sources"]["consultancy_pricing"]["state"] == "HELD_UNVERIFIED_PRICE_OR_AUTHORITY"
    assert not any(item["approved_to_quote"] for item in packet["items"])
