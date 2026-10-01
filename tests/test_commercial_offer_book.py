from empire_os.commercial_offer_book import (
    build_commercial_offer_book,
)


def ready_product(code="managed_service"):
    return {
        "product_id": "p1",
        "product_code": code,
        "product_name": "Ready Product",
        "product_family": "test",
        "billing_model": "one_time",
        "currency": "USD",
        "active": True,
        "binding_terms_ready": True,
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "verified_at": "2026-09-30T00:00:00Z",
        "readiness_blockers": [],
        "price_basis": {
            "amount_cents": 24900,
            "currency": "USD",
            "unit": "per_report",
        },
    }


def test_person_email_and_ready_product_make_offer_package():
    book = build_commercial_offer_book(
        catalog={
            "products": [
                ready_product()
            ]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Example",
                "domain": "example.com",
                "person_name": "Buyer Person",
                "person_verified": True,
                "email": "buyer@example.com",
                "email_verified": True,
                "product_codes": [
                    "managed_service"
                ],
                "demand_state": "UNKNOWN",
            }]
        },
    )

    assert book["offer_ready_count"] == 1

    row = book["offer_ready"][0]

    assert row["state"] == "OFFER_READY"
    assert row["offer_package_ready"] is True

    # Commercial fit is not buyer-demand proof.
    assert row["buyer_demand_verified"] is False

    # Price is not predicted revenue.
    assert row["expected_revenue_cents"] is None

    # Never auto-authorize outbound.
    assert row["live_send_ready"] is False
    assert (
        row["live_outbound_authorized"]
        is False
    )


def test_unready_product_cannot_enter_offer_ready():
    product = ready_product(
        "predictive_revenue_os"
    )

    product["catalog_state"] = "UNKNOWN"
    product["binding_terms_ready"] = False

    book = build_commercial_offer_book(
        catalog={
            "products": [product]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Enterprise",
                "person_verified": True,
                "email_verified": True,
                "product_codes": [
                    "predictive_revenue_os"
                ],
            }]
        },
    )

    assert book["offer_ready_count"] == 0
    assert (
        book["targets"][0]["state"]
        == "PRODUCT_READINESS_REQUIRED"
    )


def test_ready_product_without_verified_person_is_blocked():
    book = build_commercial_offer_book(
        catalog={
            "products": [
                ready_product(
                    "competitor_search_gap"
                )
            ]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Roofing Co",
                "person_verified": False,
                "email_verified": False,
                "product_codes": [
                    "competitor_search_gap"
                ],
            }]
        },
    )

    assert book["offer_ready_count"] == 0
    assert (
        book["targets"][0]["state"]
        == "CONTACT_EVIDENCE_REQUIRED"
    )


def test_existing_thread_is_preserved_not_restarted():
    book = build_commercial_offer_book(
        catalog={
            "products": [
                ready_product()
            ]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Example",
                "person_verified": True,
                "email_verified": True,
                "product_codes": [
                    "managed_service"
                ],
                "conversation_refs": [
                    "conversation-1"
                ],
            }]
        },
    )

    row = book["offer_ready"][0]

    assert (
        row["contact_mode"]
        == "EXISTING_THREAD_REVIEW"
    )

    assert (
        "founder_live_outbound_approval_required"
        in row["send_blockers"]
    )


def test_price_amount_is_required_for_offer_ready():
    product = ready_product()
    product["price_basis"] = {
        "currency": "USD",
        "unit": "per_report",
    }

    book = build_commercial_offer_book(
        catalog={
            "products": [product]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Example",
                "person_verified": True,
                "email_verified": True,
                "product_codes": [
                    "managed_service"
                ],
            }]
        },
    )

    assert book["offer_ready_count"] == 0


def test_price_amount_is_required_for_offer_ready():
    product = ready_product()
    product["price_basis"] = {
        "currency": "USD",
        "unit": "per_report",
    }

    book = build_commercial_offer_book(
        catalog={
            "products": [product]
        },
        revenue_distribution={
            "human_review_queue": [{
                "company": "Example",
                "person_verified": True,
                "email_verified": True,
                "product_codes": [
                    "managed_service"
                ],
            }]
        },
    )

    assert book["offer_ready_count"] == 0
