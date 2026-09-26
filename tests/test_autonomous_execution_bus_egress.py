import importlib
import json
import sys


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _load_bus(monkeypatch, tmp_path):
    env = tmp_path / "empire.env"
    env.write_text(
        "SUPABASE_URL=https://example.supabase.co\n"
        "SUPABASE_SERVICE_KEY=test-service-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EMPIRE_ENV_PATH", str(env))
    monkeypatch.setenv("EMPIRE_COMPONENT", "crawler-acquisition")
    sys.modules.pop("empire_os.autonomous_execution_bus", None)
    return importlib.import_module("empire_os.autonomous_execution_bus")


def test_execution_bus_rest_uses_shared_egress_guard(monkeypatch, tmp_path):
    bus = _load_bus(monkeypatch, tmp_path)
    events = []
    monkeypatch.setattr(
        bus,
        "_reserve_supabase_request",
        lambda: events.append("reserve"),
    )
    monkeypatch.setattr(
        bus,
        "_close_supabase_egress_circuit",
        lambda: events.append("close"),
    )
    requests = []

    def opener(req, timeout=30):
        requests.append(req)
        return FakeResponse([{"id": "p1"}])

    monkeypatch.setattr(bus.urllib.request, "urlopen", opener)

    result = bus._rest_json(
        "GET",
        "/rest/v1/prospects",
        params={"select": "id", "limit": "1"},
    )

    assert result == [{"id": "p1"}]
    assert events == ["reserve", "close"]
    assert requests[0].headers["User-agent"] == "EmpireOS/crawler-acquisition"
    assert requests[0].headers["X-empire-component"] == "crawler-acquisition"
