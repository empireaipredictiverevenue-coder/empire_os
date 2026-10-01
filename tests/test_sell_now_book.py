from empire_os.sell_now_book import (
    build_sell_now_book,
)


def ready_product(code):
    return {
        "product_id": "p1",
        "product_code": code,
        "product_name": code,
        "product_family": "test",
        "billing_model": "one_time",
        "currency": "USD",
        "active": True,
        "binding_terms_ready": True,
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "verified_at": "2026-09-23T00:00:00Z",
        "price_basis": {
            "status": "verified",
        },
        "readiness_blockers": [],
    }


def test_specific_verified_factory_ready_is_sell_now():
    catalog = {
        "products": [
            ready_product(
                "competitor_search_gap"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "title":
                "Denver roofing competitor search gap",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 1
    assert (
        book["sell_now"][0]["status"]
        == "SELL_NOW"
    )


def test_generic_search_word_does_not_trigger_technical():
    catalog = {
        "products": [
            ready_product(
                "technical_search_audit"
            ),
            ready_product(
                "serp_intelligence_api"
            ),
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "title":
                "Predictive revenue enterprise search opportunity",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["matched_route_count"] == 0


def test_generic_acquisition_does_not_trigger_private_capital():
    catalog = {
        "products": [
            ready_product(
                "private_capital_rollup"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "summary":
                "Customer acquisition opportunity",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["matched_route_count"] == 0


def test_private_equity_is_specific_fit():
    catalog = {
        "products": [
            ready_product(
                "private_capital_rollup"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "summary":
                "Private equity roll-up opportunity",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 1


def test_specific_fit_without_evidence_is_not_sell_now():
    catalog = {
        "products": [
            ready_product(
                "competitor_search_gap"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "title":
                "Competitor search gap",
            "factory_ready": True,
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 0
    assert (
        book["needs_evidence_count"]
        == 1
    )


def test_general_product_requires_review():
    catalog = {
        "products": [
            ready_product(
                "managed_service"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-1",
            "title":
                "Strong commercial opportunity",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 0
    assert book["needs_review_count"] == 1


def test_solar_country_match():
    catalog = {
        "products": [
            ready_product(
                "solar_opportunity_map_gb"
            )
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_id": "opp-gb",
            "title":
                "UK solar installer demand",
            "factory_ready": True,
            "evidence_refs": ["e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 1


def test_canonical_opportunity_factory_ready_is_sell_now():
    catalog = {
        "products": [
            ready_product("competitor_search_gap")
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_key":
                "market:roofing:denver",
            "title":
                "Competitor search gap",
            "opportunity_factory_ready": True,
            "evidence_refs": ["canonical:e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["sell_now_count"] == 1
    assert (
        book["sell_now"][0]["opportunity_id"]
        == "market:roofing:denver"
    )


def test_explicit_radar_product_reference_outranks_text():
    catalog = {
        "products": [
            ready_product("managed_service"),
            ready_product("technical_search_audit"),
        ]
    }

    radar = {
        "candidates": [{
            "opportunity_key":
                "market:class-action-lawyer:atlanta",
            "title":
                "Search opportunity for law firm",
            "offer_key": "managed_service",
            "products": ["managed_service"],
            "opportunity_factory_ready": True,
            "evidence_refs": ["canonical:e1"],
        }]
    }

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    assert book["matched_route_count"] == 1
    assert book["sell_now_count"] == 1
    assert (
        book["sell_now"][0]["product_code"]
        == "managed_service"
    )
    assert (
        book["sell_now"][0]["fit_scope"]
        == "explicit"
    )
