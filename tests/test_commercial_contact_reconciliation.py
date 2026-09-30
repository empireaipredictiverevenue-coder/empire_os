from empire_os.commercial_contact_reconciliation import (
    reconcile_review_contacts,
)


def contact(domain="example.com", name="Jane Smith", email="jane@example.com"):
    return {
        "person_name": name,
        "person_title": "CEO",
        "email": email,
        "source_url": f"https://{domain}/team/{name.lower().replace(' ', '-')}",
        "person_explicitly_named": True,
        "email_directly_bound_to_person": True,
        "contact_verification_ready": True,
        "outreach_authorized": True,
    }


def snapshot(*contacts, domain="example.com"):
    return {
        "items": [{
            "domain": domain,
            "contacts": list(contacts),
        }]
    }


def test_unique_verified_contact_promotes_review_contact_only():
    result = reconcile_review_contacts(
        [{
            "company": "Example",
            "domain": "example.com",
            "product_codes": ["managed_service"],
            "person_verified": False,
            "email_verified": False,
        }],
        snapshot(contact()),
    )

    row = result["review_rows"][0]
    assert result["promoted_count"] == 1
    assert row["person_name"] == "Jane Smith"
    assert row["email"] == "jane@example.com"
    assert row["person_verified"] is True
    assert row["email_verified"] is True
    assert row["execution_authority"] == "none"
    assert row["outreach_authorized"] is False


def test_multiple_verified_people_remain_ambiguous():
    result = reconcile_review_contacts(
        [{
            "company": "Example",
            "domain": "example.com",
            "person_verified": False,
            "email_verified": False,
        }],
        snapshot(
            contact(name="Jane Smith", email="jane@example.com"),
            contact(name="John Smith", email="john@example.com"),
        ),
    )

    row = result["review_rows"][0]
    assert result["promoted_count"] == 0
    assert result["ambiguous_domains"] == ["example.com"]
    assert row["person_verified"] is False
    assert row["email_verified"] is False


def test_cross_domain_email_fails_closed():
    result = reconcile_review_contacts(
        [{
            "domain": "example.com",
            "person_verified": False,
            "email_verified": False,
        }],
        snapshot(
            contact(email="jane@other.com"),
        ),
    )

    assert result["promoted_count"] == 0
    assert result["review_rows"][0]["person_verified"] is False


def test_cross_domain_source_url_fails_closed():
    bad = contact()
    bad["source_url"] = "https://other.com/team/jane-smith"

    result = reconcile_review_contacts(
        [{
            "domain": "example.com",
            "person_verified": False,
            "email_verified": False,
        }],
        snapshot(bad),
    )

    assert result["promoted_count"] == 0


def test_non_ready_contact_does_not_promote():
    pending = contact()
    pending["contact_verification_ready"] = False

    result = reconcile_review_contacts(
        [{
            "domain": "example.com",
            "person_verified": False,
            "email_verified": False,
        }],
        snapshot(pending),
    )

    assert result["promoted_count"] == 0
