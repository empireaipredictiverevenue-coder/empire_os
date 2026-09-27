from empire_os.market_sweep_revenue_gps import (
    build_market_sweep_runtime,
    fetch_market_sweep_postgres,
    normalize_market_sweep,
    write_market_sweep_snapshot,
)


def _catalog():
    return [{
        "product_code": "managed_service",
        "product_name": "Empire Opportunity Intelligence Pilot",
        "currency": "USD",
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "binding_terms_ready": True,
        "price_basis": {"amount_cents": 150000},
        "acquisition_cost_basis": {"amount_cents": 30000},
        "fulfilment_cost_basis": {"amount_cents": 30000},
        "margin_policy": {"minimum_margin_bps": 5500},
    }]


def _raw():
    return {
        "schema_version": "empire.market_sweep_revenue_gps.v1",
        "generated_at": "2026-09-22T15:00:00+00:00",
        "window_days": 7,
        "markets": [{
            "niche": "roofing",
            "metro": "denver, co",
            "prospect_count": 13,
            "canonical_company_count": 5,
            "scored_prospect_count": 13,
            "acquisition_count": 13,
            "qualification_count": 5,
            "approved_buyer_count": 1,
            "delivered_outreach_count": 1,
            "commercial_reply_count": 0,
            "commercial_terms_count": 0,
            "verified_payment_count": 0,
            "recognized_revenue_event_count": 0,
            "recognized_revenue_cents": 0,
            "realized_margin_cents": 0,
            "competitive_entity_count": 4,
            "competitive_signal_count": 23,
        }],
        "execution_authority": "none",
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
    }


def test_normalize_market_sweep_keeps_demand_unobserved():
    result = normalize_market_sweep(_raw(), catalog=_catalog())
    market = result["markets"][0]

    assert result["market_count"] == 1
    assert result["commercial_demand_market_count"] == 0
    assert market["commercial_demand_state"] == "not_observed"
    assert market["commercial_demand_evidence_count"] == 0
    assert market["supply_gap_state"] == "unknown_not_measured"
    assert market["supply_gap_inferred"] is False
    assert market["buyer_intent_inferred"] is False
    assert market["commercial_intent_inferred"] is False
    assert market["market_share_inferred"] is False
    assert market["revenue_inferred"] is False
    assert market["execution_authority"] == "none"


def test_competitor_pressure_is_explicit_model_not_market_share():
    result = normalize_market_sweep(_raw(), catalog=_catalog())
    market = result["markets"][0]

    assert market["competitor_pressure_proxy"] is not None
    assert market["competitor_pressure_is_model"] is True
    assert market["competitor_pressure_basis"] == (
        "competitive_signal_density"
    )
    assert market["market_share_inferred"] is False


def test_verified_product_candidate_does_not_infer_purchase():
    result = normalize_market_sweep(_raw(), catalog=_catalog())
    market = result["markets"][0]
    economics = market["economics_scenario"]

    assert market["product_candidate"] == "managed_service"
    assert market["product_purchase_inferred"] is False
    assert economics["pilot_price_cents"] == 150000
    assert economics["policy_cost_ceiling_cents"] == 60000
    assert economics["policy_margin_at_ceiling_cents"] == 90000
    assert economics["prediction"] is False
    assert economics["actual_cost_observed"] is False
    assert economics["actual_revenue"] is False
    assert market["market_revenue_prediction_cents"] is None


def test_genuine_commercial_reply_becomes_observed_demand_evidence():
    raw = _raw()
    raw["markets"][0]["commercial_reply_count"] = 1
    result = normalize_market_sweep(raw, catalog=_catalog())
    market = result["markets"][0]

    assert result["commercial_demand_market_count"] == 1
    assert market["commercial_demand_state"] == "observed"
    assert market["commercial_demand_evidence_count"] == 1
    assert market["buyer_intent_inferred"] is False


class _Cursor:
    def __init__(self):
        self.calls = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, tuple(params or ())))
        if normalized.startswith(
            "SELECT public.get_market_sweep_revenue_gps"
        ):
            self.row = (_raw(),)
        elif normalized.startswith(
            "SELECT public.get_commercial_product_catalog"
        ):
            self.row = (_catalog(),)

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


def test_postgres_reader_uses_restricted_role():
    cursor = _Cursor()

    def connect(dsn):
        assert dsn == "postgresql://restricted/market"
        return _Connection(cursor)

    result = fetch_market_sweep_postgres(
        "postgresql://restricted/market",
        window_days=7,
        limit=500,
        connect_factory=connect,
    )

    assert result["market_count"] == 1
    assert cursor.calls == [
        ("SET LOCAL ROLE empire_intelligence_materializer", ()),
        (
            "SELECT public.get_market_sweep_revenue_gps(%s,%s)",
            (7, 200),
        ),
        (
            "SELECT public.get_commercial_product_catalog(%s,%s)",
            ("managed_service", 5),
        ),
    ]


def test_runtime_reads_snapshot(tmp_path):
    payload = normalize_market_sweep(_raw(), catalog=_catalog())
    write_market_sweep_snapshot(payload, tmp_path)

    result = build_market_sweep_runtime(tmp_path)

    assert result["available"] is True
    assert result["market_count"] == 1
    assert result["markets"][0]["niche"] == "roofing"
