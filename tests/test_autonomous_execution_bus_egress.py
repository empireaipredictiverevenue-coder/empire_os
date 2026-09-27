import importlib
import inspect
import sys


def _load_bus(monkeypatch, tmp_path):
    env = tmp_path / "empire.env"
    env.write_text(
        "EMPIRE_DATA_BACKEND=supabase_legacy\n"
        "SUPABASE_URL=https://example.supabase.co\n"
        "SUPABASE_SERVICE_KEY=test-service-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EMPIRE_ENV_PATH", str(env))
    sys.modules.pop("empire_os.autonomous_execution_bus", None)
    return importlib.import_module("empire_os.autonomous_execution_bus")


def test_execution_bus_contains_no_direct_vendor_transport(monkeypatch, tmp_path):
    bus = _load_bus(monkeypatch, tmp_path)
    source = inspect.getsource(bus)

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "urllib.request" not in source
    assert "_rest_json" not in source


def test_execution_bus_runtime_env_is_passed_to_gateway(monkeypatch, tmp_path):
    bus = _load_bus(monkeypatch, tmp_path)
    seen = {}
    fake_gateway = object()
    fake_repo = object()

    def gateway_factory(env):
        seen["env"] = env
        return fake_gateway

    def repository_factory(gateway):
        seen["gateway"] = gateway
        return fake_repo

    monkeypatch.setattr(bus, "gateway_from_environment", gateway_factory)
    monkeypatch.setattr(bus, "ExecutionBusDataRepository", repository_factory)

    result = bus._data_repository()

    assert seen["env"]["EMPIRE_DATA_BACKEND"] == "supabase_legacy"
    assert seen["gateway"] is fake_gateway
    assert result is fake_repo


def test_execution_bus_rpc_wraps_repository_failure(monkeypatch, tmp_path):
    bus = _load_bus(monkeypatch, tmp_path)

    class Repo:
        def rpc(self, name, payload):
            raise RuntimeError("backend unavailable")

    monkeypatch.setattr(bus, "_data_repository", lambda: Repo())

    try:
        bus.rpc("claim_next_gtm_job", {})
    except bus.BusError as exc:
        assert "claim_next_gtm_job" in str(exc)
        assert "backend unavailable" in str(exc)
    else:
        raise AssertionError("repository failure must be wrapped as BusError")
