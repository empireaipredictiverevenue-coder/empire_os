import inspect

import pytest

import empire_os.sb as sb


class FakeGateway:
    def __init__(self, configured=True):
        self.configured = configured
        self.calls = []

    def select(self, table, columns, filters, order, limit, offset):
        self.calls.append(("select", table))
        return [{"id": "1"}]

    def query(
        self,
        table,
        columns="*",
        *,
        filters=(),
        order=(),
        limit=1000,
        offset=0,
    ):
        self.calls.append((
            "query",
            table,
            columns,
            tuple(filters),
            tuple(order),
            limit,
            offset,
        ))
        return [{"id": "1"}]

    def insert(self, table, row, *, return_repr=True):
        self.calls.append(("insert", table))
        return [dict(row)] if return_repr else []

    def upsert(
        self,
        table,
        row,
        *,
        conflict_columns,
        action,
        return_repr=True,
    ):
        self.calls.append((
            "upsert",
            table,
            tuple(conflict_columns),
            action.value,
        ))
        return [dict(row)] if return_repr else []

    def insert_ignore_conflicts(
        self,
        table,
        row,
        *,
        conflict_columns=(),
        return_repr=False,
    ):
        self.calls.append((
            "insert_ignore_conflicts",
            table,
            tuple(conflict_columns),
        ))
        return [dict(row)] if return_repr else []

    def update(self, table, match, values):
        self.calls.append(("update", table, dict(match)))
        return [dict(values)]

    def delete(self, table, match):
        self.calls.append(("delete", table, dict(match)))

    def rpc(self, name, params=None):
        self.calls.append(("rpc", name, dict(params or {})))
        return {"ok": True}


def test_sb_has_no_vendor_credentials_or_http_transport():
    source = inspect.getsource(sb)
    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "urllib.request" not in source
    assert "urlopen(" not in source
    assert "Authorization" not in source


def test_sb_routes_legacy_alias_through_gateway(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_gateway", lambda: gateway)

    assert sb.select("si_outbox") == [{"id": "1"}]
    assert gateway.calls == [("select", "outbox_messages")]


def test_sb_write_operations_delegate_to_gateway(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_gateway", lambda: gateway)

    assert sb.insert("prospects", {"id": "1"}) == [{"id": "1"}]
    assert sb.update("prospects", {"id": "1"}, {"status": "new"}) == [{"status": "new"}]
    assert sb.delete("prospects", {"id": "1"}) is None
    assert sb.rpc("claim_next_gtm_job") == {"ok": True}

    assert gateway.calls == [
        ("insert", "prospects"),
        ("update", "prospects", {"id": "1"}),
        ("delete", "prospects", {"id": "1"}),
        ("rpc", "claim_next_gtm_job", {}),
    ]


def test_unconfigured_backend_preserves_compatibility_noop(monkeypatch):
    gateway = FakeGateway(configured=False)
    monkeypatch.setattr(sb, "_gateway", lambda: gateway)

    assert sb.select("prospects") == []
    assert sb.insert("prospects", {"id": "1"}) == []
    assert sb.update("prospects", {"id": "1"}, {"status": "x"}) == []
    assert sb.delete("prospects", {"id": "1"}) is None
    assert sb.rpc("anything") is None
    assert gateway.calls == []


def test_each_sb_operation_selects_gateway_once(monkeypatch):
    gateway = FakeGateway()
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return gateway

    monkeypatch.setattr(sb, "_gateway", factory)
    sb.select("prospects")

    assert calls["count"] == 1


def test_request_json_routes_rpc_without_http(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: gateway)

    result = sb.request_json(
        "POST",
        "/rest/v1/rpc/example_rpc",
        payload={"p_id": "1"},
    )

    assert result == {"ok": True}
    assert gateway.calls == [("rpc", "example_rpc", {"p_id": "1"})]


def test_request_json_translates_table_read(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: gateway)

    rows = sb.request_json(
        "GET",
        "/rest/v1/prospects?select=id,status&status=eq.ready&order=id.desc&limit=5",
    )

    assert rows == [{"id": "1"}]
    call = gateway.calls[0]
    assert call[0:3] == ("query", "prospects", "id,status")
    assert call[5:] == (5, 0)
    assert call[3][0].column == "status"
    assert call[3][0].value == "ready"
    assert call[4][0].column == "id"
    assert call[4][0].descending is True


def test_request_json_translates_upsert(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: gateway)

    rows = sb.request_json(
        "POST",
        "/rest/v1/business_entities?on_conflict=id",
        payload={"id": "entity-1"},
        prefer="resolution=merge-duplicates,return=representation",
    )

    assert rows == [{"id": "entity-1"}]
    assert gateway.calls == [
        ("upsert", "business_entities", ("id",), "merge")
    ]


def test_request_json_fails_closed_for_embedded_select(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: gateway)

    with pytest.raises(ValueError, match="domain repository"):
        sb.request_json(
            "GET",
            "/rest/v1/prospects?select=id,qualifications(id)",
        )


def test_request_json_fails_closed_for_egress_probe(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: gateway)

    with pytest.raises(ValueError, match="backend provider"):
        sb.request_json(
            "GET",
            "/rest/v1/prospects?select=id&limit=1",
            allow_egress_probe=True,
        )

def test_compatibility_parser_supports_not_is_null():
    from empire_os.sb import _data_filter
    from empire_os.data_query import FilterOperator

    item = _data_filter("website", "not.is.null")
    assert item.column == "website"
    assert item.operator is FilterOperator.IS_NOT_NULL
    assert item.value is None

def test_compatibility_in_filter_strips_postgrest_quotes():
    from empire_os.sb import _data_filter
    from empire_os.data_query import FilterOperator

    item = _data_filter(
        "niche",
        'in.("roofing","solar","mass tort lawyer")',
    )

    assert item.operator is FilterOperator.IN
    assert item.value == (
        "roofing",
        "solar",
        "mass tort lawyer",
    )


def test_compatibility_in_filter_preserves_unquoted_values():
    from empire_os.sb import _data_filter
    from empire_os.data_query import FilterOperator

    item = _data_filter("status", "in.(new,qualified)")

    assert item.operator is FilterOperator.IN
    assert item.value == ("new", "qualified")


def test_compat_scalar_preserves_iso_timezone_plus():
    from empire_os.sb import _table_request_parts

    (
        _table,
        _columns,
        filters,
        _ordering,
        _limit,
        _offset,
        _conflicts,
    ) = _table_request_parts(
        "/rest/v1/qualifications?"
        "scored_at=eq.2026-09-28T08%3A56%3A28%2B00%3A00"
    )

    assert len(filters) == 1
    assert filters[0].value == "2026-09-28T08:56:28+00:00"


def test_unwrap_data_value_normalizes_native_empiredb_types():
    from datetime import date, datetime, timezone
    from decimal import Decimal
    from uuid import UUID

    from empire_os.data_values import unwrap_data_value

    uid = UUID("12345678-1234-5678-1234-567812345678")

    value = {
        "id": uid,
        "created_at": datetime(
            2026, 9, 28, 8, 56, 28, tzinfo=timezone.utc
        ),
        "day": date(2026, 9, 28),
        "amount": Decimal("12.50"),
        "nested": [{"prospect_id": uid}],
    }

    result = unwrap_data_value(value)

    assert result == {
        "id": "12345678-1234-5678-1234-567812345678",
        "created_at": "2026-09-28T08:56:28+00:00",
        "day": "2026-09-28",
        "amount": "12.50",
        "nested": [
            {
                "prospect_id":
                "12345678-1234-5678-1234-567812345678"
            }
        ],
    }


def test_compatibility_parser_supports_json_text_filter():
    from empire_os.data_query import FilterOperator
    from empire_os.sb import _data_filter

    item = _data_filter(
        "evidence->>niche",
        "eq.solar",
    )

    assert item.column == "evidence->>niche"
    assert item.operator is FilterOperator.EQ
    assert item.value == "solar"
