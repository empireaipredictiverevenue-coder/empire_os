import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_legacy_module():
    path = ROOT / "mcp_lead_server.py"
    spec = importlib.util.spec_from_file_location("legacy_mcp_lead_server", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_root_mcp_manifest_is_retired_and_canonicalizes_bsc_usdt():
    payload = json.loads((ROOT / "mcp_manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "retired"
    assert payload["settlement"]["currency"] == "USDT"
    assert payload["settlement"]["chain"] == "BSC"
    assert payload["settlement"]["payment_execution"] is False
    assert payload["settlement"]["revenue_recognition"] is False
    assert payload["canonical_runtime"]["public_base_url"] == "https://empire-ai.co.uk"


def test_legacy_mcp_server_is_fail_closed_by_default(monkeypatch):
    module = _load_legacy_module()
    monkeypatch.delenv(module.LEGACY_MCP_ENABLE_ENV, raising=False)
    assert module.legacy_runtime_enabled() is False
    assert module.main() == 2


def test_legacy_mcp_requires_explicit_yes(monkeypatch):
    module = _load_legacy_module()
    monkeypatch.setenv(module.LEGACY_MCP_ENABLE_ENV, "no")
    assert module.legacy_runtime_enabled() is False
    monkeypatch.setenv(module.LEGACY_MCP_ENABLE_ENV, "YES")
    assert module.legacy_runtime_enabled() is True
