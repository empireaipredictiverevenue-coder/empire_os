"""Regression tests for the production no-simulation invariant."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from empire_os.auto_pilot import AutoPilot
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.agents import marketplace_agent
from empire_os.agents import outreach_runner
from empire_os.agents import satellite_strike_cap_agent


class _ObservedAgent(SyntheticAgent):
    """Minimal legacy-named agent without filesystem-heavy base init."""

    def __init__(self):
        self._log = lambda *args, **kwargs: None

    def observe(self) -> dict:
        return {}

    def reason(self, state: dict) -> str:
        return "{}"

    def act(self, decision: str) -> dict:
        return {"ok": True}


def test_shared_agent_learning_is_real_observation_only():
    agent = _ObservedAgent()
    learned = agent.learn(
        {"source": "real"},
        '{"action":"observe"}',
        {"ok": True, "summary": "observed"},
    )
    assert learned["mode"] == "real_observations_only"
    assert learned["examples"] == []
    assert learned["observed_success"] is True


def test_legacy_outreach_transports_are_fail_closed():
    assert outreach_runner.send_via_resend(
        "buyer@example.com", "subject", "body", {}
    ) == (False, "legacy_outreach_retired_use_governed_phase3e")
    assert outreach_runner._smtp_fallback(
        "buyer@example.com", "subject", "body"
    ) == (False, "legacy_outreach_retired_use_governed_phase3e")


def test_legacy_autopilot_never_posts():
    pilot = AutoPilot()
    calls = []

    def fake_http(method, path, payload=None):
        calls.append((method, path, payload))
        return 200, {"prospects": []}

    pilot._http = fake_http
    report = pilot.run_cycle()
    assert report.sent == 0
    assert report.settled == 0
    assert calls
    assert all(method == "GET" for method, _, _ in calls)


def test_marketplace_pending_order_stays_pending_without_real_evidence(
    tmp_path, monkeypatch
):
    orders_path = tmp_path / "orders.json"
    services_path = tmp_path / "services.json"
    wallets_path = tmp_path / "wallets.json"
    ledger_path = tmp_path / "ledger.jsonl"
    orders_path.write_text(json.dumps([{"id": "o1", "status": "pending"}]))
    services_path.write_text("[]")

    monkeypatch.setattr(marketplace_agent, "ORDERS_PATH", orders_path)
    monkeypatch.setattr(marketplace_agent, "SERVICES_PATH", services_path)
    monkeypatch.setattr(marketplace_agent, "WALLETS_PATH", wallets_path)
    monkeypatch.setattr(marketplace_agent, "LEDGER_PATH", ledger_path)

    agent = object.__new__(marketplace_agent.MarketplaceAgent)
    result = agent._process_orders()
    order = json.loads(orders_path.read_text())[0]
    assert result["n_processed"] == 0
    assert result["mode"] == "real_evidence_only"
    assert order["status"] == "pending"
    assert "tx_hash" not in order
    assert not wallets_path.exists()
    assert not ledger_path.exists()


def test_satellite_fake_alert_entrypoint_removed():
    assert not hasattr(satellite_strike_cap_agent, "synthetic_fire_test")


def test_marketplace_never_counts_legacy_completion_as_actual_revenue(
    tmp_path, monkeypatch
):
    orders_path = tmp_path / "orders.json"
    services_path = tmp_path / "services.json"
    wallets_path = tmp_path / "wallets.json"
    orders_path.write_text(
        json.dumps([{"id": "old", "status": "complete", "price_usdc": 25.0}])
    )
    services_path.write_text("[]")
    wallets_path.write_text("{}")
    monkeypatch.setattr(marketplace_agent, "ORDERS_PATH", orders_path)
    monkeypatch.setattr(marketplace_agent, "SERVICES_PATH", services_path)
    monkeypatch.setattr(marketplace_agent, "WALLETS_PATH", wallets_path)

    agent = object.__new__(marketplace_agent.MarketplaceAgent)
    state = agent.observe()
    assert state["total_revenue_usdc"] == 0.0
    assert state["legacy_unverified_complete_value_usdc"] == 25.0
    assert state["actual_revenue_source"] == "canonical_phase3f_only"


def test_finance_replay_endpoint_is_permanently_fail_closed():
    source = Path("empire_os/hub.py").read_text()
    tree = ast.parse(source)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "finance_replay"
    )
    executable = [
        node for node in fn.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert len(executable) == 1
    assert isinstance(executable[0], ast.Raise)
