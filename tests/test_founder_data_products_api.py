from fastapi.testclient import TestClient

from empire_os.founder_data_products_api import create_founder_data_products_router
from fastapi import FastAPI


def app():
    value = FastAPI()
    value.include_router(create_founder_data_products_router())
    return value


def test_catalog_is_read_only_and_unpriced():
    client = TestClient(app())
    response = client.get("/v1/founder-data-products")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_authority"] == "none"
    assert payload["products"]
    assert all(row["pricing_cents"] is None for row in payload["products"])


def test_unknown_product_404s():
    client = TestClient(app())
    assert client.get("/v1/founder-data-products/nope").status_code == 404



def test_recovered_vertical_products_are_visible():
    client = TestClient(app())
    payload = client.get("/v1/founder-data-products").json()
    rows = {row["key"]: row for row in payload["products"]}

    assert "permit_intelligence_feed" in rows
    assert "property_intelligence_monitor" in rows
    assert "private_capital_intelligence" in rows

    for key in (
        "permit_intelligence_feed",
        "property_intelligence_monitor",
        "private_capital_intelligence",
    ):
        assert rows[key]["pricing_cents"] is None
        assert rows[key]["execution_authority"] == "none"
