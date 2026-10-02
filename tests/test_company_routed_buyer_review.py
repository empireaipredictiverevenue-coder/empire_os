from empire_os.company_routed_buyer_review import (
    build_company_routed_review_queue,
)


def test_unique_same_domain_economic_buyer_is_founder_review_ready():
    payload = build_company_routed_review_queue([{
        "prospect_id": "p1",
        "business_name": "TopDog Law",
        "offer_key": "predictive_revenue_diagnostic",
        "priority_score": 100,
        "target_people": [{
            "name": "James Helm",
            "title": "Founder, Attorney",
            "evidence_url": "https://topdoglaw.com/about-us",
            "source": "official_site_current",
        }],
        "company_contact_routes": [{
            "channel": "email",
            "value": "reception@topdoglaw.com",
            "verified": True,
            "person_bound": False,
            "source": "first_party_site",
            "evidence_url": "https://topdoglaw.com/about-us",
        }],
    }])
    assert payload["review_ready_count"] == 1
    row = payload["items"][0]
    assert row["state"] == "FOUNDER_REVIEW_READY"
    assert row["routing_person"]["name"] == "James Helm"
    assert row["company_routes"][0]["person_bound"] is False
    assert row["outbound_authorized"] is False
    assert row["founder_gate_required"] is True


def test_cross_domain_person_evidence_is_rejected():
    payload = build_company_routed_review_queue([{
        "prospect_id": "p2",
        "business_name": "Example Law",
        "target_people": [{
            "name": "Jane Smith",
            "title": "Founder",
            "evidence_url": "https://directory.example/jane",
        }],
        "company_contact_routes": [{
            "channel": "email",
            "value": "info@examplelaw.com",
            "verified": True,
            "source": "first_party_site",
            "evidence_url": "https://examplelaw.com/contact",
        }],
    }])
    assert payload["review_ready_count"] == 0
    assert payload["candidate_count"] == 0
    assert payload["no_same_domain_person_count"] == 1


def test_tied_top_authority_people_are_ambiguous():
    payload = build_company_routed_review_queue([{
        "prospect_id": "p3",
        "business_name": "Apex",
        "target_people": [
            {
                "name": "AJ Brown",
                "title": "Co-Chief Executive Officer",
                "evidence_url": "https://apex.example/team",
            },
            {
                "name": "Will Matson",
                "title": "Co-Chief Executive Officer",
                "evidence_url": "https://apex.example/team",
            },
        ],
        "company_contact_routes": [{
            "channel": "email",
            "value": "info@apex.example",
            "verified": True,
            "source": "first_party_privacy_policy",
            "evidence_url": "https://apex.example/privacy",
        }],
    }])
    assert payload["review_ready_count"] == 0
    assert payload["ambiguous_person_count"] == 1
    assert payload["items"][0]["state"] == "AMBIGUOUS_PERSON"
    assert payload["outbound_authorized"] is False


def test_prior_company_domain_is_excluded_from_review_queue():
    payload = build_company_routed_review_queue(
        [{
            "prospect_id": "p4",
            "business_name": "Example Roofing",
            "target_people": [{
                "name": "Jane Smith",
                "title": "Founder",
                "evidence_url": "https://example.com/about",
            }],
            "company_contact_routes": [{
                "channel": "email",
                "value": "info@example.com",
                "verified": True,
                "source": "first_party_site",
                "evidence_url": "https://example.com/contact",
            }],
        }],
        prior_contact_domains={"example.com"},
    )
    assert payload["candidate_count"] == 0
    assert payload["review_ready_count"] == 0
    assert payload["prior_contact_history_count"] == 1


def test_prior_prospect_is_excluded_even_with_new_route():
    payload = build_company_routed_review_queue(
        [{
            "prospect_id": "p5",
            "business_name": "Example HVAC",
            "target_people": [{
                "name": "John Smith",
                "title": "Owner",
                "evidence_url": "https://examplehvac.com/about",
            }],
            "company_contact_routes": [{
                "channel": "email",
                "value": "office@examplehvac.com",
                "verified": True,
                "source": "first_party_site",
                "evidence_url": "https://examplehvac.com/contact",
            }],
        }],
        prior_contact_prospect_ids={"p5"},
    )
    assert payload["candidate_count"] == 0
    assert payload["prior_contact_history_count"] == 1


def test_suppressed_company_route_is_excluded():
    payload = build_company_routed_review_queue(
        [{
            "prospect_id": "p6",
            "business_name": "Example Solar",
            "target_people": [{
                "name": "Alex Smith",
                "title": "Founder",
                "evidence_url": "https://examplesolar.com/about",
            }],
            "company_contact_routes": [{
                "channel": "email",
                "value": "info@examplesolar.com",
                "verified": True,
                "source": "first_party_site",
                "evidence_url": "https://examplesolar.com/contact",
            }],
        }],
        suppressed_emails={"info@examplesolar.com"},
    )
    assert payload["candidate_count"] == 0
    assert payload["suppressed_route_count"] == 1
