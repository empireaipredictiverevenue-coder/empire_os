from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.products import (
    SEARCH_PRODUCTS,
    evaluate_product_readiness,
    get_search_product,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


def test_product_catalog_has_core_sellable_products():
    keys = {product.key for product in SEARCH_PRODUCTS}

    assert {
        "technical_search_audit",
        "search_opportunity_map",
        "content_protection",
        "authority_intelligence",
        "geo_ai_visibility",
        "organic_ai_recommendation_intelligence",
        "competitor_search_gap",
        "search_growth_command",
    } <= keys


def test_product_readiness_fails_closed_when_required_data_is_missing():
    product = get_search_product("search_growth_command")
    assert product is not None

    readiness = evaluate_product_readiness(
        product,
        {
            "pages": False,
            "indexation": False,
            "opportunities": False,
            "decay": False,
            "cannibalisation": False,
            "search_console": False,
        },
    )

    assert readiness["status"] == "GATED"
    assert readiness["pricing_observed"] is False
    assert readiness["publishing_authority"] is False
    assert readiness["indexation_authority"] is False


def test_product_readiness_becomes_ready_only_when_required_evidence_exists():
    product = get_search_product("technical_search_audit")
    assert product is not None

    readiness = evaluate_product_readiness(
        product,
        {
            "pages": True,
            "indexation": True,
            "internal_links": False,
            "search_console": False,
        },
    )

    assert readiness["status"] == "READY"
    assert readiness["missing_required"] == []
    assert readiness["optional_available"] == []


def test_search_product_api_is_available_without_canonical_repository():
    app = FastAPI()
    app.include_router(
        create_search_router(
            repository=None,
            search_console_adapter=DisabledSearchConsoleAdapter(
                SearchConsoleStatus(
                    enabled=False,
                    configured=False,
                    available=False,
                    reason="not_configured",
                )
            ),
        )
    )
    client = TestClient(app)

    catalog = client.get("/v1/search/products")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["count"] == len(SEARCH_PRODUCTS)
    assert body["execution_allowed"] is False
    assert body["pricing_observed"] is False

    detail = client.get("/v1/search/products/geo_ai_visibility")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["product"]["name"] == "AEO / GEO AI Visibility"
    assert payload["readiness"]["status"] == "GATED"

    missing = client.get("/v1/search/products/not-real")
    assert missing.status_code == 404



def test_serp_product_preserves_monetisation_models():
    product = get_search_product("serp_intelligence_api")
    assert product is not None
    assert product.commercial_model == "usage_and_subscription"
    assert {
        "api_usage",
        "prepaid_credits",
        "subscription",
        "agency_reseller_wholesale",
        "white_label_license",
        "enterprise_data_api_contract",
    } <= set(product.revenue_models)


def test_organic_ai_recommendation_product_has_measurement_not_guarantee_contract():
    product = get_search_product("organic_ai_recommendation_intelligence")
    assert product is not None
    assert product.name == "Organic + AI Recommendation Intelligence"
    assert {
        "organic_visibility_baseline",
        "ai_answer_presence",
        "ai_citation_presence",
        "ai_recommendation_presence",
        "share_of_observed_recommendations",
        "competitor_recommendation_gap",
        "search_to_revenue_attribution",
    } <= set(product.deliverables)
    assert product.required_capabilities == (
        "serp",
        "recommendation_visibility",
    )
    assert product.publishing_authority is False
    assert product.indexation_authority is False
