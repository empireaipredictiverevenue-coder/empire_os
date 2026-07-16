"""Tests for the AGI Loop orchestrator."""
import asyncio
from unittest.mock import MagicMock

import pytest
from empire_os.agi_loop import AgiLoop


@pytest.fixture
def mock_clients():
    return {
        "agi_scout": MagicMock(tick=MagicMock(return_value={"ok": True})),
        "agi_marketing": MagicMock(tick=MagicMock(return_value={"ok": True})),
        "agi_sales": MagicMock(tick=MagicMock(return_value={"ok": True})),
        "agi_closer": MagicMock(tick=MagicMock(return_value={"ok": True})),
        "ceo_fn": MagicMock(tick=MagicMock(return_value={"ok": True})),
    }


@pytest.fixture
def loop_orchestrator(mock_clients):
    return AgiLoop(
        agi_scout_client=mock_clients["agi_scout"],
        agi_marketing_client=mock_clients["agi_marketing"],
        agi_sales_agent=mock_clients["agi_sales"],
        agi_closer_agent=mock_clients["agi_closer"],
        ceo_brief_fn=mock_clients["ceo_fn"],
        intervals={
            "agi-scout": 1,       # 1s for fast tests
            "agi-marketing": 1,
            "agi-sales": 1,
            "agi-closer": 1,
            "ceo-brief": 1,
        },
    )


class TestAgiLoop:
    def test_init(self, loop_orchestrator):
        """Loop should have 5 clients registered."""
        assert len(loop_orchestrator.clients) == 5

    def test_status(self, loop_orchestrator):
        """status() returns running=False initially."""
        status = loop_orchestrator.status()
        assert status["running"] is False
        assert "agents" in status
        assert "intervals" in status
        assert len(status["agents"]) == 5

    @pytest.mark.asyncio
    async def test_start_runs_all_loops(self, loop_orchestrator, mock_clients):
        """start() spawns a task per agent and runs at least one cycle."""
        await loop_orchestrator.start()
        # Wait long enough for at least one cycle of each
        await asyncio.sleep(2.5)
        await loop_orchestrator.stop()

        # Each mock client.tick should have been called at least once
        for name in ["agi_scout", "agi_marketing", "agi_sales", "agi_closer", "ceo_fn"]:
            assert mock_clients[name].tick.call_count >= 1, f"{name} not called"

    @pytest.mark.asyncio
    async def test_metrics_update(self, loop_orchestrator):
        """After cycles, metrics.cycles should be > 0."""
        await loop_orchestrator.start()
        await asyncio.sleep(2)
        await loop_orchestrator.stop()

        status = loop_orchestrator.status()
        for name in status["agents"]:
            assert status["agents"][name]["cycles"] >= 1

    @pytest.mark.asyncio
    async def test_backoff_on_error(self, mock_clients):
        """Errors should be caught and logged without crashing the loop."""
        mock_clients["agi_sales"].tick.side_effect = RuntimeError("LLM down")
        loop = AgiLoop(
            agi_scout_client=mock_clients["agi_scout"],
            agi_marketing_client=mock_clients["agi_marketing"],
            agi_sales_agent=mock_clients["agi_sales"],
            agi_closer_agent=mock_clients["agi_closer"],
            ceo_brief_fn=mock_clients["ceo_fn"],
            intervals={"agi-scout": 1, "agi-marketing": 1, "agi-sales": 1,
                       "agi-closer": 1, "ceo-brief": 1},
        )
        await loop.start()
        await asyncio.sleep(2.5)
        await loop.stop()

        # Other agents should still have completed cycles
        status = loop.status()
        assert status["agents"]["agi-scout"]["last_error"] is None
        assert status["agents"]["agi-sales"]["last_error"] is not None

    def test_stop_event_set(self, loop_orchestrator):
        """stop() sets the stop event."""
        loop_orchestrator._stop.set()
        assert loop_orchestrator._stop.is_set()