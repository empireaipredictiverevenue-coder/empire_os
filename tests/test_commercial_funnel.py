from empire_os.commercial_funnel import (
    build_funnel_runtime,
    fetch_founder_commercial_funnel_postgres,
    normalize_funnel_payload,
    write_funnel_snapshot,
)


def _raw():
    return {
        "schema_version": "empire.founder_commercial_funnel.v1",
        "generated_at": "2026-09-22T15:00:00+00:00",
        "counts": {
            "prospect_acquisitions": 493,
            "buyer_reviews": 34,
            "buyer_reviews_approved": 32,
            "outbound_intents": 31,
            "outbound_delivered": 25,
            "commercial_replies": 0,
            "unsubscribe_replies": 1,
            "closer_cases": 0,
            "commercial_terms_reviews": 0,
            "commercial_terms_approved": 0,
            "payment_requests": 0,
            "verified_payment_evidence": 0,
            "fulfilment_orders": 0,
            "fulfilled_orders": 0,
            "commercial_outcomes": 0,
            "recognized_revenue_events": 0,
        },
        "outbound_status_counts": {
            "delivered": 25,
            "cancelled": 3,
        },
        "reply_classification_counts": {
            "unsubscribe": 1,
        },
        "recognized_revenue_cents": 0,
        "realized_margin_cents": 0,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def test_normalize_funnel_identifies_waiting_external_stage():
    result = normalize_funnel_payload(_raw())

    assert result["current_stage"] == "outbound_delivered"
    assert result["next_event"] == "await_genuine_buyer_reply"
    assert result["counts"]["prospect_acquisitions"] == 493
    assert result["counts"]["outbound_delivered"] == 25
    assert result["counts"]["commercial_replies"] == 0
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_real_commercial_reply_advances_stage():
    raw = _raw()
    raw["counts"]["commercial_replies"] = 1
    result = normalize_funnel_payload(raw)

    assert result["current_stage"] == "buyer_conversation"
    assert result["next_event"] == "open_or_advance_closer"


def test_revenue_requires_canonical_recognized_event():
    raw = _raw()
    raw["counts"]["recognized_revenue_events"] = 1
    raw["recognized_revenue_cents"] = 150000
    raw["realized_margin_cents"] = 90000
    raw["actual_revenue"] = True

    result = normalize_funnel_payload(raw)

    assert result["current_stage"] == "recognized_revenue"
    assert result["actual_revenue"] is True
    assert result["recognized_revenue_cents"] == 150000
    assert result["realized_margin_cents"] == 90000


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
            "SELECT public.get_founder_commercial_funnel()"
        ):
            self.row = (_raw(),)

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


def test_postgres_funnel_uses_restricted_role():
    cursor = _Cursor()

    def connect(dsn):
        assert dsn == "postgresql://restricted/funnel"
        return _Connection(cursor)

    result = fetch_founder_commercial_funnel_postgres(
        "postgresql://restricted/funnel",
        connect_factory=connect,
    )

    assert result["current_stage"] == "outbound_delivered"
    assert cursor.calls == [
        ("SET LOCAL ROLE empire_intelligence_materializer", ()),
        ("SELECT public.get_founder_commercial_funnel()", ()),
    ]


def test_runtime_reads_snapshot(tmp_path):
    path = tmp_path / "runtime/commercial_funnel/latest.json"
    write_funnel_snapshot(_raw(), path)

    result = build_funnel_runtime(tmp_path)

    assert result["available"] is True
    assert result["current_stage"] == "outbound_delivered"
    assert result["counts"]["buyer_reviews_approved"] == 32
