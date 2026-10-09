from pathlib import Path

from empire_os.buyer_network_integration import (
    integration_status,
)


def test_runtime_bridge_exists():

    assert Path(
        "scripts/run_buyer_network_runtime_bridge.py"
    ).exists()


def test_existing_stack_remains_ready():

    status = integration_status()

    assert status.ready is True
    assert status.authority == "OBSERVE"
