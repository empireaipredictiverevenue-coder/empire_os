from empire_os.founder_approved_commercial_sync import (
    _identity_rows,
    sync_founder_approved_commercial_pricing,
)


class FakeRequest:
    def __init__(self):
        self.catalog = {}
        self.proposals = []

    def __call__(self, method, path, payload=None, **kwargs):
        if path.endswith("/register_commercial_product_identity"):
            return {
                "product_id": "product-" + payload["p_product_code"],
                "product_code": payload["p_product_code"],
            }

        if path.endswith("/get_commercial_product_catalog"):
            code = payload["p_product_code"]
            row = self.catalog.get(code)
            return [row] if row else []

        if path.endswith("/propose_commercial_product_version"):
            code = payload["p_product_code"]
            self.proposals.append(dict(payload))
            self.catalog[code] = {
                "product_code": code,
                "version_id": "version-" + code,
                "version_state": "PENDING",
                "binding_terms_ready": False,
                "price_basis": dict(payload["p_price_basis"]),
            }
            return {
                "decision": "proposed",
                "version_id": "version-" + code,
                "version_state": "PENDING",
            }

        raise AssertionError((method, path))


def test_founder_commercial_rows_cover_exchange_and_predictive_revenue():
    rows = {row["product_code"]: row for row in _identity_rows()}

    assert len(rows) == 9
    assert rows["exchange_seat_starter"]["amount_cents"] == 9900
    assert rows["exchange_seat_enterprise"]["amount_cents"] == 99900
    assert rows["predictive_revenue_diagnostic"]["amount_cents"] == 2_500_000
    assert (
        rows["predictive_revenue_private_strategic"]["amount_cents"]
        == 25_000_000
    )


def test_founder_commercial_sync_is_idempotent_on_matching_price():
    request = FakeRequest()

    first = sync_founder_approved_commercial_pricing(request=request)
    second = sync_founder_approved_commercial_pricing(request=request)

    assert first["error_count"] == 0
    assert first["result_count"] == 9
    assert len(request.proposals) == 9
    assert second["error_count"] == 0
    assert all(
        row["decision"] == "existing_approved_price"
        for row in second["results"]
    )
    assert len(request.proposals) == 9
