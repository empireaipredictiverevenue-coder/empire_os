import inspect

import empire_os.market_pricing as pricing
from empire_os.market_pricing_repository import MarketPricingRepository


class FakeGateway:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params=None):
        self.calls.append((name, dict(params or {})))
        if name == "get_commercial_product_catalog":
            return [{
                "product_code": "solar_opportunity_map_gb",
                "version_id": "v1",
            }]
        if name == "register_commercial_product_identity":
            return {
                "decision": "identity_synchronized",
                "product_id": "p1",
            }
        if name == "propose_commercial_product_version":
            return {
                "decision": "proposed",
                "version_id": "v1",
            }
        raise AssertionError(name)


def test_market_pricing_repository_uses_semantic_gateway_rpc_names():
    gateway = FakeGateway()
    repository = MarketPricingRepository(gateway)

    rows = repository.catalog_rows("solar_opportunity_map_gb")
    identity = repository.register_product_identity({
        "p_product_code": "solar_opportunity_map_gb",
    })
    version = repository.propose_product_version({
        "p_product_code": "solar_opportunity_map_gb",
    })

    assert rows[0]["version_id"] == "v1"
    assert identity["decision"] == "identity_synchronized"
    assert version["decision"] == "proposed"
    assert [name for name, _ in gateway.calls] == [
        "get_commercial_product_catalog",
        "register_commercial_product_identity",
        "propose_commercial_product_version",
    ]


def test_market_pricing_business_module_has_no_vendor_transport_dependency():
    source = inspect.getsource(pricing)

    assert "qualification_worker_v2" not in source
    assert "/rest/v1/" not in source
    assert "SUPABASE_" not in source
    assert "urllib" not in source
