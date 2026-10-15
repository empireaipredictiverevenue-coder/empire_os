from datetime import datetime, timezone

import pytest

from empire_os.departments import default_departments
from empire_os.executive_commercial_roles import review_executive_commercial_roles

NOW = datetime(2026, 10, 15, 12, 20, tzinfo=timezone.utc)


def evidence(**overrides):
    p = {
        "name": "AceLeads", "domain": "aceleads.co.uk", "market": "UK",
        "state": "APPLICATION_ACKNOWLEDGED", "evidence_refs": [
            "docs/commercial/ACELEADS_APPLICATION_EVIDENCE_20261013.json"
        ],
        "last_touch_at": "2026-10-13T11:00:00Z",
        "contact_history_verified": True,
        "suppressed": False,
        "paid_revenue_verified": False,
    }
    p.update(overrides)
    return p


def operations(**overrides):
    p = {
        "department_cycle_status": "FAILED",
        "astra_dispatcher_status": "SUCCEEDED",
        "department_cycle_failure_reason":
            "opportunities_runtime source proof stale or untrusted",
        "founder_attention_items": 281, "founder_notifications_sent": False,
        "evidence_refs": [
            "systemd:empire-department-cycle.service:2026-10-15T12:04:43Z",
            "runtime/astra/department_cycle_latest.json",
        ],
    }
    p.update(overrides)
    return p


def review(cases, ops=None):
    return review_executive_commercial_roles(cases, ops or operations(), as_of=NOW)


def test_existing_application_not_classified_as_fresh_or_as_revenue():
    result = review([evidence()])
    case = result["business_development"]["partner_cases"][0]
    assert case["next_action"] == "OBTAIN_HUMAN_BUYING_BRIEF"
    assert result["business_development"]["fresh_verified_uncontacted_count"] == 0
    assert case["paid_revenue_claim"] != "VERIFIED_SEPARATELY"
    assert result["email_sent"] is False
    assert result["outbound_enabled"] is False


def test_accepted_leadsdowork_not_approved_for_live_supply():
    result = review([evidence(
        name="LeadsDoWork", domain="leads.work", state="PARTNER_ACCEPTED"
    )])
    case = result["business_development"]["partner_cases"][0]
    assert case["next_action"] == "RESOLVE_TERMS_SOURCE_CONSENT_AND_SANDBOX"
    assert case["contact_allowed"] is False
    assert result["commercial_terms_accepted"] is False


def test_new_uk_or_us_candidate_with_unverified_contact_history_is_held():
    for market in ("UK", "USA"):
        item = evidence(
            name="Research Prospect", domain="fresh.example", market=market,
            state="RESEARCH_ONLY", last_touch_at=None, contact_history_verified=False
        )
        result = review([item])
        case = result["business_development"]["partner_cases"][0]
        assert case["next_action"] == "RECONCILE_MAILBOX_AND_CRM_BEFORE_ANY_OUTREACH"
        assert result["business_development"]["fresh_verified_uncontacted_count"] == 0


def test_suppressed_person_never_recontacted_even_after_human_reply():
    result = review([evidence(
        state="HUMAN_REPLY", suppressed=True,
    )])
    case = result["business_development"]["partner_cases"][0]
    assert case["status"] == "SUPPRESSED"
    assert case["next_action"] == "NO_CONTACT"
    assert case["contact_allowed"] is False


def test_hard_bounce_requires_suppression():
    with pytest.raises(ValueError, match="suppression state"):
        review([evidence(state="HARD_BOUNCE", suppressed=False)])
    assert review([evidence(state="HARD_BOUNCE", suppressed=True)])[
        "business_development"]["partner_cases"][0]["next_action"] == "NO_CONTACT"


def test_cannot_sneak_duplicate_company_through_www():
    with pytest.raises(ValueError, match="duplicate domain"):
        review([evidence(), evidence(domain="www.aceleads.co.uk", name="Ace Leads")])


def test_coo_surface_production_failure_without_bypassing_security():
    result = review([evidence()])
    coo = result["coo"]
    first = coo["tasks"][0]
    assert first["action"] == "RESTORE_VERIFIED_DEPARTMENT_FINALISATION"
    assert first["bypass_guard_allowed"] is False
    assert first["production_activation_allowed"] is False
    assert result["chief_of_staff"]["operation_has_unresolved_incident"] is True
    assert len(result["chief_of_staff"]["founder_brief"]["risks"]) == 1
    assert result["chief_of_staff"]["founder_brief"]["verified_outcomes"] == []
    assert result["db_writes"] is False


def test_attention_rows_are_not_converted_to_unique_blocker_count():
    tasks = review([])["coo"]["tasks"]
    triage = next(t for t in tasks if t["action"] == "DEDUPLICATE_AND_TRIAGE_FOUNDER_ATTENTION")
    assert triage["unresolved_attention_rows"] == 281
    assert triage["unique_business_blocker_count"] is None


def test_operational_evidence_fail_closes():
    with pytest.raises(ValueError):
        review([], operations(department_cycle_status="FAILED", department_cycle_failure_reason=""))
    with pytest.raises(ValueError):
        review([], operations(founder_attention_items=-1))
    with pytest.raises(ValueError):
        review([], operations(department_cycle_status="SUCCEEDED"))


@pytest.mark.parametrize("changes", [
    {"last_touch_at": "2030-10-01T00:00:00Z"},
    {"last_touch_at": "2026-10-13T12:00:00"},
    {"domain": "https://aceleads.co.uk/login"},
    {"evidence_refs": []},
    {"contact_history_verified": None},
])
def test_bad_partner_evidence_fails_closed(changes):
    with pytest.raises(ValueError):
        review([evidence(**changes)])


def test_roles_extend_existing_departments_instead_of_creating_duplicate_units():
    departments = {d.key: d for d in default_departments()}
    assert {"coo", "chief_of_staff"} <= set(departments["strategy"].agent_roles)
    assert "business_development" in departments["sales_revenue"].agent_roles
    assert departments["strategy"].components[0] == "astra_executive"


def test_date_only_application_receipt_is_not_given_an_invented_timestamp():
    case = evidence(last_touch_at=None, last_touch_date="2026-10-13")
    output = review([case])["business_development"]["partner_cases"][0]
    assert output["last_touch_date"] == "2026-10-13"
    assert output["last_touch_at"] is None
    assert output["next_action"] == "OBTAIN_HUMAN_BUYING_BRIEF"


def test_date_only_evidence_rejects_future_date():
    with pytest.raises(ValueError, match="future"):
        review([evidence(last_touch_at=None, last_touch_date="2027-01-01")])


def test_sample_handoff_packet_matches_real_contact_and_operations_evidence():
    import json
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parents[1]
        / "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json"
    )
    packet = json.loads(fixture.read_text())
    report = review_executive_commercial_roles(
        packet["partners"], packet["operations"],
        as_of=datetime.fromisoformat(packet["as_of"].replace("Z", "+00:00")),
    )
    by_domain = {
        r["domain"]: r
        for r in report["business_development"]["partner_cases"]
    }
    assert by_domain["aceleads.co.uk"]["relationship_state"] == "APPLICATION_ACKNOWLEDGED"
    assert by_domain["aceleads.co.uk"]["last_touch_at"] is None
    assert by_domain["rvnu.com"]["next_action"] == "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY"
    assert by_domain["leads.work"]["next_action"] == "RESOLVE_TERMS_SOURCE_CONSENT_AND_SANDBOX"
    assert report["business_development"]["fresh_verified_uncontacted_count"] == 0
    assert report["coo"]["department_cycle_status"] == "FAILED"
    assert report["business_development"]["emails_sent"] == 0


def test_boolean_fields_cannot_be_forged_by_integer_one():
    with pytest.raises(ValueError, match="explicit boolean"):
        review([evidence(contact_history_verified=1)])
    with pytest.raises(ValueError, match="explicit boolean"):
        review([evidence(suppressed=0)])
    with pytest.raises(ValueError, match="notification"):
        review([], operations(founder_notifications_sent=1))


def test_chief_of_staff_top_three_owner_actions_are_evidence_bounded():
    from datetime import datetime
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json"
    packet = json.loads(p.read_text())
    output = review_executive_commercial_roles(
        packet["partners"], packet["operations"],
        as_of=datetime.fromisoformat(packet["as_of"].replace("Z", "+00:00")),
    )
    tasks = output["chief_of_staff"]["top_three_next_actions"]
    assert len(tasks) == 3
    assert tasks[0]["owner"] == "coo"
    assert tasks[0]["action"] == "RESTORE_VERIFIED_DEPARTMENT_FINALISATION"
    assert tasks[1]["partner"] == "LeadsDoWork"
    assert tasks[2]["partner"] == "AceLeads"
    assert all(t["evidence_refs"] and t["external_action_authorized"] is False for t in tasks)
