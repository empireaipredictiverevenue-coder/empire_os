from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_discovery_recovery.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_discovery_recovery",
        PATH,
    )

    mod = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        mod
    )

    return mod


def test_exists():
    assert PATH.exists()


def test_domain():

    mod = module()

    assert (
        mod.normalise_domain(
            "https://www.example.com/publishers"
        )
        == "example.com"
    )


def test_buyer_signals():

    mod = module()

    assert (
        mod.buyer_signal_count(
            "publisher program pay per call payout"
        )
        >= 3
    )


def test_vertical():

    mod = module()

    assert (
        "roofing"
        in mod.detect_verticals(
            "roofing publisher"
        )
    )


def test_google_ignored():

    mod = module()

    assert (
        mod.normalise_domain(
            "https://google.com"
        )
        is None
    )
