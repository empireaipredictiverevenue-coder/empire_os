from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/run_buyer_network_discovery_observer.py"
)


def load_module():

    spec = spec_from_file_location(
        "buyer_network_discovery_observer",
        PATH,
    )

    module = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        module
    )

    return module


def test_observer_exists():

    assert PATH.exists()


def test_queries_target_buyer_networks():

    module = load_module()

    queries = " ".join(
        item["query"]
        for item in module.SEARCHES
    ).lower()

    assert "publisher" in queries
    assert "pay per call" in queries
    assert "roofing" in queries
    assert "hvac" in queries
    assert "restoration" in queries


def test_domain_extraction():

    module = load_module()

    result = module.domains_from_text(
        "https://buyerone.com/publishers "
        "https://www.buyertwo.ai/home "
        "https://google.com/search"
    )

    assert "buyerone.com" in result
    assert "buyertwo.ai" in result
    assert "google.com" not in result


def test_no_execution_authority():

    text = PATH.read_text()

    assert '"OUTBOUND_ENABLED": "0"' in text
    assert '"LIVE_OUTBOUND": "0"' in text


def test_founder_do_not_pursue_domain_is_not_extracted_from_stale_search():
    module = load_module()
    found = module.domains_from_text(
        "https://www.callvox.pro/publishers "
        "https://polyares.com/pay-per-call-affiliate-program"
    )
    assert "callvox.pro" not in found
    assert found == {"polyares.com"}
