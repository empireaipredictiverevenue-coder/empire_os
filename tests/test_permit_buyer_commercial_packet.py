from datetime import datetime, timezone

from empire_os.permit_buyer_commercial_packet import (
    build_permit_buyer_packet,
)


def _candidate():
    return {
        "id": "buyer-candidate-1",
        "domain": "vipfiresprinkler.com",
        "business_name": "V.I.P FIRE SPRINKLERS INC",
        "website": "https://vipfiresprinkler.com/",
        "buyer_type": "qualified_end_buyer",
        "target_product_codes": ["permit_intelligence"],
        "target_corridor_keys": [
            "permit-recovery:v1:general_contractor:nyc"
        ],
        "review_state": "review_ready",
        "reconciliation_state": "REVIEW_READY",
        "site_evidence": {
            "permit_territory_state": "NYC_FIRST_PARTY_EVIDENCE",
            "permit_territory_evidence": [
                "new york city",
                "brooklyn",
            ],
            "first_party_emails": [
                "vipfiresprinkler@aol.com",
                "emailvipfiresprinkler@aol.comcall",
            ],
            "first_party_phones": [
                "(718) 945-3315",
                "718-596-5086",
            ],
        },
    }


def _inventory():
    return {
        "verified_current_inventory": 1706,
        "verified_current_owner_identified": 1258,
        "verified_current_project_only": 448,
        "niche_counts": {
            "general_contractor": 1588,
            "plumbing": 412,
        },
        "full_scan_complete": False,
    }


def _catalog():
    return {
        "active": True,
        "product_id": "product-1",
        "product_code": "permit_intelligence",
        "product_name": "Permit Intelligence",
        "billing_model": "monthly_subscription",
        "currency": "USD",
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "binding_terms_ready": True,
        "price_basis": {
            "state": "VERIFIED",
            "amount_cents": 49900,
            "currency": "USD",
            "unit": "per_month",
            "approval_reference": "founder_approval:test",
        },
    }


def _evidence():
    return {
        "domain": "vipfiresprinkler.com",
        "decision_maker_priority": [
            {
                "name": "Thomas A. Petronis",
                "role": "Officer, Owner",
                "confidence": "official_public_record",
                "person_bound_email": None,
                "person_bound_phone": None,
            },
            {
                "name": "Matthew R. Petronis",
                "role": "Officer, CT Mgr; BBB lists VP",
                "confidence": (
                    "official_public_record_plus_business_directory"
                ),
                "person_bound_email": None,
                "person_bound_phone": None,
            },
        ],
        "contact_route": {
            "type": "company_route",
            "email": "vipfiresprinkler@aol.com",
            "phone": "718-596-5086",
            "fallback_phone": "718-945-3315",
            "person_bound": False,
        },
    }


def test_review_ready_vip_packet_is_conversation_ready_but_not_send_ready():
    packet = build_permit_buyer_packet(
        candidate=_candidate(),
        inventory_summary=_inventory(),
        catalog=_catalog(),
        public_evidence=_evidence(),
        observed_at=datetime(
            2026, 9, 24, 20, 45, tzinfo=timezone.utc
        ),
    )

    assert packet["conversation_ready"] is True
    assert packet["offer"]["amount_cents"] == 49900
    assert packet["supply"]["verified_current_inventory"] == 1706
    assert packet["contact_routes"]["emails"] == [
        "vipfiresprinkler@aol.com"
    ]
    assert "emailvipfiresprinkler@aol.comcall" not in (
        packet["contact_routes"]["emails"]
    )
    assert packet["contact_routes"]["person_bound"] is False
    assert packet["live_outbound_send"] is False
    assert packet["buyer_activation_performed"] is False
    assert packet["terms_accepted"] is False
    assert packet["payment_request_created"] is False
    assert packet["actual_revenue"] is False
    assert packet["execution_authority"] == "review_packet_only"


def test_packet_rejects_non_review_ready_candidate():
    candidate = _candidate()
    candidate["review_state"] = "discovered"

    try:
        build_permit_buyer_packet(
            candidate=candidate,
            inventory_summary=_inventory(),
            catalog=_catalog(),
            public_evidence=_evidence(),
        )
    except ValueError as exc:
        assert "review_ready" in str(exc)
    else:
        raise AssertionError("expected review-ready guard")


def test_packet_rejects_non_nyc_permit_candidate():
    candidate = _candidate()
    candidate["site_evidence"]["permit_territory_state"] = (
        "NYC_NOT_OBSERVED"
    )

    try:
        build_permit_buyer_packet(
            candidate=candidate,
            inventory_summary=_inventory(),
            catalog=_catalog(),
            public_evidence=_evidence(),
        )
    except ValueError as exc:
        assert "NYC first-party territory" in str(exc)
    else:
        raise AssertionError("expected NYC territory guard")


def test_packet_rejects_unready_catalog():
    catalog = _catalog()
    catalog["binding_terms_ready"] = False

    try:
        build_permit_buyer_packet(
            candidate=_candidate(),
            inventory_summary=_inventory(),
            catalog=catalog,
            public_evidence=_evidence(),
        )
    except ValueError as exc:
        assert "terms-ready" in str(exc)
    else:
        raise AssertionError("expected catalog readiness guard")
