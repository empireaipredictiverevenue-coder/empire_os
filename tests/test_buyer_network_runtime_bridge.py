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


def test_runtime_domain_extraction_respects_founder_do_not_pursue():
    from scripts.run_buyer_network_runtime_bridge import extract_observed_domains
    domains = extract_observed_domains({
        "candidates": [
            {"website": "https://www.callvox.pro/"},
            {"buyer_domain": "polyares.com"},
            {"company_domain": "callvox.pro"},
        ]
    })
    assert "callvox.pro" not in domains
    assert domains == {"polyares.com"}
