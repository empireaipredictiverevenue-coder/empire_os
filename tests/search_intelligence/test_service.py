from fastapi.testclient import TestClient
from empire_os.search_intelligence.service import build_search_intelligence_service


def test_service_exposes_bounded_search_product_reads():
    client = TestClient(build_search_intelligence_service())
    health = client.get('/health'); assert health.status_code == 200
    assert health.json()['execution_allowed'] is False
    products = client.get('/v1/search/products'); assert products.status_code == 200
    assert products.json()['execution_allowed'] is False
    assert products.json()['commercial_terms_required'] is True
    readiness = client.get('/v1/search/products/readiness'); assert readiness.status_code == 200
    assert readiness.json()['execution_allowed'] is False
