from datetime import datetime, timezone

from empire_os.permit_buyer_outreach_draft import (
    build_permit_buyer_outreach_draft,
)


def _packet():
    return {
        "conversation_ready": True,
        "live_outbound_send": False,
        "buyer": {
            "domain": "vipfiresprinkler.com",
            "business_name": "V.I.P FIRE SPRINKLERS INC",
        },
        "decision_makers": [
            {
                "name": "Thomas A. Petronis",
                "role": "Officer, Owner",
            },
            {
                "name": "Matthew R. Petronis",
                "role": "Officer, CT Mgr; BBB lists VP",
            },
        ],
        "contact_routes": {
            "emails": ["vipfiresprinkler@aol.com"],
            "phones": ["+17185965086", "+17189453315"],
            "person_bound": False,
        },
        "supply": {
            "verified_current_inventory": 2914,
        },
        "offer": {
            "product_name": "Permit Intelligence",
            "amount_cents": 49900,
            "currency": "USD",
            "unit": "per_month",
            "binding_terms_ready": True,
        },
    }


def test_company_route_outreach_draft_is_specific_and_send_blocked():
    draft = build_permit_buyer_outreach_draft(
        _packet(),
        observed_at=datetime(
            2026, 9, 24, 21, 0, tzinfo=timezone.utc
        ),
    )

    assert draft["recipient_route"]["email"] == (
        "vipfiresprinkler@aol.com"
    )
    assert draft["recipient_route"]["person_bound"] is False
    assert draft["recipient_route"]["attention"] == (
        "Thomas A. Petronis or Matthew R. Petronis"
    )
    assert "2,914 NYC permit records" in draft["body_text"]
    assert "not assuming all of those are relevant" in draft["body_text"]
    assert "$499/month" in draft["body_text"]
    assert "boroughs / project types" in draft["body_text"]
    assert "opportunities you could review" in draft["body_text"]
    assert draft["send_gate_ready"] is False
    assert "founder_live_outbound_approval_required" in (
        draft["send_gate_blockers"]
    )
    assert "company_route_not_person_bound" in (
        draft["send_gate_blockers"]
    )
    assert draft["live_outbound_send"] is False
    assert draft["actual_revenue"] is False


def test_draft_rejects_non_conversation_ready_packet():
    packet = _packet()
    packet["conversation_ready"] = False

    try:
        build_permit_buyer_outreach_draft(packet)
    except ValueError as exc:
        assert "conversation-ready" in str(exc)
    else:
        raise AssertionError("expected conversation-ready guard")


def test_draft_rejects_missing_company_email():
    packet = _packet()
    packet["contact_routes"]["emails"] = []

    try:
        build_permit_buyer_outreach_draft(packet)
    except ValueError as exc:
        assert "company email route" in str(exc)
    else:
        raise AssertionError("expected company email guard")


def test_draft_does_not_accept_person_bound_route():
    packet = _packet()
    packet["contact_routes"]["person_bound"] = True

    try:
        build_permit_buyer_outreach_draft(packet)
    except ValueError as exc:
        assert "company-route outreach" in str(exc)
    else:
        raise AssertionError("expected company-route guard")
