"""A real publisher reply can advance negotiation without implying paid revenue."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from empire_os.executive_commercial_roles import review_executive_commercial_roles

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/commercial/EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json"


def evidence():
    return json.loads(EVIDENCE.read_text())


def assessed(data):
    return review_executive_commercial_roles(
        data["partners"],
        data["operations"],
        as_of=datetime.fromisoformat(data["as_of"].replace("Z", "+00:00")),
    )


def test_actual_solarbriton_response_is_a_discussion_not_accepted_pilot():
    review = assessed(evidence())
    cases = {r["domain"]: r for r in review["business_development"]["partner_cases"]}
    solar = cases["solarbriton.co.uk"]
    assert solar["relationship_state"] == "PILOT_DISCUSSION"
    assert solar["last_touch_at"] == "2026-10-15T10:34:23+00:00"
    assert solar["next_action"] == "QUALIFY_NO_UPFRONT_PERFORMANCE_PILOT"
    assert solar["contact_allowed"] is False
    assert solar["founder_outreach_approval_required"] is True
    assert solar["paid_revenue_claim"] == "NOT_ASSESSED_IN_THIS_LANE"
    assert review["outbound_enabled"] is False
    assert review["funds_moved"] is False
    assert review["commercial_terms_accepted"] is False


def test_chief_of_staff_prioritises_human_discussion_without_duplicate_introductions():
    review = assessed(evidence())
    priorities = review["chief_of_staff"]["top_three_next_actions"]
    assert [p["partner"] for p in priorities] == [
        "SolarBriton", "Home Services Lead Group", "LeadsDoWork"
    ]
    assert all(p["external_action_authorized"] is False for p in priorities)
    cases = {r["domain"]: r for r in review["business_development"]["partner_cases"]}
    assert cases["rvnu.com"]["next_action"] == "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY"
    assert cases["modernize.com"]["next_action"] == "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY"


def test_no_invented_buyer_approval_or_verified_new_contact():
    report = assessed(evidence())
    assert report["business_development"]["buyer_approval_implied"] is False
    assert report["business_development"]["commercial_revenue_implied"] is False
    assert report["business_development"]["fresh_verified_uncontacted_count"] == 0
    assert report["chief_of_staff"]["operation_has_unresolved_incident"] is False
    assert report["coo"]["mailbox_observer_state"] == "PROVIDER_ONLY"


def test_pilot_requires_actual_dated_email_evidence():
    data = evidence()
    solar = next(p for p in data["partners"] if p["domain"] == "solarbriton.co.uk")
    solar.pop("last_touch_at")
    with pytest.raises(ValueError, match="dated evidence"):
        assessed(data)


def test_account_dedupe_cannot_create_a_second_solarbriton():
    data = evidence()
    solar = next(p for p in data["partners"] if p["domain"] == "solarbriton.co.uk")
    data["partners"].append({**solar, "domain": "www.solarbriton.co.uk"})
    with pytest.raises(ValueError, match="duplicate domain"):
        assessed(data)


def test_stale_selective_mail_review_can_never_be_live_founder_partner_priority():
    data = evidence()
    data["operations"]["partner_snapshot_state"] = "STALE_REVIEW"
    report = assessed(data)
    tasks = report["chief_of_staff"]["top_three_next_actions"]
    assert all("partner" not in task for task in tasks)
    assert any(
        task["action"] == "REVALIDATE_CURRENT_PARTNER_EVIDENCE"
        for task in tasks
    )
    assert report["business_development"]["source_tasks"][0]["action"] == (
        "REVALIDATE_CURRENT_PARTNER_EVIDENCE"
    )
    assert report["business_development"]["emails_sent"] == 0


def test_hslg_is_existing_responding_us_network_not_new_or_contracted_buyer():
    review = assessed(evidence())
    cases = {row["domain"]: row for row in review["business_development"]["partner_cases"]}
    hslg = cases["homeservicesleadgroup.com"]
    assert hslg["market"] == "USA"
    assert hslg["relationship_state"] == "HUMAN_REPLY"
    assert hslg["contact_history_verified"] is True
    assert hslg["last_touch_at"] == "2026-10-09T23:25:31+00:00"
    assert hslg["next_action"] == "REVIEW_SUBSTANTIVE_REPLY_AND_PROPOSE_FOUNDER_ACTION"
    assert "gmail_message:1a114d6b9b33e40b" in hslg["evidence_refs"]
    assert "gmail_sent:1a122fc70c9614" in hslg["evidence_refs"]
    assert hslg["contact_allowed"] is False
    assert hslg["paid_revenue_claim"] == "NOT_ASSESSED_IN_THIS_LANE"
    assert "validatedlg.ai" not in cases
    assert review["email_sent"] is False
    assert review["outbound_enabled"] is False


def test_modernize_prior_outreach_is_not_treated_as_fresh_prospect():
    review = assessed(evidence())
    cases = {row["domain"]: row for row in review["business_development"]["partner_cases"]}
    modern = cases["modernize.com"]
    assert modern["relationship_state"] == "CONTACTED"
    assert modern["contact_history_verified"] is True
    assert modern["last_touch_at"] == "2026-10-13T09:35:38+00:00"
    assert "gmail_sent:1a1349e18b6e46cf" in modern["evidence_refs"]
    assert modern["next_action"] == "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY"
    assert modern["contact_allowed"] is False


def test_suppressed_warm_network_must_never_be_a_priority():
    data = evidence()
    warm = next(row for row in data["partners"]
                if row["domain"] == "homeservicesleadgroup.com")
    warm["state"] = "SUPPRESSED"
    warm["suppressed"] = True
    result = assessed(data)
    cases = {row["domain"]: row for row in result["business_development"]["partner_cases"]}
    assert cases["homeservicesleadgroup.com"]["next_action"] == "NO_CONTACT"
    assert all(row.get("partner") != "Home Services Lead Group"
               for row in result["chief_of_staff"]["top_three_next_actions"])


def test_live_buyer_capacity_priority_then_warm_us_thread_before_cold_targets():
    data=evidence()
    data['operations']['buyer_capacity_state']='NO_VERIFIED_COMMERCIAL_CAPACITY'
    report=assessed(data)
    priorities=report['chief_of_staff']['top_three_next_actions']
    assert [(p.get('partner'),p['action']) for p in priorities]==[
        (None,'VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY'),
        ('SolarBriton','QUALIFY_NO_UPFRONT_PERFORMANCE_PILOT'),
        ('Home Services Lead Group','REVIEW_SUBSTANTIVE_REPLY_AND_PROPOSE_FOUNDER_ACTION'),
    ]
    assert all(p['external_action_authorized'] is False for p in priorities)
    assert report['business_development']['buyer_approval_implied'] is False
    assert report['business_development']['commercial_revenue_implied'] is False
    assert report['funds_moved'] is False
    assert report['email_sent'] is False
