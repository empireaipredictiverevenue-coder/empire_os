import inspect

import empire_os.sb as sb


class FakeGateway:
    def __init__(self, configured=True):
        self.configured = configured
        self.calls = []

    def select(self, table, columns, filters, order, limit, offset):
        self.calls.append(("select", table))
        return [{"id": "1"}]

    def insert(self, table, row, *, return_repr=True):
        self.calls.append(("insert", table))
        return [dict(row)] if return_repr else []

    def update(self, table, match, values):
        self.calls.append(("update", table))
        return [dict(values)]

    def delete(self, table, match):
        self.calls.append(("delete", table))

    def rpc(self, name, params=None):
        self.calls.append(("rpc", name))
        return {"ok": True}


def test_sb_has_no_vendor_credentials_or_urls():
    source = inspect.getsource(sb)
    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source


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
        ("update", "prospects"),
        ("delete", "prospects"),
        ("rpc", "claim_next_gtm_job"),
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
